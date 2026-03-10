import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent_service import AgentDeletionBlockedError, AgentNotFoundError


SERVICE = "app.routers.agents"


@pytest.mark.asyncio
async def test_can_delete_allowed(client):
    aid = uuid.uuid4()
    with patch(
        f"{SERVICE}.can_delete_agent",
        new_callable=AsyncMock,
        return_value=(True, None),
    ):
        resp = await client.get(f"/api/agents/{aid}/can-delete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_delete"] is True
    assert data["reason"] is None


@pytest.mark.asyncio
async def test_can_delete_blocked_active_session(client):
    aid = uuid.uuid4()
    reason = "Agent 'Coder' has active sessions"
    with patch(
        f"{SERVICE}.can_delete_agent",
        new_callable=AsyncMock,
        return_value=(False, reason),
    ):
        resp = await client.get(f"/api/agents/{aid}/can-delete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_delete"] is False
    assert data["reason"] == reason


@pytest.mark.asyncio
async def test_can_delete_blocked_workflow_active(client):
    aid = uuid.uuid4()
    reason = "Agent 'Coder' is part of a workflow with an active task"
    with patch(
        f"{SERVICE}.can_delete_agent",
        new_callable=AsyncMock,
        return_value=(False, reason),
    ):
        resp = await client.get(f"/api/agents/{aid}/can-delete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_delete"] is False
    assert "active task" in data["reason"]


@pytest.mark.asyncio
async def test_can_delete_agent_not_found(client):
    aid = uuid.uuid4()
    with patch(
        f"{SERVICE}.can_delete_agent",
        new_callable=AsyncMock,
        side_effect=AgentNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/agents/{aid}/can-delete")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_blocked_returns_409(client):
    aid = uuid.uuid4()
    reason = "Agent 'Coder' has active sessions"
    with patch(
        f"{SERVICE}.delete_agent",
        new_callable=AsyncMock,
        side_effect=AgentDeletionBlockedError(reason),
    ):
        resp = await client.delete(f"/api/agents/{aid}")
    assert resp.status_code == 409
    assert reason in resp.json()["detail"]
