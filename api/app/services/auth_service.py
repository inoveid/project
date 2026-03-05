from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from app.config import settings
from app.schemas.auth import AuthStatusRead

logger = logging.getLogger(__name__)

_login_process: Optional[asyncio.subprocess.Process] = None

URL_PATTERN = re.compile(r"https://\S+")


class AuthCheckError(Exception):
    pass


class AuthLoginError(Exception):
    pass


async def get_auth_status() -> AuthStatusRead:
    try:
        process = await asyncio.create_subprocess_exec(
            settings.claude_cli_path, "auth", "status", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
    except (OSError, asyncio.TimeoutError) as exc:
        raise AuthCheckError(f"Failed to run claude auth status: {exc}")

    raw = stdout.decode().strip() if stdout else ""
    if not raw and process.returncode != 0:
        error_text = stderr.decode().strip() if stderr else "unknown error"
        raise AuthCheckError(f"claude auth status failed: {error_text}")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuthCheckError(f"Invalid JSON from claude auth status: {exc}")

    return AuthStatusRead(
        logged_in=data.get("loggedIn", False),
        email=data.get("email"),
        org_name=data.get("orgName"),
        subscription_type=data.get("subscriptionType"),
        auth_method=data.get("authMethod"),
    )


async def _kill_login_process() -> None:
    global _login_process
    if _login_process is not None and _login_process.returncode is None:
        try:
            _login_process.terminate()
            await asyncio.wait_for(_login_process.wait(), timeout=3.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            _login_process.kill()
    _login_process = None


async def _read_stream_for_url(
    stream: asyncio.StreamReader,
) -> tuple[str, Optional[str]]:
    """Read lines from stream, return (collected_text, url_or_none)."""
    collected = ""
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode()
        collected += text
        match = URL_PATTERN.search(text)
        if match:
            return collected, match.group(0)
    return collected, None


async def start_auth_login() -> str:
    global _login_process

    await _kill_login_process()

    try:
        _login_process = await asyncio.create_subprocess_exec(
            settings.claude_cli_path, "auth", "login",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise AuthLoginError(f"Failed to run claude auth login: {exc}")

    async def _scan_streams() -> str:
        tasks = []
        if _login_process.stdout:
            tasks.append(asyncio.ensure_future(
                _read_stream_for_url(_login_process.stdout)
            ))
        if _login_process.stderr:
            tasks.append(asyncio.ensure_future(
                _read_stream_for_url(_login_process.stderr)
            ))

        collected = ""
        for coro in asyncio.as_completed(tasks):
            text, url = await coro
            collected += text
            if url:
                for t in tasks:
                    t.cancel()
                return url

        raise AuthLoginError(
            f"OAuth URL not found in claude auth login output. "
            f"Collected: {collected[:200]}"
        )

    try:
        return await asyncio.wait_for(_scan_streams(), timeout=15.0)
    except asyncio.TimeoutError:
        raise AuthLoginError("Timed out waiting for OAuth URL from claude auth login")


async def submit_auth_code(code: str) -> None:
    if _login_process is None or _login_process.returncode is not None:
        raise AuthLoginError("No active login process")
    if _login_process.stdin is None:
        raise AuthLoginError("Login process has no stdin pipe")
    _login_process.stdin.write((code + "\n").encode())
    await _login_process.stdin.drain()
    _login_process.stdin.close()


async def auth_logout() -> None:
    try:
        process = await asyncio.create_subprocess_exec(
            settings.claude_cli_path, "auth", "logout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=15.0)
    except (OSError, asyncio.TimeoutError) as exc:
        raise AuthCheckError(f"Failed to run claude auth logout: {exc}")
