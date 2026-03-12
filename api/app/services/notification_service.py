"""
Notification service — Redis pub/sub for broadcasting notifications.

Replaces the in-memory NotificationBroker with Redis-based pub/sub.
All notifications are published via event_bus.publish_notification().
Subscribers (notification WS clients) receive events via event_bus.subscribe_notifications().
"""
from __future__ import annotations

from typing import Any

from app.services.event_bus import publish_notification


async def broadcast_notification(event_type: str, data: dict[str, Any]) -> None:
    """Convenience wrapper — broadcasts a notification via Redis pub/sub."""
    await publish_notification(event_type, data)
