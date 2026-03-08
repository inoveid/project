import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.session_service import SessionNotFoundError


def _make_session_mock(session_id, agent_id=None):
    agent_id = agent_id or uuid.uuid4()
    agent = MagicMock()
    agent.config = {"workdir": "/tmp/project"}
    agent.system_prompt = "You are helpful"

    session = MagicMock()
    session.id = session_id
    session.agent_id = agent_id
    session.status = "active"
    session.claude_session_id = None
    session.agent = agent
    session.messages = []
    return session


WS_SERVICE = "app.routers.ws"


def _default_patches(session):
    """Return common patches for WS tests (session + handoff_targets)."""
    return [
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
    ]


def test_ws_session_not_found():
    with (
        patch(
            f"{WS_SERVICE}.get_session",
            new_callable=AsyncMock,
            side_effect=SessionNotFoundError("not found"),
        ),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
    ):
        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{uuid.uuid4()}") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "not found" in data["error"]


def test_ws_invalid_json():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS_SERVICE}.runtime") as mock_runtime,
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_text("not json")
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON" in data["error"]


def test_ws_unknown_message_type():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS_SERVICE}.runtime") as mock_runtime,
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "unknown"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown type" in data["error"]


def test_ws_empty_message_content():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS_SERVICE}.runtime") as mock_runtime,
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": ""})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Empty" in data["error"]


def test_ws_stop_message():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS_SERVICE}.runtime") as mock_runtime,
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "stop"})
            data = ws.receive_json()
            assert data["type"] == "done"

        mock_runtime.stop_session.assert_called_once_with(session_id)



def test_ws_starts_runtime_if_not_running():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS_SERVICE}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS_SERVICE}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS_SERVICE}.runtime") as mock_runtime,
    ):
        mock_runtime.is_running.return_value = False
        mock_runtime.start_session = AsyncMock()
        mock_runtime.stop_session = AsyncMock()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "stop"})
            ws.receive_json()

        mock_runtime.start_session.assert_called_once()
        call_kwargs = mock_runtime.start_session.call_args.kwargs
        assert call_kwargs["session_id"] == session_id
        assert call_kwargs["workdir"] == "/tmp/project"
        assert call_kwargs["system_prompt"] == "You are helpful"
