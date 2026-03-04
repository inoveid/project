import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.agent_link import AgentLinkCreate, LinkType
from app.services.agent_link_service import (
    AgentNotInTeamError,
    DuplicateLinkError,
    LinkNotFoundError,
    TeamNotFoundError,
)


def _make_link(team_id: Optional[uuid.UUID] = None) -> dict:
    return {
        "id": uuid.uuid4(),
        "team_id": team_id or uuid.uuid4(),
        "from_agent_id": uuid.uuid4(),
        "to_agent_id": uuid.uuid4(),
        "link_type": "handoff",
        "created_at": datetime.now(timezone.utc),
    }


SERVICE = "app.routers.agent_links"


@pytest.mark.asyncio
async def test_list_links(client):
    tid = uuid.uuid4()
    link = _make_link(tid)
    with patch(f"{SERVICE}.get_links", new_callable=AsyncMock, return_value=[link]):
        resp = await client.get(f"/api/teams/{tid}/links")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["link_type"] == "handoff"


@pytest.mark.asyncio
async def test_list_links_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_links",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/teams/{tid}/links")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_link(client):
    tid = uuid.uuid4()
    link = _make_link(tid)
    with patch(f"{SERVICE}.create_link", new_callable=AsyncMock, return_value=link):
        resp = await client.post(
            f"/api/teams/{tid}/links",
            json={
                "from_agent_id": str(link["from_agent_id"]),
                "to_agent_id": str(link["to_agent_id"]),
                "link_type": "handoff",
            },
        )
    assert resp.status_code == 201
    assert resp.json()["link_type"] == "handoff"


@pytest.mark.asyncio
async def test_create_link_team_not_found(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_link",
        new_callable=AsyncMock,
        side_effect=TeamNotFoundError("not found"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/links",
            json={
                "from_agent_id": str(uuid.uuid4()),
                "to_agent_id": str(uuid.uuid4()),
                "link_type": "handoff",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_link_agent_not_in_team(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_link",
        new_callable=AsyncMock,
        side_effect=AgentNotInTeamError("wrong team"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/links",
            json={
                "from_agent_id": str(uuid.uuid4()),
                "to_agent_id": str(uuid.uuid4()),
                "link_type": "review",
            },
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_link_duplicate(client):
    tid = uuid.uuid4()
    with patch(
        f"{SERVICE}.create_link",
        new_callable=AsyncMock,
        side_effect=DuplicateLinkError("duplicate"),
    ):
        resp = await client.post(
            f"/api/teams/{tid}/links",
            json={
                "from_agent_id": str(uuid.uuid4()),
                "to_agent_id": str(uuid.uuid4()),
                "link_type": "handoff",
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_link(client):
    lid = uuid.uuid4()
    with patch(f"{SERVICE}.delete_link", new_callable=AsyncMock):
        resp = await client.delete(f"/api/links/{lid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_link_not_found(client):
    lid = uuid.uuid4()
    with patch(
        f"{SERVICE}.delete_link",
        new_callable=AsyncMock,
        side_effect=LinkNotFoundError("not found"),
    ):
        resp = await client.delete(f"/api/links/{lid}")
    assert resp.status_code == 404


def test_agent_link_create_schema():
    data = AgentLinkCreate(
        from_agent_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        link_type=LinkType.handoff,
    )
    assert data.link_type == LinkType.handoff


def test_agent_link_create_invalid_type():
    with pytest.raises(Exception):
        AgentLinkCreate(
            from_agent_id=uuid.uuid4(),
            to_agent_id=uuid.uuid4(),
            link_type="invalid",  # type: ignore[arg-type]
        )
