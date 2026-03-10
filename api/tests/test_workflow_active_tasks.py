import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.workflow_service import WorkflowNotFoundError


def _make_task(workflow_id: uuid.UUID, status: str = "in_progress") -> dict:
    return {
        "id": uuid.uuid4(),
        "title": "Test Task",
        "description": "desc",
        "product_id": uuid.uuid4(),
        "team_id": uuid.uuid4(),
        "workflow_id": workflow_id,
        "status": status,
        "created_at": datetime.now(timezone.utc),
    }


WORKFLOW_SERVICE = "app.routers.workflows"
SERVICE = WORKFLOW_SERVICE


@pytest.mark.asyncio
async def test_active_tasks_returns_list(client):
    wid = uuid.uuid4()
    tasks = [_make_task(wid, "in_progress"), _make_task(wid, "awaiting_user")]
    with patch(
        f"{SERVICE}.get_active_tasks",
        new_callable=AsyncMock,
        return_value=tasks,
    ):
        resp = await client.get(f"/api/workflows/{wid}/active-tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["status"] == "in_progress"
    assert data[1]["status"] == "awaiting_user"


@pytest.mark.asyncio
async def test_active_tasks_empty(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_active_tasks",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client.get(f"/api/workflows/{wid}/active-tasks")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_active_tasks_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_active_tasks",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/workflows/{wid}/active-tasks")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lock_status_returns_locked_ids(client):
    wid1 = uuid.uuid4()
    wid2 = uuid.uuid4()
    with patch(
        f"{WORKFLOW_SERVICE}.get_locked_workflow_ids",
        new_callable=AsyncMock,
        return_value={wid1},
    ):
        resp = await client.post(
            "/api/workflows/lock-status",
            json={"workflow_ids": [str(wid1), str(wid2)]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert str(wid1) in data["locked_ids"]
    assert str(wid2) not in data["locked_ids"]


@pytest.mark.asyncio
async def test_lock_status_empty(client):
    with patch(
        f"{WORKFLOW_SERVICE}.get_locked_workflow_ids",
        new_callable=AsyncMock,
        return_value=set(),
    ):
        resp = await client.post(
            "/api/workflows/lock-status",
            json={"workflow_ids": []},
        )
    assert resp.status_code == 200
    assert resp.json()["locked_ids"] == []
