import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.team import TeamCreate, TeamUpdate
from app.services.team_service import (
    TeamDuplicateNameError,
    TeamNotFoundError,
)


@pytest.fixture
def team_dict():
    return {
        "id": uuid.uuid4(),
        "name": "Test Team",
        "description": "A test team",
        "project_scoped": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "agents_count": 0,
    }


SERVICE = "app.routers.teams"


@pytest.mark.asyncio
async def test_list_teams(client, team_dict):
    with patch(f"{SERVICE}.get_teams", new_callable=AsyncMock, return_value=[team_dict]):
        resp = await client.get("/api/teams")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Team"


@pytest.mark.asyncio
async def test_create_team(client, team_dict):
    with patch(f"{SERVICE}.create_team", new_callable=AsyncMock, return_value=team_dict):
        resp = await client.post("/api/teams", json={"name": "Test Team"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test Team"


@pytest.mark.asyncio
async def test_create_team_duplicate(client):
    with patch(
        f"{SERVICE}.create_team",
        new_callable=AsyncMock,
        side_effect=TeamDuplicateNameError("duplicate"),
    ):
        resp = await client.post("/api/teams", json={"name": "Dup"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_team(client, team_dict):
    tid = team_dict["id"]
    with patch(f"{SERVICE}.get_team", new_callable=AsyncMock, return_value=team_dict):
        resp = await client.get(f"/api/teams/{tid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Team"


@pytest.mark.asyncio
async def test_get_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_team",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/teams/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_team(client, team_dict):
    tid = team_dict["id"]
    updated = {**team_dict, "name": "Updated"}
    with patch(f"{SERVICE}.update_team", new_callable=AsyncMock, return_value=updated):
        resp = await client.patch(f"/api/teams/{tid}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_team(client):
    tid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_team", new_callable=AsyncMock):
        resp = await client.delete(f"/api/teams/{tid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.delete_team",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.delete(f"/api/teams/{tid}")
    assert resp.status_code == 404


def test_team_create_schema():
    data = TeamCreate(name="My Team")
    assert data.name == "My Team"
    assert data.project_scoped is False
    assert data.description is None


def test_team_update_schema():
    data = TeamUpdate(name="Updated")
    dump = data.model_dump(exclude_unset=True)
    assert dump == {"name": "Updated"}


def test_team_create_validation():
    with pytest.raises(Exception):
        TeamCreate(name="")
