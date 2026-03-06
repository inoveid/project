from __future__ import annotations

import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.agent import Agent
from app.services.agent_link_service import get_agent_handoff_targets
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_HANDOFF_HOPS = 5


@router.websocket("/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await websocket.accept()

    try:
        session = await get_session(db, session_id)
    except SessionNotFoundError:
        await websocket.send_json({"type": "error", "error": "Session not found"})
        await websocket.close(code=4004)
        return

    agent = session.agent

    handoff_targets = await get_agent_handoff_targets(db, agent.id)
    system_prompt = agent.system_prompt
    if handoff_targets:
        system_prompt = system_prompt + _format_handoff_instructions(handoff_targets)

    if not runtime.is_running(session_id):
        try:
            await runtime.start_session(
                session_id=session_id,
                workdir=agent.config.get("workdir", "") if agent.config else "",
                system_prompt=system_prompt,
                claude_session_id=session.claude_session_id,
            )
        except Exception as exc:
            await websocket.send_json({"type": "error", "error": str(exc)})
            await websocket.close(code=4000)
            return

    try:
        await _handle_messages(websocket, db, session_id, agent, handoff_targets)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
        await runtime.kill_active_process(session_id)


def _format_handoff_instructions(targets: list[Agent]) -> str:
    lines = ["\n\n## Available Handoff Targets"]
    lines.append("You can delegate tasks to the following agents:")
    for a in targets:
        desc = f" — {a.description}" if a.description else ""
        lines.append(f"- **{a.name}** ({a.role}){desc}")
    lines.append("\nTo hand off, include at the END of your response:")
    lines.append('```handoff\n{"to": "<agent name>", "message": "<full context>"}\n```')
    lines.append("Only hand off when you have completed your part of the task.")
    return "\n".join(lines)


async def _handle_messages(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    agent: Agent,
    handoff_targets: list[Agent],
) -> None:
    while True:
        raw = await websocket.receive_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "error": "Invalid JSON"})
            continue

        msg_type = data.get("type")

        if msg_type == "stop":
            await runtime.stop_session(session_id)
            await websocket.send_json({"type": "done"})
            break

        if msg_type == "message":
            content = data.get("content", "")
            if not content:
                await websocket.send_json(
                    {"type": "error", "error": "Empty message content"}
                )
                continue

            await add_message(db, session_id, "user", content)
            await _stream_response(
                websocket, db, session_id, content, agent, handoff_targets,
            )
            continue

        await websocket.send_json({"type": "error", "error": f"Unknown type: {msg_type}"})


