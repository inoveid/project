from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TransientAgentError(Exception):
    """Временная ошибка — можно повторить (rate limit, timeout, сеть)."""
    pass


def parse_event(
    event: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Parse a single Claude CLI JSON event into an internal event dict.

    Pure function — no side effects.  For "system" events carrying a
    claude session id the caller is responsible for updating RunningProcess.
    """
    event_type = event.get("type")

    if event_type == "system" and "session_id" in event:
        return {"type": "system_session_id", "session_id": event["session_id"]}

    if event_type == "assistant":
        # Final message with content blocks is handled in read_stream
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


async def read_stream(
    process: asyncio.subprocess.Process,
) -> AsyncIterator[dict[str, Any]]:
    """Read stdout of a Claude CLI process and yield parsed events.

    Pure async generator — no access to AgentRuntime state.
    Yields ``system_session_id`` events that the caller must handle.
    """
    if not process.stdout:
        return

    stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
    had_streaming_text = False

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

            # Final assistant message with content blocks (BUG-1 + BUG-2):
            # Iterate all blocks, yield tool_use/tool_result individually,
            # skip text if streaming chunks already sent it.
            if event.get("type") == "assistant" and isinstance(event.get("message"), dict):
                for block in event["message"].get("content", []):
                    block_type = block.get("type")
                    if block_type == "text" and not had_streaming_text:
                        yield {"type": "assistant_text", "content": block.get("text", "")}
                    elif block_type == "tool_use":
                        yield {
                            "type": "tool_use",
                            "tool_name": block.get("name", ""),
                            "tool_input": block.get("input", {}),
                        }
                    elif block_type == "tool_result":
                        yield {"type": "tool_result", "content": str(block.get("content", ""))}
                continue

            parsed = parse_event(event)
            if parsed:
                if parsed["type"] == "assistant_text":
                    had_streaming_text = True
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
