from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RunningProcess:
    process: Optional[asyncio.subprocess.Process]
    session_id: uuid.UUID
    workdir: str
    system_prompt: str
    claude_session_id: Optional[str] = None


class AgentRuntimeError(Exception):
    pass


class AgentRuntime:
    """Manages long-lived claude CLI subprocesses for agent sessions."""

    def __init__(self) -> None:
        self._processes: dict[uuid.UUID, RunningProcess] = {}

    async def start_session(
        self,
        session_id: uuid.UUID,
        workdir: str,
        system_prompt: str,
        claude_session_id: Optional[str] = None,
    ) -> None:
        if session_id in self._processes:
            raise AgentRuntimeError(f"Session {session_id} already running")

        self._processes[session_id] = RunningProcess(
            process=None,
            session_id=session_id,
            workdir=workdir or settings.workspace_path,
            system_prompt=system_prompt,
            claude_session_id=claude_session_id,
        )

    async def send_message(
        self, session_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict[str, Any]]:
        running = self._processes.get(session_id)
        if not running:
            raise AgentRuntimeError(f"Session {session_id} not running")

        # Kill ALL stale CLI processes (any session may lock the workdir)
        for r in self._processes.values():
            await self._kill_process(r)

        from app.services.auth_service import get_current_access_token

        token = await get_current_access_token()
        if not token:
            raise AgentRuntimeError("Not authenticated. Please login first.")

        env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": token}

        cmd = self._build_command(running)
        logger.warning("CLI command: %s", " ".join(cmd))
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=running.workdir,
            env=env,
        )
        running.process = process

        if process.stdin:
            process.stdin.write(content.encode())
            process.stdin.write_eof()

        async for event in self._read_stream(session_id, process):
            yield event

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

    async def stop_session(self, session_id: uuid.UUID) -> None:
        running = self._processes.pop(session_id, None)
        if running:
            await self._kill_process(running)

    def is_running(self, session_id: uuid.UUID) -> bool:
        return session_id in self._processes

    def get_claude_session_id(self, session_id: uuid.UUID) -> Optional[str]:
        running = self._processes.get(session_id)
        if running:
            return running.claude_session_id
        return None

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

        return cmd

    async def _read_stream(
        self,
        session_id: uuid.UUID,
        process: asyncio.subprocess.Process,
    ) -> AsyncIterator[dict[str, Any]]:
        if not process.stdout:
            return

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

        await process.wait()

        if process.stderr:
            stderr = await process.stderr.read()
            error_text = stderr.decode().strip()
            if error_text:
                if process.returncode != 0:
                    logger.error("Claude CLI error (rc=%s): %s", process.returncode, error_text)
                    yield {"type": "error", "error": error_text}
                else:
                    logger.info("Claude CLI stderr: %s", error_text[:500])

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
            return None

        if event_type == "tool_result":
            content = event.get("output", event.get("content", ""))
            return {"type": "tool_result", "content": str(content)}

        return None


runtime = AgentRuntime()
