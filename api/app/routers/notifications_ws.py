"""
WebSocket endpoint for global notifications via Redis pub/sub.

Clients connect at /api/ws/notifications and receive broadcast events:
- approval_required
- max_cycles_reached
- task_completed
- task_error
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.services.event_bus import subscribe_notifications

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/notifications")
async def notifications_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Notification subscriber connected")

    async def forward_notifications():
        """Subscribe to Redis notifications and forward to WebSocket."""
        try:
            async for event in subscribe_notifications():
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                try:
                    await websocket.send_json(event)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def keep_alive():
        """Wait for client disconnect."""
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass

    notify_task = asyncio.create_task(forward_notifications())
    alive_task = asyncio.create_task(keep_alive())

    try:
        done, pending = await asyncio.wait(
            [notify_task, alive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        logger.info("Notification subscriber disconnected")
