"""
In-memory pub/sub for broadcasting notifications to connected WebSocket clients.

MVP implementation — single server, no Redis. Sufficient for development
and small deployments. Replace with Redis pub/sub for horizontal scaling.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class NotificationBroker:
    """Manages WebSocket subscribers and broadcasts notification events."""

    def __init__(self) -> None:
        self._subscribers: list[WebSocket] = []

    def subscribe(self, ws: WebSocket) -> None:
        self._subscribers.append(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        try:
            self._subscribers.remove(ws)
        except ValueError:
            pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Send a notification event to all connected clients."""
        message = {"type": event_type, **data}
        disconnected: list[WebSocket] = []

        for ws in list(self._subscribers):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    disconnected.append(ws)
            except Exception:
                logger.debug("Failed to send notification to subscriber, removing")
                disconnected.append(ws)

        for ws in disconnected:
            self.unsubscribe(ws)


# Module-level singleton
notification_broker = NotificationBroker()


async def broadcast_notification(event_type: str, data: dict[str, Any]) -> None:
    """Convenience wrapper for broadcasting a notification event."""
    await notification_broker.broadcast(event_type, data)
