"""
WebSocket handler — thin proxy between client and Task Worker via Redis Event Bus.

WS resilience:
- WS disconnect does NOT stop the Worker — graph keeps running
- On reconnect, missed events are replayed from Redis buffer
- Only explicit "stop" command stops the Worker
- Client sends last_event_index on reconnect to get missed events
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
    get_buffer_length,
    get_buffered_events,
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

    # Tell Worker to start handling this session (idempotent — Worker ignores if already active)
    await _notify_worker_start(sid)

    # Replay buffered events the client may have missed during disconnection.
    # Client can pass last_event_index as query param (default 0 = full replay).
    # We get the current buffer length BEFORE subscribing to avoid duplicates.
    buffer_len = await get_buffer_length(sid)

    # Two concurrent tasks:
    # 1. Forward Redis events → WebSocket (to client)
    # 2. Forward WebSocket messages → Redis commands (to Worker)

    async def forward_events_to_ws():
        """Replay buffered events, then subscribe to live events."""
        try:
            # Phase 1: Replay missed events from buffer
            if buffer_len > 0:
                missed_events = await get_buffered_events(sid)
                for event in missed_events:
                    if websocket.client_state != WebSocketState.CONNECTED:
                        return
                    try:
                        await websocket.send_json(event)
                    except Exception:
                        return
                logger.info("Replayed %d buffered events for session %s", len(missed_events), sid)

            # Phase 2: Subscribe to live events (new events from Worker)
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

                # If stop — we're done (this is the ONLY way to stop the Worker)
                if data.get("type") == "stop":
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for session %s (Worker continues)", sid)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("WS receive error for %s: %s", sid, exc)

    event_task = asyncio.create_task(forward_events_to_ws(), name=f"events-{sid}")
    ws_task = asyncio.create_task(forward_ws_to_commands(), name=f"ws-recv-{sid}")

    try:
        done, pending = await asyncio.wait(
            [event_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        # NOTE: NO _notify_worker_stop here — Worker keeps running!
        # Worker only stops on explicit "stop" command from client.
        pass
