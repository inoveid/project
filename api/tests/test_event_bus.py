"""Tests for app.services.event_bus — Redis pub/sub and event buffer."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

EVENT_BUS = "app.services.event_bus"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal mock for Redis operations used by event_bus."""

    def __init__(self):
        self.published = []  # (channel, payload) tuples
        self.lists = {}      # key → [values]
        self.ttls = {}       # key → seconds
        self._pubsub_instance = None

    async def publish(self, channel, payload):
        self.published.append((channel, payload))

    def pipeline(self):
        return FakePipeline(self)

    async def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start:end + 1]

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def delete(self, key):
        self.lists.pop(key, None)

    def pubsub(self):
        self._pubsub_instance = FakePubSub()
        return self._pubsub_instance


class FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def publish(self, channel, payload):
        self._ops.append(("publish", channel, payload))

    def rpush(self, key, value):
        self._ops.append(("rpush", key, value))

    def ltrim(self, key, start, end):
        self._ops.append(("ltrim", key, start, end))

    def expire(self, key, seconds):
        self._ops.append(("expire", key, seconds))

    async def execute(self):
        for op in self._ops:
            if op[0] == "publish":
                await self._redis.publish(op[1], op[2])
            elif op[0] == "rpush":
                self._redis.lists.setdefault(op[1], []).append(op[2])
            elif op[0] == "ltrim":
                key, start, end = op[1], op[2], op[3]
                items = self._redis.lists.get(key, [])
                self._redis.lists[key] = items[start:] if end == -1 else items[start:end + 1]
            elif op[0] == "expire":
                self._redis.ttls[op[1]] = op[2]


class FakePubSub:
    def __init__(self, messages=None):
        self._messages = messages or []
        self._subscribed = []

    async def subscribe(self, channel):
        self._subscribed.append(channel)

    async def unsubscribe(self, channel):
        if channel in self._subscribed:
            self._subscribed.remove(channel)

    async def aclose(self):
        pass

    async def listen(self):
        for msg in self._messages:
            yield msg


# ---------------------------------------------------------------------------
# publish_event tests
# ---------------------------------------------------------------------------

class TestPublishEvent:
    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_publishes_to_events_channel(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import publish_event
        await publish_event("session-123", {"type": "done"})

        # Should publish to events channel
        assert len(fake.published) == 1
        channel, payload = fake.published[0]
        assert channel == "session:session-123:events"
        assert json.loads(payload) == {"type": "done"}

    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_appends_to_buffer(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import publish_event
        await publish_event("s1", {"type": "assistant_text", "content": "hello"})

        buf_key = "session:s1:buffer"
        assert buf_key in fake.lists
        assert len(fake.lists[buf_key]) == 1
        assert json.loads(fake.lists[buf_key][0])["type"] == "assistant_text"

    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_buffer_has_ttl(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import publish_event, EVENT_BUFFER_TTL
        await publish_event("s1", {"type": "done"})

        buf_key = "session:s1:buffer"
        assert fake.ttls.get(buf_key) == EVENT_BUFFER_TTL


# ---------------------------------------------------------------------------
# publish_command tests
# ---------------------------------------------------------------------------

class TestPublishCommand:
    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_publishes_to_commands_channel(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import publish_command
        await publish_command("session-456", {"type": "message", "content": "hi"})

        assert len(fake.published) == 1
        channel, payload = fake.published[0]
        assert channel == "session:session-456:commands"
        assert json.loads(payload)["type"] == "message"


# ---------------------------------------------------------------------------
# publish_notification tests
# ---------------------------------------------------------------------------

class TestPublishNotification:
    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_publishes_to_notifications_channel(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import publish_notification
        await publish_notification("task_completed", {"task_id": "t1"})

        assert len(fake.published) == 1
        channel, payload = fake.published[0]
        assert channel == "notifications"
        data = json.loads(payload)
        assert data["type"] == "task_completed"
        assert data["task_id"] == "t1"


# ---------------------------------------------------------------------------
# get_buffered_events tests
# ---------------------------------------------------------------------------

class TestGetBufferedEvents:
    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_returns_parsed_events(self, mock_get_redis):
        fake = FakeRedis()
        fake.lists["session:s1:buffer"] = [
            json.dumps({"type": "assistant_text", "content": "a"}),
            json.dumps({"type": "done"}),
        ]
        mock_get_redis.return_value = fake

        from app.services.event_bus import get_buffered_events
        events = await get_buffered_events("s1")
        assert len(events) == 2
        assert events[0]["type"] == "assistant_text"
        assert events[1]["type"] == "done"

    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_empty_buffer_returns_empty_list(self, mock_get_redis):
        fake = FakeRedis()
        mock_get_redis.return_value = fake

        from app.services.event_bus import get_buffered_events
        events = await get_buffered_events("nonexistent")
        assert events == []

    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_skips_invalid_json(self, mock_get_redis):
        fake = FakeRedis()
        fake.lists["session:s1:buffer"] = [
            json.dumps({"type": "done"}),
            "not-json",
            json.dumps({"type": "error", "error": "x"}),
        ]
        mock_get_redis.return_value = fake

        from app.services.event_bus import get_buffered_events
        events = await get_buffered_events("s1")
        assert len(events) == 2  # skipped the invalid one


# ---------------------------------------------------------------------------
# clear_buffer tests
# ---------------------------------------------------------------------------

class TestClearBuffer:
    @pytest.mark.asyncio
    @patch(f"{EVENT_BUS}.get_redis")
    async def test_deletes_buffer_key(self, mock_get_redis):
        fake = FakeRedis()
        fake.lists["session:s1:buffer"] = [json.dumps({"type": "done"})]
        mock_get_redis.return_value = fake

        from app.services.event_bus import clear_buffer
        await clear_buffer("s1")
        assert "session:s1:buffer" not in fake.lists


# ---------------------------------------------------------------------------
# Channel naming tests
# ---------------------------------------------------------------------------

class TestChannelNaming:
    def test_events_channel_format(self):
        from app.services.event_bus import _events_channel
        assert _events_channel("abc-123") == "session:abc-123:events"

    def test_commands_channel_format(self):
        from app.services.event_bus import _commands_channel
        assert _commands_channel("abc-123") == "session:abc-123:commands"

    def test_buffer_key_format(self):
        from app.services.event_bus import _buffer_key
        assert _buffer_key("abc-123") == "session:abc-123:buffer"


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_buffer_size_is_reasonable(self):
        from app.services.event_bus import EVENT_BUFFER_SIZE
        assert 100 <= EVENT_BUFFER_SIZE <= 10000

    def test_buffer_ttl_is_reasonable(self):
        from app.services.event_bus import EVENT_BUFFER_TTL
        assert 300 <= EVENT_BUFFER_TTL <= 86400  # 5 min to 24 hours
