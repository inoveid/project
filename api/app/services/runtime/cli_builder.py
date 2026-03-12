from __future__ import annotations

import uuid

from app.config import settings

from .process_manager import RunningProcess


def build_command(running: RunningProcess) -> list[str]:
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

    if running.workdir:
        cmd.extend(["--directory", running.workdir])

    if running.allowed_tools:
        cmd.extend(["--allowedTools", ",".join(running.allowed_tools)])

    return cmd
