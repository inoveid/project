"""
WebSocket handler — thin proxy between client and Task Worker via Redis Event Bus.

WS resilience:
- WS disconnect does NOT stop the Worker — graph keeps running
- On reconnect, missed events are replayed from Redis buffer
- Only explicit "stop" command stops the Worker
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

    # Worker is started by backend (update_task_status / _handle_peer_handoff).
    # WS is a pure proxy — no worker management here.

    # Two concurrent tasks:
    # 1. Forward Redis events → WebSocket (to client)
    # 2. Forward WebSocket messages → Redis commands (to Worker)

    async def forward_events_to_ws():
        """
        Subscribe to live events FIRST, then replay buffer.
        
        This avoids the race condition where events published between
        buffer read and subscribe would be lost.
        
        Flow:
        1. Subscribe to pub/sub channel (captures all new events from this moment)
        2. Read buffer snapshot (events before subscription)
        3. Send buffer events to client (replay)
        4. Forward live events from subscription
        """
        r = get_redis()
        pubsub = r.pubsub()
        channel = f"session:{sid}:events"
        await pubsub.subscribe(channel)

        try:
            # Replay buffered events while subscribed (no gap possible)
            buffered = await get_buffered_events(sid)
            for event in buffered:
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                try:
                    await websocket.send_json(event)
                except Exception:
                    return
            if buffered:
                logger.info("Replayed %d buffered events for session %s", len(buffered), sid)

            # Now forward live events
            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                try:
                    event = json.loads(raw_message["data"])
                    await websocket.send_json(event)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Event forwarding error for %s: %s", sid, exc)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

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

                await publish_command(sid, data)

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
        pass
