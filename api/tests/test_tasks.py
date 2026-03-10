import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

SERVICE = "app.routers.tasks"


def make_task(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "title": "Implement feature X",
        "description": "Full description",
        "product_id": uuid.uuid4(),
        "team_id": uuid.uuid4(),
        "workflow_id": uuid.uuid4(),
        "status": "backlog",
        "created_at": datetime(2026, 3, 10),
    }
    defaults.update(kwargs)
    return defaults


@pytest.mark.asyncio
async def test_list_tasks(client):
    product_id = uuid.uuid4()
    tasks = [make_task(product_id=product_id)]
    with patch(f"{SERVICE}.get_tasks", new_callable=AsyncMock, return_value=tasks):
        resp = await client.get(f"/api/tasks?product_id={product_id}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Implement feature X"


@pytest.mark.asyncio
async def test_list_tasks_requires_product_id(client):
    resp = await client.get("/api/tasks")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_task(client):
    task = make_task()
    with patch(f"{SERVICE}.create_task", new_callable=AsyncMock, return_value=task):
        resp = await client.post("/api/tasks", json={"title": "Implement feature X"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Implement feature X"


@pytest.mark.asyncio
async def test_get_task(client):
    task = make_task()
    tid = task["id"]
    with patch(f"{SERVICE}.get_task", new_callable=AsyncMock, return_value=task):
        resp = await client.get(f"/api/tasks/{tid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Implement feature X"


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    tid = uuid.uuid4()
    exc = HTTPException(status_code=404, detail="Task not found")
    with patch(f"{SERVICE}.get_task", new_callable=AsyncMock, side_effect=exc):
        resp = await client.get(f"/api/tasks/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client):
    task = make_task(title="Updated title")
    tid = task["id"]
    with patch(f"{SERVICE}.update_task", new_callable=AsyncMock, return_value=task):
        resp = await client.put(f"/api/tasks/{tid}", json={"title": "Updated title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


@pytest.mark.asyncio
async def test_delete_task(client):
    tid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_task", new_callable=AsyncMock, return_value=None):
        resp = await client.delete(f"/api/tasks/{tid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_update_task_status(client):
    task = make_task(status="in_progress")
    tid = task["id"]
    with patch(f"{SERVICE}.update_task_status", new_callable=AsyncMock, return_value=task):
        resp = await client.patch(f"/api/tasks/{tid}/status", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_update_task_status_invalid_transition(client):
    tid = uuid.uuid4()
    exc = HTTPException(status_code=422, detail="Invalid transition: backlog -> done")
    with patch(f"{SERVICE}.update_task_status", new_callable=AsyncMock, side_effect=exc):
        resp = await client.patch(f"/api/tasks/{tid}/status", json={"status": "done"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_task_status_missing_fields(client):
    tid = uuid.uuid4()
    exc = HTTPException(status_code=400, detail="Required fields missing: description, product_id")
    with patch(f"{SERVICE}.update_task_status", new_callable=AsyncMock, side_effect=exc):
        resp = await client.patch(f"/api/tasks/{tid}/status", json={"status": "in_progress"})
    assert resp.status_code == 400
