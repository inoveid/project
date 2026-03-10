import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.task_service import (
    VALID_TRANSITIONS,
    update_task_status,
)


def _make_mock_task(status="backlog", **kwargs):
    task = MagicMock()
    task.status = status
    task.title = kwargs.get("title", "Test task")
    task.description = kwargs.get("description", None)
    task.product_id = kwargs.get("product_id", None)
    task.team_id = kwargs.get("team_id", None)
    task.workflow_id = kwargs.get("workflow_id", None)
    return task


@pytest.mark.asyncio
async def test_valid_transitions_map():
    """Verify all expected status transitions exist."""
    assert "backlog" in VALID_TRANSITIONS
    assert "in_progress" in VALID_TRANSITIONS["backlog"]
    assert "awaiting_user" in VALID_TRANSITIONS["in_progress"]
    assert "done" in VALID_TRANSITIONS["in_progress"]
    assert "error" in VALID_TRANSITIONS["in_progress"]
    assert "in_progress" in VALID_TRANSITIONS["done"]
    assert "in_progress" in VALID_TRANSITIONS["error"]


@pytest.mark.asyncio
async def test_update_status_invalid_transition():
    """Invalid transitions should raise 422."""
    task = _make_mock_task(status="backlog")
    db = AsyncMock()

    with patch("app.services.task_service.get_task", new_callable=AsyncMock, return_value=task):
        with pytest.raises(HTTPException) as exc_info:
            await update_task_status(db, uuid.uuid4(), "done")
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_status_backlog_to_in_progress_missing_fields():
    """backlog -> in_progress without required fields should raise 400."""
    task = _make_mock_task(
        status="backlog",
        title="Test",
        description=None,
        product_id=None,
        team_id=None,
        workflow_id=None,
    )
    db = AsyncMock()

    with patch("app.services.task_service.get_task", new_callable=AsyncMock, return_value=task):
        with pytest.raises(HTTPException) as exc_info:
            await update_task_status(db, uuid.uuid4(), "in_progress")
        assert exc_info.value.status_code == 400
        assert "description" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_status_backlog_to_in_progress_all_filled():
    """backlog -> in_progress with all required fields should succeed."""
    task = _make_mock_task(
        status="backlog",
        title="Test",
        description="Description",
        product_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    db = AsyncMock()

    with patch("app.services.task_service.get_task", new_callable=AsyncMock, return_value=task):
        result = await update_task_status(db, uuid.uuid4(), "in_progress")
    assert result.status == "in_progress"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_in_progress_to_awaiting_user():
    """in_progress -> awaiting_user should succeed without field checks."""
    task = _make_mock_task(status="in_progress")
    db = AsyncMock()

    with patch("app.services.task_service.get_task", new_callable=AsyncMock, return_value=task):
        result = await update_task_status(db, uuid.uuid4(), "awaiting_user")
    assert result.status == "awaiting_user"


@pytest.mark.asyncio
async def test_update_status_done_to_in_progress_no_field_check():
    """done -> in_progress should NOT require field validation."""
    task = _make_mock_task(
        status="done",
        description=None,
        product_id=None,
    )
    db = AsyncMock()

    with patch("app.services.task_service.get_task", new_callable=AsyncMock, return_value=task):
        result = await update_task_status(db, uuid.uuid4(), "in_progress")
    assert result.status == "in_progress"
