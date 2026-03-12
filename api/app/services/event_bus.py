"""
Event Bus — Redis-based pub/sub for session events and commands.

Channels:
  session:{session_id}:events  — Worker publishes graph events (assistant_text, tool_use, done, etc.)
  session:{session_id}:commands — WS handler publishes commands (message, approve, reject, stop)
  notifications                — broadcast notifications (approval_required, task_completed, etc.)

All messages are JSON-encoded dicts with a "type" field.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis

from app.services.redis_service import get_redis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel helpers
# ---------------------------------------------------------------------------

def _events_channel(session_id: str) -> str:
    return f"session:{session_id}:events"


def _commands_channel(session_id: str) -> str:
    return f"session:{session_id}:commands"


NOTIFICATIONS_CHANNEL = "notifications"


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

async def publish_event(session_id: str, event: dict[str, Any]) -> None:
    """Publish a session event from Worker → WS handler."""
    r = get_redis()
    await r.publish(_events_channel(session_id), json.dumps(event))


async def publish_command(session_id: str, command: dict[str, Any]) -> None:
    """Publish a command from WS handler → Worker."""
    r = get_redis()
    await r.publish(_commands_channel(session_id), json.dumps(command))


async def publish_notification(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast a notification to all subscribers (dashboard toasts, etc.)."""
    r = get_redis()
    message = {"type": event_type, **data}
    await r.publish(NOTIFICATIONS_CHANNEL, json.dumps(message))


# ---------------------------------------------------------------------------
# Subscribing
# ---------------------------------------------------------------------------

async def subscribe_events(session_id: str) -> AsyncIterator[dict[str, Any]]:
    """
    Subscribe to session events. Yields dicts as they arrive.
    Caller should wrap in try/finally and break on "done" or "error".
    """
    r = get_redis()
    pubsub = r.pubsub()
    channel = _events_channel(session_id)
    await pubsub.subscribe(channel)
    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] != "message":
                continue
            try:
                event = json.loads(raw_message["data"])
                yield event
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid event JSON on %s", channel)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def subscribe_commands(session_id: str) -> AsyncIterator[dict[str, Any]]:
    """
    Subscribe to session commands. Used by Worker to receive messages/approve/reject/stop.
    """
    r = get_redis()
    pubsub = r.pubsub()
    channel = _commands_channel(session_id)
    await pubsub.subscribe(channel)
    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] != "message":
                continue
            try:
                command = json.loads(raw_message["data"])
                yield command
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid command JSON on %s", channel)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def subscribe_notifications() -> AsyncIterator[dict[str, Any]]:
    """Subscribe to broadcast notifications. Used by notification WS handler."""
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(NOTIFICATIONS_CHANNEL)
    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] != "message":
                continue
            try:
                event = json.loads(raw_message["data"])
                yield event
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid notification JSON")
    finally:
        await pubsub.unsubscribe(NOTIFICATIONS_CHANNEL)
        await pubsub.aclose()
