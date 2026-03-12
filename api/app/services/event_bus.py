"""
Event Bus — Redis-based pub/sub for session events and commands.

Channels:
  session:{session_id}:events  — Worker publishes graph events (pub/sub, real-time)
  session:{session_id}:commands — WS handler publishes commands (pub/sub)
  notifications                — broadcast notifications (pub/sub)

Buffers:
  session:{session_id}:buffer  — Recent events stored in Redis list for WS reconnection replay.
                                  Capped at EVENT_BUFFER_SIZE, TTL = EVENT_BUFFER_TTL seconds.

All messages are JSON-encoded dicts with a "type" field.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.services.redis_service import get_redis

logger = logging.getLogger(__name__)

# Buffer settings
EVENT_BUFFER_SIZE = 500     # max events to keep per session
EVENT_BUFFER_TTL = 3600     # buffer expires after 1 hour of inactivity


# ---------------------------------------------------------------------------
# Channel / key helpers
# ---------------------------------------------------------------------------

def _events_channel(session_id: str) -> str:
    return f"session:{session_id}:events"


def _commands_channel(session_id: str) -> str:
    return f"session:{session_id}:commands"


def _buffer_key(session_id: str) -> str:
    return f"session:{session_id}:buffer"


NOTIFICATIONS_CHANNEL = "notifications"


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

async def publish_event(session_id: str, event: dict[str, Any]) -> None:
    """Publish a session event from Worker → WS handler.
    
    Also appends to the session buffer for reconnection replay.
    """
    r = get_redis()
    payload = json.dumps(event)
    pipe = r.pipeline()
    # Publish to real-time subscribers
    pipe.publish(_events_channel(session_id), payload)
    # Append to buffer (RPUSH = chronological order)
    buf_key = _buffer_key(session_id)
    pipe.rpush(buf_key, payload)
    # Trim buffer to max size (keep latest N events)
    pipe.ltrim(buf_key, -EVENT_BUFFER_SIZE, -1)
    # Reset TTL on activity
    pipe.expire(buf_key, EVENT_BUFFER_TTL)
    await pipe.execute()


async def publish_command(session_id: str, command: dict[str, Any]) -> None:
    """Publish a command from WS handler → Worker."""
    r = get_redis()
    await r.publish(_commands_channel(session_id), json.dumps(command))


async def publish_notification(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast a notification to all subscribers."""
    r = get_redis()
    message = {"type": event_type, **data}
    await r.publish(NOTIFICATIONS_CHANNEL, json.dumps(message))


# ---------------------------------------------------------------------------
# Replay (for WS reconnection)
# ---------------------------------------------------------------------------

async def get_buffered_events(session_id: str, after_index: int = 0) -> list[dict[str, Any]]:
    """
    Get buffered events for a session, starting from after_index.
    
    Returns events that the client missed during disconnection.
    The client sends its last known event index; we return everything after that.
    """
    r = get_redis()
    buf_key = _buffer_key(session_id)
    raw_events = await r.lrange(buf_key, after_index, -1)
    events = []
    for raw in raw_events:
        try:
            events.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue
    return events


async def get_buffer_length(session_id: str) -> int:
    """Get the current buffer length for a session."""
    r = get_redis()
    return await r.llen(_buffer_key(session_id))


async def clear_buffer(session_id: str) -> None:
    """Clear the event buffer for a session (on session end)."""
    r = get_redis()
    await r.delete(_buffer_key(session_id))


# ---------------------------------------------------------------------------
# Subscribing
# ---------------------------------------------------------------------------

async def subscribe_events(session_id: str) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to session events. Yields dicts as they arrive."""
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
    """Subscribe to session commands. Used by Worker."""
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
    """Subscribe to broadcast notifications."""
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
