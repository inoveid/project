"""Tests for notifications WebSocket endpoint logic.

Since TestClient(app) triggers the DB lifespan, we test the endpoint handler
directly using a lightweight FastAPI app with just the notifications router.
"""

from unittest.mock import patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers.notifications_ws import router
from app.services.notification_service import NotificationBroker


def _make_test_app(broker: NotificationBroker) -> FastAPI:
    """Create a minimal app with only the notifications router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/ws")
    return test_app


def test_connect_subscribes_and_disconnect_unsubscribes():
    """Client connects → subscribed; client disconnects → unsubscribed."""
    test_broker = NotificationBroker()
    app = _make_test_app(test_broker)

    with patch("app.routers.notifications_ws.notification_broker", test_broker):
        client = TestClient(app)
        with client.websocket_connect("/ws/notifications") as ws:
            assert test_broker.subscriber_count == 1
            ws.send_text("ping")  # keep-alive — server receives and loops

        assert test_broker.subscriber_count == 0


def test_multiple_clients():
    """Multiple clients can connect simultaneously."""
    test_broker = NotificationBroker()
    app = _make_test_app(test_broker)

    with patch("app.routers.notifications_ws.notification_broker", test_broker):
        client = TestClient(app)
        with client.websocket_connect("/ws/notifications"):
            assert test_broker.subscriber_count == 1
            with client.websocket_connect("/ws/notifications"):
                assert test_broker.subscriber_count == 2
            assert test_broker.subscriber_count == 1
        assert test_broker.subscriber_count == 0
