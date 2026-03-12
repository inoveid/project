"""Tests for notification_service — Redis pub/sub wrapper."""

import pytest
from unittest.mock import AsyncMock, patch


from app.services.notification_service import broadcast_notification


@pytest.mark.asyncio
async def test_broadcast_notification_publishes_to_redis():
    """broadcast_notification calls publish_notification with correct args."""
    with patch("app.services.notification_service.publish_notification", new_callable=AsyncMock) as mock_publish:
        await broadcast_notification("task_completed", {"task_id": "123"})
        mock_publish.assert_awaited_once_with("task_completed", {"task_id": "123"})


@pytest.mark.asyncio
async def test_broadcast_notification_different_event_types():
    """Works with various event types."""
    with patch("app.services.notification_service.publish_notification", new_callable=AsyncMock) as mock_publish:
        await broadcast_notification("task_error", {"error": "fail", "task_id": "456"})
        mock_publish.assert_awaited_once_with("task_error", {"error": "fail", "task_id": "456"})


@pytest.mark.asyncio
async def test_broadcast_notification_empty_data():
    """Works with empty data dict."""
    with patch("app.services.notification_service.publish_notification", new_callable=AsyncMock) as mock_publish:
        await broadcast_notification("ping", {})
        mock_publish.assert_awaited_once_with("ping", {})
