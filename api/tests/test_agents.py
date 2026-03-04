import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.agent_service import (
    AgentDuplicateNameError,
    AgentNotFoundError,
    TeamNotFoundError,
)


def _make_agent(team_id: Optional[uuid.UUID] = None) -> dict:
    return {
        "id": uuid.uuid4(),
        "team_id": team_id or uuid.uuid4(),
        "name": "Coder",
        "role": "developer",
        "description": "Writes code",
        "system_prompt": "You are a developer.",
        "allowed_tools": ["bash", "read"],
        "config": {"model": "claude-sonnet"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


SERVICE = "app.routers.agents"


@pytest.mark.asyncio
async def test_list_agents(client):
    tid = uuid.uuid4()
    agent = _make_agent(tid)
    with patch(f"{SERVICE}.get_agents", new_callable=AsyncMock, return_value=[agent]):
        resp = await client.get(f"/api/teams/{tid}/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Coder"


@pytest.mark.asyncio
async def test_list_agents_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_agents",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/teams/{tid}/agents")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_agent(client):
    tid = uuid.uuid4()
    agent = _make_agent(tid)
    with patch(f"{SERVICE}.create_agent", new_callable=AsyncMock, return_value=agent):
        resp = await client.post(
            f"/api/teams/{tid}/agents",
            json={
                "name": "Coder",
                "role": "developer",
                "system_prompt": "You are a developer.",
            },
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Coder"


@pytest.mark.asyncio
async def test_create_agent_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_agent",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/agents",
            json={
                "name": "Coder",
                "role": "developer",
                "system_prompt": "You are a developer.",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_agent_duplicate(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_agent",
        new_callable=AsyncMock,
        side_effect=AgentDuplicateNameError("duplicate"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/agents",
            json={
                "name": "Dup",
                "role": "developer",
                "system_prompt": "prompt",
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_agent(client):
    agent = _make_agent()
    aid = agent["id"]
    with patch(f"{SERVICE}.get_agent", new_callable=AsyncMock, return_value=agent):
        resp = await client.get(f"/api/agents/{aid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Coder"


@pytest.mark.asyncio
async def test_get_agent_not_found(client):
    aid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_agent",
        new_callable=AsyncMock,
        side_effect=AgentNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/agents/{aid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_agent(client):
    agent = _make_agent()
    aid = agent["id"]
    updated = {**agent, "name": "Reviewer"}
    with patch(f"{SERVICE}.update_agent", new_callable=AsyncMock, return_value=updated):
        resp = await client.patch(f"/api/agents/{aid}", json={"name": "Reviewer"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Reviewer"


@pytest.mark.asyncio
async def test_update_agent_not_found(client):
    aid = uuid.uuid4()
    with patch(
        f"{SERVICE}.update_agent",
        new_callable=AsyncMock,
        side_effect=AgentNotFoundError("not found"),
    ):
        resp = await client.patch(f"/api/agents/{aid}", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(client):
    aid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_agent", new_callable=AsyncMock):
        resp = await client.delete(f"/api/agents/{aid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_agent_not_found(client):
    aid = uuid.uuid4()
    with patch(
        f"{SERVICE}.delete_agent",
        new_callable=AsyncMock,
        side_effect=AgentNotFoundError("not found"),
    ):
        resp = await client.delete(f"/api/agents/{aid}")
    assert resp.status_code == 404


def test_agent_create_schema():
    data = AgentCreate(
        name="Test", role="dev", system_prompt="prompt"
    )
    assert data.name == "Test"
    assert data.allowed_tools == []
    assert data.config == {}


def test_agent_update_schema():
    data = AgentUpdate(name="Updated")
    dump = data.model_dump(exclude_unset=True)
    assert dump == {"name": "Updated"}


def test_agent_create_validation():
    with pytest.raises(Exception):
        AgentCreate(name="", role="dev", system_prompt="prompt")
