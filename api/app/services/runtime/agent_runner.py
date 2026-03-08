from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any, Optional

from app.config import settings
from app.services.budget import BudgetTracker
from app.services.circuit_breaker import CircuitBreaker
from .cli_builder import build_command
from .event_parser import TransientAgentError, read_stream
from .process_manager import RunningProcess, kill_process, launch_process

logger = logging.getLogger(__name__)


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
            await kill_process(running)

        from app.services.auth_service import get_current_access_token

        token = await get_current_access_token()
        if not token:
            raise AgentRuntimeError("Not authenticated. Please login first.")

        # Budget check: fail if session budget is exhausted
        self._budget.check_budget(str(session_id))

        # Circuit breaker: fail-fast if CLI is known to be down
        self._breaker.check()

        env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}

        cmd = build_command(running)
        logger.warning("CLI command: %s", " ".join(cmd))
        process = await launch_process(cmd, env, running.workdir)
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
            async for event in read_stream(process):
                etype = event["type"]

                # Handle session id update from CLI system event
                if etype == "system_session_id":
                    running.claude_session_id = event["session_id"]
                    continue

                if etype == "assistant_text":
                    output_parts.append(event["content"])
                elif etype == "result":
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

                    continue  # don't forward result to frontend
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

    async def kill_active_process(self, session_id: uuid.UUID) -> None:
        """Kill the CLI process without removing the session from runtime."""
        running = self._processes.get(session_id)
        if running:
            await kill_process(running)

    def get_children(self, session_id: uuid.UUID) -> set[uuid.UUID]:
        """Return a copy of child session IDs (for DB cleanup before stop)."""
        return set(self._children.get(session_id, set()))

    async def stop_session(self, session_id: uuid.UUID) -> None:
        # Рекурсивно остановить все дочерние сессии
        for child_id in self._children.pop(session_id, set()):
            await self.stop_session(child_id)
        running = self._processes.pop(session_id, None)
        if running:
            await kill_process(running)
        self._budget.remove_session(str(session_id))
        # Удалить себя из _children родителя (при нормальном завершении sub-agent)
        for parent_children in self._children.values():
            parent_children.discard(session_id)

    def is_running(self, session_id: uuid.UUID) -> bool:
        return session_id in self._processes

    def get_claude_session_id(self, session_id: uuid.UUID) -> Optional[str]:
        running = self._processes.get(session_id)
        if running:
            return running.claude_session_id
        return None


runtime = AgentRuntime()
