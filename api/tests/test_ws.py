"""Tests for app.routers.ws — WebSocket thin proxy via Redis Event Bus."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketState

from app.services.session_service import SessionNotFoundError

WS = "app.routers.ws"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_mock(session_id, agent_id=None):
    agent_id = agent_id or uuid.uuid4()
    agent = MagicMock()
    agent.id = agent_id
    agent.name = "TestAgent"

    session = MagicMock()
    session.id = session_id
    session.agent_id = agent_id
    session.status = "active"
    session.agent = agent
    return session


class FakePubSub:
    """Minimal mock for Redis pub/sub."""

    def __init__(self, messages=None):
        self._messages = messages or []
        self._subscribed = []

    async def subscribe(self, channel):
        self._subscribed.append(channel)

    async def unsubscribe(self, channel):
        self._subscribed.remove(channel)

    async def aclose(self):
        pass

    async def listen(self):
        for msg in self._messages:
            yield msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWebSocketProxy:
    """Test the WS proxy: session validation, event forwarding, command publishing."""

    @pytest.mark.asyncio
    async def test_session_not_found_closes_ws(self):
        """WS closes with 4004 if session doesn't exist."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED
        db = AsyncMock()

        with patch(f"{WS}.get_session", side_effect=SessionNotFoundError("nope")):
            from app.routers.ws import websocket_session
            await websocket_session(ws, uuid.uuid4(), db)

        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        ws.close.assert_awaited_once_with(code=4004)

    @pytest.mark.asyncio
    async def test_notifies_worker_on_connect(self):
        """WS connection publishes start command to worker:sessions."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        mock_redis = AsyncMock()
        mock_pubsub = FakePubSub()
        mock_redis.pubsub.return_value = mock_pubsub

        # WS disconnects immediately
        from fastapi import WebSocketDisconnect
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=[]), \
             patch(f"{WS}._notify_worker_start") as notify_mock:
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        notify_mock.assert_awaited_once_with(str(sid))

    @pytest.mark.asyncio
    async def test_replays_buffered_events(self):
        """On connect, buffered events are sent to WS before live events."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        buffered = [
            {"type": "assistant_text", "content": "Hello"},
            {"type": "done"},
        ]

        mock_redis = AsyncMock()
        mock_pubsub = FakePubSub()  # no live messages
        mock_redis.pubsub.return_value = mock_pubsub

        from fastapi import WebSocketDisconnect
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=buffered), \
             patch(f"{WS}._notify_worker_start"):
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        # Both buffered events should have been sent
        assert ws.send_json.await_count >= 2
        calls = [c[0][0] for c in ws.send_json.call_args_list]
        assert buffered[0] in calls
        assert buffered[1] in calls

    @pytest.mark.asyncio
    async def test_forwards_live_redis_events_to_ws(self):
        """Live Redis pub/sub events are forwarded to WebSocket."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        live_event = {"type": "assistant_text", "content": "Live!"}
        mock_pubsub = FakePubSub(messages=[
            {"type": "subscribe", "data": None},
            {"type": "message", "data": json.dumps(live_event)},
        ])

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        from fastapi import WebSocketDisconnect
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=[]), \
             patch(f"{WS}._notify_worker_start"):
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        # The live event should be sent to WS
        calls = [c[0][0] for c in ws.send_json.call_args_list]
        assert live_event in calls

    @pytest.mark.asyncio
    async def test_publishes_commands_to_redis(self):
        """Client messages are published as Redis commands."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        user_msg = {"type": "message", "content": "Hello agent"}

        # First call returns user message, second disconnects
        from fastapi import WebSocketDisconnect
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps(user_msg),
            WebSocketDisconnect(),
        ])

        mock_redis = AsyncMock()
        mock_pubsub = FakePubSub()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=[]), \
             patch(f"{WS}._notify_worker_start"), \
             patch(f"{WS}.publish_command") as cmd_mock:
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        cmd_mock.assert_awaited_once_with(str(sid), user_msg)

    @pytest.mark.asyncio
    async def test_stop_command_ends_ws_loop(self):
        """Client sending stop command breaks the WS receive loop."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        stop_msg = {"type": "stop"}
        ws.receive_text = AsyncMock(return_value=json.dumps(stop_msg))

        mock_redis = AsyncMock()
        mock_pubsub = FakePubSub()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=[]), \
             patch(f"{WS}._notify_worker_start"), \
             patch(f"{WS}.publish_command") as cmd_mock:
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        cmd_mock.assert_awaited_once_with(str(sid), stop_msg)

    @pytest.mark.asyncio
    async def test_invalid_json_sends_error(self):
        """Invalid JSON from client sends error back, doesn't crash."""
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED

        sid = uuid.uuid4()
        session = _make_session_mock(sid)
        db = AsyncMock()

        from fastapi import WebSocketDisconnect
        ws.receive_text = AsyncMock(side_effect=[
            "not valid json {{{",
            WebSocketDisconnect(),
        ])

        mock_redis = AsyncMock()
        mock_pubsub = FakePubSub()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch(f"{WS}.get_session", return_value=session), \
             patch(f"{WS}.get_redis", return_value=mock_redis), \
             patch(f"{WS}.get_buffered_events", return_value=[]), \
             patch(f"{WS}._notify_worker_start"), \
             patch(f"{WS}.publish_command"):
            from app.routers.ws import websocket_session
            await websocket_session(ws, sid, db)

        # Should have sent an error JSON back
        calls = [c[0][0] for c in ws.send_json.call_args_list]
        error_calls = [c for c in calls if c.get("type") == "error"]
        assert len(error_calls) >= 1
        assert "Invalid JSON" in error_calls[0]["error"]
