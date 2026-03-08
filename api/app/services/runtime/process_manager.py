from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


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


async def kill_process(running: RunningProcess) -> None:
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OSError),
)
async def launch_process(
    cmd: list[str], env: dict, cwd: str
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
