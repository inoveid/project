from __future__ import annotations

import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Optional

from app.config import settings
from app.services.budget import BudgetExceededError, BudgetTracker
from app.services.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


@dataclass
class RunningProcess:
    process: Optional[asyncio.subprocess.Process]
    session_id: uuid.UUID
    workdir: str
    system_prompt: str
    claude_session_id: Optional[str] = None
    allowed_tools: list[str] = None

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = []

class TransientAgentError(Exception):
    """Временная ошибка — можно повторить (rate limit, timeout, сеть)."""
    pass

class AgentRuntimeError(Exception):
    pass


class AgentRuntime:
    """Manages long-lived claude CLI subprocesses for agent sessions."""

    def __init__(self) -> None:
        self._processes: dict[uuid.UUID, RunningProcess] = {}
        self._children: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._budget = BudgetTracker(
            default_session_limit=settings.budget_session_limit_usd,
        )
        self._breaker = CircuitBreaker(
            failure_threshold=settings.cb_failure_threshold,
            recovery_timeout=settings.cb_recovery_timeout,
            failure_window=settings.cb_failure_window,
            name="claude_cli",
        )

    async def start_session(
        self,
        session_id: uuid.UUID,
        workdir: str,
        system_prompt: str,
        claude_session_id: Optional[str] = None,
        allowed_tools: list[str] = None,
        parent_session_id: Optional[uuid.UUID] = None,
    ) -> None:
        if session_id in self._processes:
            raise AgentRuntimeError(f"Session {session_id} already running")

        # Reject if workdir is actively used by another session
        effective_workdir = workdir or settings.workspace_path
        for sid, r in self._processes.items():
            if r.workdir == effective_workdir and r.process and r.process.returncode is None:
                raise AgentRuntimeError(
                    f"Workdir {effective_workdir} already in use by session {sid}"
                )

        self._processes[session_id] = RunningProcess(
            process=None,
            session_id=session_id,
            workdir=effective_workdir,
            system_prompt=system_prompt,
            claude_session_id=claude_session_id,
            allowed_tools=allowed_tools or [],
        )
        if parent_session_id:
            self._children.setdefault(parent_session_id, set()).add(session_id)
        self._budget.start_session(str(session_id))

    async def send_message(
        self, session_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict[str, Any]]:
        running = self._processes.get(session_id)
        if not running:
            raise AgentRuntimeError(f"Session {session_id} not running")

        # Kill stale CLI process for THIS session only
        if running.process and running.process.returncode is None:
            await self._kill_process(running)

        from app.services.auth_service import get_current_access_token

        token = await get_current_access_token()
        if not token:
            raise AgentRuntimeError("Not authenticated. Please login first.")

        # Budget check: fail if session budget is exhausted
        self._budget.check_budget(str(session_id))

        # Circuit breaker: fail-fast if CLI is known to be down
        self._breaker.check()

        env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}

        cmd = self._build_command(running)
        logger.warning("CLI command: %s", " ".join(cmd))
        process = await self._launch_process(cmd, env, running.workdir)
        running.process = process

        if process.stdin:
            process.stdin.write(content.encode())
            process.stdin.write_eof()

        from app.services.telemetry import get_langfuse
        lf = get_langfuse()
        trace = lf.trace(
            name="agent.send_message",
            session_id=str(session_id),
            input=content,
        ) if lf else None
        generation = trace.generation(
            name="claude_cli",
            input=content,
        ) if trace else None

        output_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        cost_usd = None
        call_succeeded = False

        try:
            async for event in self._read_stream(session_id, process):
                if event["type"] == "assistant_text":
                    output_parts.append(event["content"])
                elif event["type"] == "result":
                    usage = event.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    cost_usd = event.get("cost_usd")
                    call_succeeded = True

                    # Record usage and emit budget events
                    budget_event = self._budget.record_usage(
                        session_id=str(session_id),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model=event.get("model"),
                        reported_cost=cost_usd,
                    )
                    if budget_event:
                        yield budget_event

                    continue  # не отправляем result на фронтенд
                yield event
        except TransientAgentError:
            self._breaker.record_failure()
            raise
        else:
            if call_succeeded:
                self._breaker.record_success()
        finally:
            output_text = "".join(output_parts)
            if generation:
                generation.end(
                    output=output_text,
                    usage={
                        "input": input_tokens,
                        "output": output_tokens,
                        "unit": "TOKENS",
                    },
                    metadata={"cost_usd": cost_usd},
                )
            if trace:
                trace.update(output=output_text)
            if lf:
                lf.flush()

    async def _kill_process(self, running: RunningProcess) -> None:
        proc = running.process
        if not proc or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass

    async def kill_active_process(self, session_id: uuid.UUID) -> None:
        """Kill the CLI process without removing the session from runtime."""
        running = self._processes.get(session_id)
        if running:
            await self._kill_process(running)

    def get_children(self, session_id: uuid.UUID) -> set[uuid.UUID]:
        """Return a copy of child session IDs (for DB cleanup before stop)."""
        return set(self._children.get(session_id, set()))

    async def stop_session(self, session_id: uuid.UUID) -> None:
        # Рекурсивно остановить все дочерние сессии
        for child_id in self._children.pop(session_id, set()):
            await self.stop_session(child_id)
        running = self._processes.pop(session_id, None)
        if running:
            await self._kill_process(running)
        self._budget.remove_session(str(session_id))
        # Удалить себя из _children родителя (при нормальном завершении sub-agent)
        for parent_children in self._children.values():
            parent_children.discard(session_id)

    async def run_task(
        self,
        workdir: str,
        system_prompt: str,
        task: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Run an ephemeral sub-agent task with an isolated CWD.

        Uses a unique subdirectory as subprocess CWD so that Claude CLI
        stores its session file there — not in the main agent's workdir.
        This prevents --continue from picking up the sub-agent's session
        when the main agent resumes.
        """
        from pathlib import Path

        temp_id = uuid.uuid4()
        isolated_dir = Path(workdir) / ".handoff_sessions" / str(temp_id)
        isolated_dir.mkdir(parents=True, exist_ok=True)

        await self.start_session(
            session_id=temp_id,
            workdir=str(isolated_dir),
            system_prompt=system_prompt,
        )
        try:
            async for event in self.send_message(temp_id, task):
                yield event
        finally:
            await self.stop_session(temp_id)

    def is_running(self, session_id: uuid.UUID) -> bool:
        return session_id in self._processes

    def get_claude_session_id(self, session_id: uuid.UUID) -> Optional[str]:
        running = self._processes.get(session_id)
        if running:
            return running.claude_session_id
        return None
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(OSError),
    )
    async def _launch_process(
        self, cmd: list[str], env: dict, cwd: str
    ) -> asyncio.subprocess.Process:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        return process

    def _build_command(self, running: RunningProcess) -> list[str]:
        cmd = [
            settings.claude_cli_path,
            "-p",
            "--output-format", "stream-json",
            "--verbose",
        ]

        if running.system_prompt:
            cmd.extend(["--system-prompt", running.system_prompt])

        if running.claude_session_id:
            # --continue picks up the last session in the project dir;
            # --session-id can NOT be reused (CLI rejects existing session files)
            cmd.append("--continue")
        else:
            # Fresh session with unique ID
            cmd.extend(["--session-id", str(uuid.uuid4())])

        if running.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(running.allowed_tools)])

        return cmd

    async def _read_stream(
        self,
        session_id: uuid.UUID,
        process: asyncio.subprocess.Process,
    ) -> AsyncIterator[dict[str, Any]]:
        if not process.stdout:
            return
        
        stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None

        try:
            async for line in process.stdout:
                text = line.decode().strip()
                if not text:
                    continue

                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON line from claude: %s", text)
                    continue

                parsed = self._parse_event(session_id, event)
                if parsed:
                    yield parsed

            try:
                await asyncio.wait_for(process.wait(), timeout=300)
            except asyncio.TimeoutError:
                logger.error("CLI process did not exit within 300s, killing")
                process.kill()
                await process.wait()

            if stderr_task:
                stderr = await stderr_task
                error_text = stderr.decode().strip()
                if error_text:
                    if process.returncode != 0:
                        logger.error("Claude CLI error (rc=%s): %s", process.returncode, error_text)
                        error_lower = error_text.lower()
                        if any(word in error_lower for word in ["rate limit", "timeout", "connection"]):
                            raise TransientAgentError(error_text)
                        yield {"type": "error", "error": error_text}
                    else:
                        logger.info("Claude CLI stderr: %s", error_text[:500])
        finally:
            if stderr_task and not stderr_task.done():
                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass

    def _parse_event(
        self, session_id: uuid.UUID, event: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        event_type = event.get("type")

        if event_type == "system" and "session_id" in event:
            running = self._processes.get(session_id)
            if running:
                running.claude_session_id = event["session_id"]
            return None

        if event_type == "assistant":
            message = event.get("message")
            if isinstance(message, dict):
                for block in message.get("content", []):
                    if block.get("type") == "text":
                        return {"type": "assistant_text", "content": block.get("text", "")}
            subtype = event.get("subtype")
            if subtype == "text":
                return {"type": "assistant_text", "content": event.get("text", "")}
            return None

        if event_type == "tool_use":
            return {
                "type": "tool_use",
                "tool_name": event.get("tool", ""),
                "tool_input": event.get("input", {}),
            }

        if event_type == "result":
            return {
                "type": "result",
                "cost_usd": event.get("cost_usd"),
                "usage": event.get("usage", {}),
                "model": event.get("model"),
            }

        if event_type == "tool_result":
            content = event.get("output", event.get("content", ""))
            return {"type": "tool_result", "content": str(content)}

        return None


runtime = AgentRuntime()
