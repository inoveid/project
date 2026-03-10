"""
WebSocket endpoint for global notifications.

Clients connect at /api/ws/notifications and receive broadcast events:
- approval_required
- max_cycles_reached
- task_completed
- task_error
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.notification_service import notification_broker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/notifications")
async def notifications_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    notification_broker.subscribe(websocket)
    logger.info(
        "Notification subscriber connected (total: %d)",
        notification_broker.subscriber_count,
    )

    try:
        # Keep the connection alive — wait for client disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        notification_broker.unsubscribe(websocket)
        logger.info(
            "Notification subscriber disconnected (total: %d)",
            notification_broker.subscriber_count,
        )
