import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.workflow_edge import WorkflowEdgeCreate
from app.services.workflow_edge_service import (
    EdgeNotFoundError,
    WorkflowNotFoundError,
)


def _make_edge(workflow_id: uuid.UUID | None = None) -> dict:
    return {
        "id": uuid.uuid4(),
        "workflow_id": workflow_id or uuid.uuid4(),
        "from_agent_id": uuid.uuid4(),
        "to_agent_id": uuid.uuid4(),
        "condition": None,
        "prompt_template": None,
        "prompt_id": None,
        "order": 0,
        "requires_approval": True,
        "created_at": datetime.now(timezone.utc),
    }


SERVICE = "app.routers.workflow_edges"


@pytest.mark.asyncio
async def test_list_edges(client):
    wid = uuid.uuid4()
    edge = _make_edge(wid)
    with patch(f"{SERVICE}.get_edges", new_callable=AsyncMock, return_value=[edge]):
        resp = await client.get(f"/api/workflows/{wid}/edges")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_edges_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_edges",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/workflows/{wid}/edges")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_edge(client):
    wid = uuid.uuid4()
    edge = _make_edge(wid)
    with patch(f"{SERVICE}.create_edge", new_callable=AsyncMock, return_value=edge):
        resp = await client.post(
            f"/api/workflows/{wid}/edges",
            json={
                "from_agent_id": str(uuid.uuid4()),
                "to_agent_id": str(uuid.uuid4()),
            },
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_edge_workflow_not_found(client):
    wid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_edge",
        new_callable=AsyncMock,
        side_effect=WorkflowNotFoundError("not found"),
    ):
        resp = await client.post(
            f"/api/workflows/{wid}/edges",
            json={
                "from_agent_id": str(uuid.uuid4()),
                "to_agent_id": str(uuid.uuid4()),
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_edge_self_edge_returns_422(client):
    wid = uuid.uuid4()
    agent_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/workflows/{wid}/edges",
        json={
            "from_agent_id": agent_id,
            "to_agent_id": agent_id,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_edge(client):
    eid = uuid.uuid4()
    edge = _make_edge()
    with patch(f"{SERVICE}.update_edge", new_callable=AsyncMock, return_value=edge):
        resp = await client.put(
            f"/api/edges/{eid}",
            json={"condition": "status == 'done'", "requires_approval": False},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_edge_not_found(client):
    eid = uuid.uuid4()
    with patch(
        f"{SERVICE}.update_edge",
        new_callable=AsyncMock,
        side_effect=EdgeNotFoundError("not found"),
    ):
        resp = await client.put(
            f"/api/edges/{eid}",
            json={"condition": "x"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_edge(client):
    eid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_edge", new_callable=AsyncMock):
        resp = await client.delete(f"/api/edges/{eid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_edge_not_found(client):
    eid = uuid.uuid4()
    with patch(
        f"{SERVICE}.delete_edge",
        new_callable=AsyncMock,
        side_effect=EdgeNotFoundError("not found"),
    ):
        resp = await client.delete(f"/api/edges/{eid}")
    assert resp.status_code == 404


def test_edge_create_schema_valid():
    data = WorkflowEdgeCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
    )
    assert data.order == 0
    assert data.requires_approval is True


def test_edge_create_schema_self_edge_rejected():
    agent_id = uuid.uuid4()
    with pytest.raises(ValueError, match="must be different"):
        WorkflowEdgeCreate(
            from_agent_id=agent_id,
            to_agent_id=agent_id,
        )
