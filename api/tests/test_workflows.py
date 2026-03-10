import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.workflow_service import (
    AgentNotInTeamError,
    DuplicateWorkflowError,
    TeamNotFoundError,
    WorkflowNotFoundError,
)


def _make_workflow(team_id: uuid.UUID | None = None) -> dict:
    return {
        "id": uuid.uuid4(),
        "name": "Test Workflow",
        "description": "desc",
        "team_id": team_id or uuid.uuid4(),
        "starting_agent_id": uuid.uuid4(),
        "starting_prompt": "Start here",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


SERVICE = "app.routers.workflows"


@pytest.mark.asyncio
async def test_list_workflows(client):
    tid = uuid.uuid4()
    wf = _make_workflow(tid)
    with patch(f"{SERVICE}.get_workflows", new_callable=AsyncMock, return_value=[wf]):
        resp = await client.get(f"/api/teams/{tid}/workflows")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_workflows_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_workflows",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/teams/{tid}/workflows")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_workflow(client):
    tid = uuid.uuid4()
    wf = _make_workflow(tid)
    with patch(f"{SERVICE}.create_workflow", new_callable=AsyncMock, return_value=wf):
        resp = await client.post(
            f"/api/teams/{tid}/workflows",
            json={
                "name": "Test",
                "starting_agent_id": str(uuid.uuid4()),
                "starting_prompt": "Go",
            },
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test Workflow"


@pytest.mark.asyncio
async def test_create_workflow_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_workflow",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/workflows",
            json={
                "name": "Test",
                "starting_agent_id": str(uuid.uuid4()),
                "starting_prompt": "Go",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_workflow_agent_not_in_team(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_workflow",
        new_callable=AsyncMock,
        side_effect=AgentNotInTeamError("wrong team"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/workflows",
            json={
                "name": "Test",
                "starting_agent_id": str(uuid.uuid4()),
                "starting_prompt": "Go",
            },
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_workflow_duplicate(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_workflow",
        new_callable=AsyncMock,
        side_effect=DuplicateWorkflowError("dup"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/workflows",
            json={
                "name": "Dup",
                "starting_agent_id": str(uuid.uuid4()),
                "starting_prompt": "Go",
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_workflow(client):
    wf = _make_workflow()
    wid = wf["id"]
    with patch(f"{SERVICE}.get_workflow", new_callable=AsyncMock, return_value=wf):
        resp = await client.get(f"/api/workflows/{wid}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_workflow",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/workflows/{wid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_workflow(client):
    wf = _make_workflow()
    wid = wf["id"]
    with patch(f"{SERVICE}.update_workflow", new_callable=AsyncMock, return_value=wf):
        resp = await client.put(
            f"/api/workflows/{wid}",
            json={"name": "Updated"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.update_workflow",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.put(
            f"/api/workflows/{wid}",
            json={"name": "Updated"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow(client):
    wid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_workflow", new_callable=AsyncMock):
        resp = await client.delete(f"/api/workflows/{wid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.delete_workflow",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.delete(f"/api/workflows/{wid}")
    assert resp.status_code == 404
