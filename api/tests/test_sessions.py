import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.session import SessionCreate
from app.services.session_service import AgentNotFoundError, SessionNotFoundError


@pytest.fixture
def session_obj():
    """Mimics a Session ORM object as dict for response_model."""
    return {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "status": "active",
        "claude_session_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stopped_at": None,
        "messages": [],
    }


@pytest.fixture
def session_list_item(session_obj):
    return {
        k: v for k, v in session_obj.items() if k != "messages"
    }


SERVICE = "app.routers.sessions"


@pytest.mark.asyncio
async def test_create_session(client, session_obj):
    agent_id = session_obj["agent_id"]
    with patch(f"{SERVICE}.create_session", new_callable=AsyncMock, return_value=session_obj):
        resp = await client.post("/api/sessions", json={"agent_id": str(agent_id)})
    assert resp.status_code == 201
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_create_session_agent_not_found(client):
    with patch(
        f"{SERVICE}.create_session",
        new_callable=AsyncMock,
        side_effect=AgentNotFoundError("not found"),
    ):
        resp = await client.post("/api/sessions", json={"agent_id": str(uuid.uuid4())})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_sessions(client, session_list_item):
    with patch(f"{SERVICE}.get_sessions", new_callable=AsyncMock, return_value=[session_list_item]):
        resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "active"


@pytest.mark.asyncio
async def test_get_session(client, session_obj):
    sid = session_obj["id"]
    with patch(f"{SERVICE}.get_session", new_callable=AsyncMock, return_value=session_obj):
        resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sid)


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    sid = uuid.uuid4()
    with patch(
        f"{SERVICE}.get_session",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundError("not found"),
    ):
        resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client):
    sid = uuid.uuid4()
    with (
        patch(f"{SERVICE}.runtime") as mock_runtime,
        patch(f"{SERVICE}.stop_session", new_callable=AsyncMock),
    ):
        mock_runtime.stop_session = AsyncMock()
        resp = await client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_session_not_found(client):
    sid = uuid.uuid4()
    with (
        patch(f"{SERVICE}.runtime") as mock_runtime,
        patch(
            f"{SERVICE}.stop_session",
            new_callable=AsyncMock,
            side_effect=SessionNotFoundError("not found"),
        ),
    ):
        mock_runtime.stop_session = AsyncMock()
        resp = await client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 404


def test_session_create_schema():
    agent_id = uuid.uuid4()
    data = SessionCreate(agent_id=agent_id)
    assert data.agent_id == agent_id
