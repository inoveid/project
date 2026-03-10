"""Tests for notification_service — in-memory pub/sub broker."""
import pytest
from unittest.mock import AsyncMock, PropertyMock, patch

from starlette.websockets import WebSocketState

from app.services.notification_service import NotificationBroker, broadcast_notification


@pytest.fixture
def broker():
    return NotificationBroker()


def _make_ws(connected: bool = True):
    ws = AsyncMock()
    type(ws).client_state = PropertyMock(
        return_value=WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    )
    return ws


class TestNotificationBroker:
    def test_subscribe_and_unsubscribe(self, broker: NotificationBroker):
        ws = _make_ws()
        broker.subscribe(ws)
        assert broker.subscriber_count == 1
        broker.unsubscribe(ws)
        assert broker.subscriber_count == 0

    def test_unsubscribe_missing_is_noop(self, broker: NotificationBroker):
        ws = _make_ws()
        broker.unsubscribe(ws)
        assert broker.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, broker: NotificationBroker):
        ws1 = _make_ws()
        ws2 = _make_ws()
        broker.subscribe(ws1)
        broker.subscribe(ws2)

        await broker.broadcast("task_completed", {"task_id": "123"})

        ws1.send_json.assert_awaited_once_with({
            "type": "task_completed",
            "task_id": "123",
        })
        ws2.send_json.assert_awaited_once_with({
            "type": "task_completed",
            "task_id": "123",
        })

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self, broker: NotificationBroker):
        ws_ok = _make_ws(connected=True)
        ws_bad = _make_ws(connected=False)
        broker.subscribe(ws_ok)
        broker.subscribe(ws_bad)

        await broker.broadcast("test", {"key": "val"})

        assert broker.subscriber_count == 1
        ws_ok.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_removes_on_exception(self, broker: NotificationBroker):
        ws_ok = _make_ws()
        ws_err = _make_ws()
        ws_err.send_json.side_effect = RuntimeError("broken pipe")
        broker.subscribe(ws_ok)
        broker.subscribe(ws_err)

        await broker.broadcast("error_event", {"msg": "test"})

        assert broker.subscriber_count == 1


@pytest.mark.asyncio
async def test_broadcast_notification_convenience():
    """Test the module-level convenience wrapper."""
    with patch("app.services.notification_service.notification_broker") as mock_broker:
        mock_broker.broadcast = AsyncMock()
        await broadcast_notification("task_error", {"error": "fail"})
        mock_broker.broadcast.assert_awaited_once_with("task_error", {"error": "fail"})
