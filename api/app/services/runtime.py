from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RunningProcess:
    process: asyncio.subprocess.Process
    session_id: uuid.UUID
    claude_session_id: str | None = None


class RuntimeError_(Exception):
    pass


class AgentRuntime:
    """Manages claude CLI subprocesses for agent sessions."""

    def __init__(self) -> None:
        self._processes: dict[uuid.UUID, RunningProcess] = {}

    async def start_session(
        self,
        session_id: uuid.UUID,
        workdir: str,
        system_prompt: str,
        claude_session_id: str | None = None,
    ) -> None:
        if session_id in self._processes:
            raise RuntimeError_(f"Session {session_id} already running")

        self._processes[session_id] = RunningProcess(
            process=None,  # type: ignore[arg-type]
            session_id=session_id,
            claude_session_id=claude_session_id,
        )

    async def send_message(
        self, session_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict[str, Any]]:
        cmd = self._build_command(session_id)
        running = self._processes.get(session_id)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._get_workdir(session_id),
        )

        if running:
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

    def _build_command(self, session_id: uuid.UUID) -> list[str]:
        running = self._processes.get(session_id)
        cmd = [
            settings.claude_cli_path,
            "--output-format", "stream-json",
            "--verbose",
        ]

        if running and running.claude_session_id:
            cmd.extend(["--session-id", running.claude_session_id])
            cmd.append("--resume")

        return cmd

    def _get_workdir(self, session_id: uuid.UUID) -> str:
        return settings.workspace_path

    def _update_claude_session_id(
        self, session_id: uuid.UUID, claude_session_id: str
    ) -> None:
        running = self._processes.get(session_id)
        if running:
            running.claude_session_id = claude_session_id

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
    ) -> dict[str, Any] | None:
        event_type = event.get("type")

        if event_type == "system" and "session_id" in event:
            self._update_claude_session_id(session_id, event["session_id"])
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
