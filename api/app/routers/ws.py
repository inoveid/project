import json
import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()

    try:
        session = await get_session(db, session_id)
    except SessionNotFoundError:
        await websocket.send_json({"type": "error", "error": "Session not found"})
        await websocket.close(code=4004)
        return

    agent = session.agent
    if not runtime.is_running(session_id):
        await runtime.start_session(
            session_id=session_id,
            workdir=agent.config.get("workdir", "") if agent.config else "",
            system_prompt=agent.system_prompt,
            claude_session_id=session.claude_session_id,
        )

    try:
        await _handle_messages(websocket, db, session_id, agent)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)


async def _handle_messages(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    agent: object,
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
            await _stream_response(websocket, db, session_id, content)
            continue

        await websocket.send_json({"type": "error", "error": f"Unknown type: {msg_type}"})


async def _stream_response(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    content: str,
) -> None:
    full_text = ""
    tool_uses: list[dict] = []

    async for event in runtime.send_message(session_id, content):
        event_type = event.get("type")

        if event_type == "assistant_text":
            full_text += event.get("content", "")

        if event_type == "tool_use":
            tool_uses.append({
                "tool_name": event.get("tool_name", ""),
                "tool_input": event.get("tool_input", {}),
            })

        await websocket.send_json(event)

    if full_text or tool_uses:
        await add_message(
            db,
            session_id,
            "assistant",
            full_text,
            tool_uses=tool_uses if tool_uses else None,
        )

    running = runtime._processes.get(session_id)
    if running and running.claude_session_id:
        session = await get_session(db, session_id)
        session.claude_session_id = running.claude_session_id
        await db.commit()

    await websocket.send_json({"type": "done"})
