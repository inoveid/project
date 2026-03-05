from __future__ import annotations

import asyncio
import json
import logging
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

        cmd = self._build_command(running)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=running.workdir,
        )
        running.process = process

        if process.stdin:
            process.stdin.write(content.encode())
            process.stdin.write_eof()

        async for event in self._read_stream(session_id, process):
            yield event

    async def stop_session(self, session_id: uuid.UUID) -> None:
        running = self._processes.pop(session_id, None)
        if running and running.process and running.process.returncode is None:
            try:
                running.process.terminate()
                await asyncio.wait_for(running.process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                running.process.kill()

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
            cmd.extend(["--session-id", running.claude_session_id])
            cmd.append("--resume")

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

        if process.returncode != 0 and process.stderr:
            stderr = await process.stderr.read()
            error_text = stderr.decode().strip()
            if error_text:
                logger.error("Claude CLI error: %s", error_text)
                yield {"type": "error", "error": error_text}

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

        if event_type == "tool_result" or event_type == "result":
            content = event.get("output", event.get("content", ""))
            return {"type": "tool_result", "content": str(content)}

        return None


runtime = AgentRuntime()
