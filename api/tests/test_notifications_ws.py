"""Tests for notifications WebSocket endpoint — Redis pub/sub based."""

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.routers.notifications_ws import notifications_ws


@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    ws.client_state = MagicMock()

    from starlette.websockets import WebSocketState
    ws.client_state = WebSocketState.CONNECTED

    # Simulate disconnect after first receive
    ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))
    return ws


@pytest.mark.asyncio
async def test_notifications_ws_accepts_connection(mock_websocket):
    """Endpoint accepts WebSocket connection."""
    async def fake_subscribe():
        return
        yield  # make it async gen

    with patch("app.routers.notifications_ws.subscribe_notifications", side_effect=fake_subscribe):
        await notifications_ws(mock_websocket)

    mock_websocket.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_notifications_ws_forwards_events(mock_websocket):
    """Events from Redis are forwarded to WebSocket."""
    events = [
        {"type": "task_completed", "task_id": "123"},
        {"type": "task_error", "error": "fail"},
    ]

    async def fake_subscribe():
        for e in events:
            yield e

    # Let receive_text raise WebSocketDisconnect to end the loop
    from fastapi import WebSocketDisconnect
    mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    with patch("app.routers.notifications_ws.subscribe_notifications", side_effect=fake_subscribe):
        await notifications_ws(mock_websocket)

    assert mock_websocket.send_json.await_count == 2
    mock_websocket.send_json.assert_any_await(events[0])
    mock_websocket.send_json.assert_any_await(events[1])