def _parse_handoff_block(text: str) -> dict | None:
    """Parse ```handoff {...} ``` block from end of agent response."""
    match = re.search(r'```handoff\s*\n([\s\S]*?)\n```', text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
        if isinstance(data.get("to"), str) and isinstance(data.get("message"), str):
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _build_sub_agent_prompt(
    agent: Agent,
    chain: list[tuple[str, str]],
    sub_targets: list[Agent],
) -> str:
    prompt = agent.system_prompt
    if chain:
        history = " → ".join(f"{a}→{b}" for a, b in chain)
        prompt += f"\n\n## Handoff Chain Context\nChain so far: {history} → {agent.name} (you)"
    workdir = agent.config.get("workdir") if agent.config else None
    if workdir:
        prompt += f"\nWorking directory: {workdir}"
    if sub_targets:
        prompt += _format_handoff_instructions(sub_targets)
    return prompt


async def _stream_response(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    content: str,
    agent: Agent,
    handoff_targets: list[Agent],
    chain: list[tuple[str, str]] | None = None,
) -> None:
    full_text = ""
    tool_uses: list[dict] = []
    stream = runtime.send_message(session_id, content)

    try:
        async for event in stream:
            event_type = event.get("type")

            if event_type == "assistant_text":
                full_text += event.get("content", "")

            if event_type == "tool_use":
                tool_uses.append({
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input", {}),
                })

            await websocket.send_json(event)
    except WebSocketDisconnect:
        await stream.aclose()
        raise
    except Exception as exc:
        logger.error("Error streaming agent response for session %s: %s", session_id, exc)
        await websocket.send_json({"type": "error", "error": str(exc)})
        await websocket.send_json({"type": "done"})
        return

    if full_text or tool_uses:
        await add_message(
            db,
            session_id,
            "assistant",
            full_text,
            tool_uses=tool_uses if tool_uses else None,
        )

    try:
        claude_sid = runtime.get_claude_session_id(session_id)
        if claude_sid:
            session = await get_session(db, session_id)
            session.claude_session_id = claude_sid
            await db.commit()
    except SessionNotFoundError:
        logger.warning("Session %s deleted during streaming", session_id)

    if full_text:
        await _run_handoff_chain(
            websocket=websocket,
            db=db,
            main_session_id=session_id,
            main_agent=agent,
            response_text=full_text,
            handoff_targets=handoff_targets,
            chain=chain or [],
            depth=0,
        )

    await websocket.send_json({"type": "done"})


async def _run_handoff_chain(
    websocket: WebSocket,
    db: AsyncSession,
    main_session_id: uuid.UUID,
    main_agent: Agent,
    response_text: str,
    handoff_targets: list[Agent],
    chain: list[tuple[str, str]],
    depth: int,
) -> None:
    if depth >= MAX_HANDOFF_HOPS:
        logger.warning("Max handoff depth %d reached", MAX_HANDOFF_HOPS)
        return

    block = _parse_handoff_block(response_text)
    if not block:
        return

    target_name = block["to"]
    task_message = block["message"]
    target = next((a for a in handoff_targets if a.name == target_name), None)
    if not target:
        logger.warning("Handoff target '%s' not found in links", target_name)
        return

    current_pair = (main_agent.name, target.name)
    if chain.count(current_pair) >= 1:
        await websocket.send_json({
            "type": "handoff_cycle_detected",
            "message": f"Cycle detected: {main_agent.name} → {target.name}",
        })
        return

    await websocket.send_json({
        "type": "handoff_start",
        "from_agent": main_agent.name,
        "to_agent": target.name,
        "task": task_message,
    })

    sub_targets = await get_agent_handoff_targets(db, target.id)
    sub_prompt = _build_sub_agent_prompt(target, chain + [current_pair], sub_targets)

    sub_text = ""
    sub_tools: list[dict] = []
    workdir = (
        (target.config.get("workdir") or settings.workspace_path)
        if target.config
        else settings.workspace_path
    )

    try:
        async for event in runtime.run_task(
            workdir=workdir, system_prompt=sub_prompt, task=task_message,
        ):
            ev_type = event.get("type")
            if ev_type == "assistant_text":
                sub_text += event.get("content", "")
            if ev_type == "tool_use":
                sub_tools.append({
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input", {}),
                })
            await websocket.send_json({
                **event, "type": f"sub_agent_{ev_type}", "agent_name": target.name,
            })
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        logger.error("Sub-agent %s error: %s", target.name, exc)
        await websocket.send_json({
            "type": "sub_agent_error", "agent_name": target.name, "error": str(exc),
        })

    await websocket.send_json({"type": "handoff_done", "agent_name": target.name})

    if sub_text or sub_tools:
        await add_message(
            db, main_session_id, "assistant",
            f"[{target.name}]: {sub_text}",
            tool_uses=sub_tools or None,
        )

    if sub_text and sub_targets:
        await _run_handoff_chain(
            websocket, db, main_session_id, target, sub_text,
            sub_targets, chain + [current_pair], depth + 1,
        )

    if sub_text:
        result_msg = f"Sub-agent {target.name} completed:\n{sub_text}"
        await _stream_response(
            websocket, db, main_session_id,
            result_msg, main_agent, handoff_targets,
            chain + [current_pair],
        )
