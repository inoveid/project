"""
WebSocket handler — thin proxy between client and Task Worker via Redis Event Bus.

Flow:
1. Client connects via WebSocket
2. WS handler notifies Worker to start session (Redis: worker:sessions)
3. Client sends message/approve/reject/stop → published to Redis commands channel
4. Worker processes and publishes events → WS handler subscribes and forwards to client

No graph execution happens here — all graph logic is in worker.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.database import get_db
from app.services.event_bus import (
    publish_command,
    subscribe_events,
)
from app.services.redis_service import get_redis
from app.services.session_service import (
    SessionNotFoundError,
    get_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _notify_worker_start(session_id: str) -> None:
    """Tell the Worker to start handling this session."""
    r = get_redis()
    await r.publish("worker:sessions", json.dumps({
        "action": "start",
        "session_id": session_id,
    }))


async def _notify_worker_stop(session_id: str) -> None:
    """Tell the Worker to stop handling this session."""
    r = get_redis()
    await r.publish("worker:sessions", json.dumps({
        "action": "stop",
        "session_id": session_id,
    }))


@router.websocket("/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await websocket.accept()

    # Validate session exists
    try:
        session = await get_session(db, session_id)
    except SessionNotFoundError:
        await websocket.send_json({"type": "error", "error": "Session not found"})
        await websocket.close(code=4004)
        return

    sid = str(session_id)

    # Tell Worker to start handling this session
    await _notify_worker_start(sid)

    # Two concurrent tasks:
    # 1. Forward Redis events → WebSocket (to client)
    # 2. Forward WebSocket messages → Redis commands (to Worker)

    async def forward_events_to_ws():
        """Subscribe to Worker events and forward to WebSocket client."""
        try:
            async for event in subscribe_events(sid):
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                try:
                    await websocket.send_json(event)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Event forwarding error for %s: %s", sid, exc)

    async def forward_ws_to_commands():
        """Receive WebSocket messages and publish as Redis commands."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "Invalid JSON"})
                    continue

                # Forward command to Worker via Redis
                await publish_command(sid, data)

                # If stop — we're done
                if data.get("type") == "stop":
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for session %s", sid)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("WS receive error for %s: %s", sid, exc)

    # Run both tasks concurrently
    event_task = asyncio.create_task(forward_events_to_ws(), name=f"events-{sid}")
    ws_task = asyncio.create_task(forward_ws_to_commands(), name=f"ws-recv-{sid}")

    try:
        # Wait for either task to complete (WS disconnect or stop command)
        done, pending = await asyncio.wait(
            [event_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancel the other task
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        # Notify worker that WS disconnected (it can decide to keep running or stop)
        await _notify_worker_stop(sid)
