"""Tests for app.routers.ws — WebSocket handler."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from starlette.testclient import TestClient

from app.database import get_db
from app.main import app
from app.services.session_service import SessionNotFoundError

WS = "app.routers.ws"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_mock(session_id, agent_id=None, task_id=None):
    agent_id = agent_id or uuid.uuid4()
    agent = MagicMock()
    agent.id = agent_id
    agent.name = "TestAgent"
    agent.config = {"workdir": "/tmp/project"}
    agent.system_prompt = "You are helpful"
    agent.allowed_tools = []

    session = MagicMock()
    session.id = session_id
    session.agent_id = agent_id
    session.status = "active"
    session.claude_session_id = None
    session.task_id = task_id
    session.agent = agent
    session.messages = []

    # When task_id is set, provide task→product chain for workdir resolution
    if task_id:
        product = MagicMock()
        product.workspace_path = "/tmp/project"
        task = MagicMock()
        task.product_id = uuid.uuid4()
        task.product = product
        session.task = task
    else:
        session.task = None

    return session


def _noop_graph():
    """Mock graph that streams nothing and finishes."""
    g = MagicMock()

    async def _astream(*args, **kwargs):
        return
        yield  # make it an async generator  # noqa: unreachable

    g.astream = _astream
    return g


def _error_graph(error_msg="Graph exploded"):
    """Mock graph whose astream raises an exception."""
    g = MagicMock()

    async def _astream(*args, **kwargs):
        raise RuntimeError(error_msg)
        yield  # noqa: unreachable — makes it async gen

    g.astream = _astream
    return g


def _capturing_graph():
    """Mock graph that captures inputs and interrupts on 1st call."""
    captured = []
    counter = {"n": 0}
    g = MagicMock()

    async def _astream(input, config, **kwargs):
        counter["n"] += 1
        captured.append(input)
        if counter["n"] == 1:
            yield {"__interrupt__": True}
        else:
            yield {"messages": []}

    g.astream = _astream
    g._captured = captured
    return g


# ---------------------------------------------------------------------------
# Basic connection & error handling
# ---------------------------------------------------------------------------


def test_ws_session_not_found():
    with patch(
        f"{WS}.get_session",
        new_callable=AsyncMock,
        side_effect=SessionNotFoundError("not found"),
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
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
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
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
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
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": ""})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Empty" in data["error"]


# ---------------------------------------------------------------------------
# Stop & runtime lifecycle
# ---------------------------------------------------------------------------


def test_ws_stop_message():
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
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
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
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


# ---------------------------------------------------------------------------
# Message → DB + Graph
# ---------------------------------------------------------------------------


def test_ws_message_saves_to_db():
    """Incoming message is saved to DB via add_message before graph runs."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    mock_add = AsyncMock()

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", mock_add),
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "Hello agent"})
            data = ws.receive_json()
            assert data["type"] == "done"

        mock_add.assert_called_once()
        args = mock_add.call_args.args
        assert args[1] == session_id
        assert args[2] == "user"
        assert args[3] == "Hello agent"


def test_ws_message_triggers_run_graph():
    """Message triggers graph.astream with correct initial WorkflowState."""
    session_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    session = _make_session_mock(session_id, agent_id=agent_id)
    session.agent.name = "Dev"

    captured = {}
    g = MagicMock()

    async def _astream(input, config, **kwargs):
        captured["state"] = input
        return
        yield  # noqa: unreachable

    g.astream = _astream

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "Do the thing"})
            ws.receive_json()  # done

    state = captured["state"]
    assert state["main_session_id"] == str(session_id)
    assert state["current_session_id"] == str(session_id)
    assert state["current_agent_id"] == str(agent_id)
    assert state["current_agent_name"] == "Dev"
    assert state["task"] == "Do the thing"
    assert state["depth"] == 0
    assert state["chain"] == []
    assert state["handoff_target"] is None


# ---------------------------------------------------------------------------
# Interrupt / Approve / Reject
# ---------------------------------------------------------------------------


def test_ws_run_graph_sets_interrupted():
    """__interrupt__ in graph output sets interrupted=True; no 'done' sent."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    g = MagicMock()

    async def _astream(*args, **kwargs):
        yield {"__interrupt__": True}

    g.astream = _astream

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
        patch(f"{WS}.stop_session", new_callable=AsyncMock),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()
        mock_runtime.get_children.return_value = set()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "trigger handoff"})
            # Verify interrupted state: a new message should get error
            ws.send_json({"type": "message", "content": "another"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "approval" in data["error"].lower()


def test_ws_approve_resumes_graph():
    """Approve when interrupted resumes graph with Command(resume=True)."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    g = _capturing_graph()

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
        patch(f"{WS}.stop_session", new_callable=AsyncMock),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()
        mock_runtime.get_children.return_value = set()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "start"})
            ws.send_json({"type": "approve"})
            data = ws.receive_json()
            assert data["type"] == "done"

    from langgraph.types import Command
    resume_input = g._captured[1]
    assert isinstance(resume_input, Command)
    assert resume_input.resume is True


def test_ws_reject_resumes_graph():
    """Reject when interrupted resumes graph with Command(resume=False)."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    g = _capturing_graph()

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
        patch(f"{WS}.stop_session", new_callable=AsyncMock),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()
        mock_runtime.get_children.return_value = set()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "start"})
            ws.send_json({"type": "reject"})
            data = ws.receive_json()
            assert data["type"] == "done"

    from langgraph.types import Command
    resume_input = g._captured[1]
    assert isinstance(resume_input, Command)
    assert resume_input.resume is False


def test_ws_message_while_interrupted_sends_error():
    """Message while graph is interrupted returns approval error."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    g = MagicMock()

    async def _astream(*args, **kwargs):
        yield {"__interrupt__": True}

    g.astream = _astream

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
        patch(f"{WS}.stop_session", new_callable=AsyncMock),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()
        mock_runtime.get_children.return_value = set()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "trigger"})
            ws.send_json({"type": "message", "content": "new message"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "approval" in data["error"].lower()


# ---------------------------------------------------------------------------
# Disconnect cleanup
# ---------------------------------------------------------------------------


def test_ws_disconnect_cleanup():
    """On disconnect, child sessions stopped in DB and main runtime cleaned up."""
    session_id = uuid.uuid4()
    child_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    mock_stop_svc = AsyncMock()

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.stop_session", mock_stop_svc),
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.get_children.return_value = {child_id}
        mock_runtime.stop_session = AsyncMock()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}"):
            pass  # disconnect immediately

        mock_stop_svc.assert_called_once()
        assert mock_stop_svc.call_args.args[1] == child_id
        mock_runtime.stop_session.assert_called_once_with(session_id)


# ---------------------------------------------------------------------------
# Handoff targets in prompt
# ---------------------------------------------------------------------------


def test_ws_handoff_targets_appended_to_prompt():
    """Handoff targets are appended to system_prompt for runtime."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    target = MagicMock()
    target.name = "Reviewer"
    target.role = "reviewer"
    target.description = "Reviews code"

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[target]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = False
        mock_runtime.start_session = AsyncMock()
        mock_runtime.stop_session = AsyncMock()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "stop"})
            ws.receive_json()

        call_kwargs = mock_runtime.start_session.call_args.kwargs
        assert "Reviewer" in call_kwargs["system_prompt"]
        assert "handoff" in call_kwargs["system_prompt"].lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_ws_start_session_error_closes_connection():
    """If runtime.start_session raises, error is sent and WS closed with 4000."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = False
        mock_runtime.start_session = AsyncMock(side_effect=RuntimeError("workdir busy"))

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "workdir busy" in data["error"]


def test_ws_graph_error_sends_error_event():
    """If graph.astream raises, error event is sent and 'done' follows."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=_error_graph("LLM timeout")),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "hello"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "LLM timeout" in data["error"]
            # After error, done is sent (interrupted=False)
            done = ws.receive_json()
            assert done["type"] == "done"


def test_ws_approve_when_not_interrupted_is_unknown():
    """Approve/reject when not interrupted goes to 'else' → unknown type error."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "approve"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Unknown type" in data["error"]


# ---------------------------------------------------------------------------
# Streaming: graph produces events forwarded to WS
# ---------------------------------------------------------------------------


def _streaming_graph():
    """Mock graph whose astream yields multiple value chunks."""
    g = MagicMock()

    async def _astream(input, config, **kwargs):
        yield {"messages": [{"agent": "Dev", "text": "chunk1"}]}
        yield {"messages": [{"agent": "Dev", "text": "chunk2"}]}

    g.astream = _astream
    return g


def test_ws_streaming_events_forwarded():
    """Graph streaming chunks are processed; 'done' is sent after completion."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=_streaming_graph()),
    ):
        mock_runtime.is_running.return_value = True

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "Hello"})
            data = ws.receive_json()
            assert data["type"] == "done"


# ---------------------------------------------------------------------------
# _try_update_task_status
# ---------------------------------------------------------------------------


def _override_db_with_mock():
    """Override get_db dependency with an AsyncMock that has no-op refresh."""
    mock_db = AsyncMock()
    mock_db.refresh = AsyncMock()  # no-op for task/product loading

    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db
    return mock_db


def test_ws_interrupt_sets_task_awaiting_user():
    """When graph interrupts, task status is updated to awaiting_user."""
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _make_session_mock(session_id, task_id=task_id)

    g = MagicMock()

    async def _astream(*args, **kwargs):
        yield {"__interrupt__": True}

    g.astream = _astream

    mock_update_task = AsyncMock()

    _override_db_with_mock()
    try:
        with (
            patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
            patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
            patch(f"{WS}.runtime") as mock_runtime,
            patch(f"{WS}.add_message", new_callable=AsyncMock),
            patch(f"{WS}.get_graph", return_value=g),
            patch(f"{WS}.stop_session", new_callable=AsyncMock),
            patch(f"{WS}.update_task_status", mock_update_task),
        ):
            mock_runtime.is_running.return_value = True
            mock_runtime.stop_session = AsyncMock()
            mock_runtime.get_children.return_value = set()

            client = TestClient(app)
            with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
                ws.send_json({"type": "message", "content": "trigger handoff"})
                # Read the error from the next message attempt to confirm interrupted state
                ws.send_json({"type": "message", "content": "another"})
                ws.receive_json()

            mock_update_task.assert_called_once()
            call_args = mock_update_task.call_args.args
            assert call_args[1] == task_id
            assert call_args[2] == "awaiting_user"
    finally:
        app.dependency_overrides.clear()


def test_ws_approve_sets_task_in_progress():
    """When approve is sent, task status is updated to in_progress."""
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _make_session_mock(session_id, task_id=task_id)
    g = _capturing_graph()

    mock_update_task = AsyncMock()

    _override_db_with_mock()
    try:
        with (
            patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
            patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
            patch(f"{WS}.runtime") as mock_runtime,
            patch(f"{WS}.add_message", new_callable=AsyncMock),
            patch(f"{WS}.get_graph", return_value=g),
            patch(f"{WS}.stop_session", new_callable=AsyncMock),
            patch(f"{WS}.update_task_status", mock_update_task),
        ):
            mock_runtime.is_running.return_value = True
            mock_runtime.stop_session = AsyncMock()
            mock_runtime.get_children.return_value = set()

            client = TestClient(app)
            with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
                ws.send_json({"type": "message", "content": "start"})
                ws.send_json({"type": "approve"})
                ws.receive_json()  # done

            # First call: awaiting_user (after interrupt), second: in_progress (after approve)
            calls = mock_update_task.call_args_list
            statuses = [c.args[2] for c in calls]
            assert "awaiting_user" in statuses
            assert "in_progress" in statuses
    finally:
        app.dependency_overrides.clear()


def test_ws_no_task_id_skips_status_update():
    """When session has no task_id, _try_update_task_status is a no-op."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    session.task_id = None  # no task

    g = MagicMock()

    async def _astream(*args, **kwargs):
        yield {"__interrupt__": True}

    g.astream = _astream

    mock_update_task = AsyncMock()

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.add_message", new_callable=AsyncMock),
        patch(f"{WS}.get_graph", return_value=g),
        patch(f"{WS}.stop_session", new_callable=AsyncMock),
        patch(f"{WS}.update_task_status", mock_update_task),
    ):
        mock_runtime.is_running.return_value = True
        mock_runtime.stop_session = AsyncMock()
        mock_runtime.get_children.return_value = set()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "message", "content": "trigger"})
            ws.send_json({"type": "message", "content": "try again"})
            ws.receive_json()

        mock_update_task.assert_not_called()


def test_ws_graph_error_sets_task_error():
    """When graph raises an exception, task status is updated to error."""
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _make_session_mock(session_id, task_id=task_id)

    mock_update_task = AsyncMock()

    _override_db_with_mock()
    try:
        with (
            patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
            patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
            patch(f"{WS}.runtime") as mock_runtime,
            patch(f"{WS}.add_message", new_callable=AsyncMock),
            patch(f"{WS}.get_graph", return_value=_error_graph("LLM timeout")),
            patch(f"{WS}.stop_session", new_callable=AsyncMock),
            patch(f"{WS}.update_task_status", mock_update_task),
        ):
            mock_runtime.is_running.return_value = True
            mock_runtime.stop_session = AsyncMock()
            mock_runtime.get_children.return_value = set()

            client = TestClient(app)
            with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
                ws.send_json({"type": "message", "content": "hello"})
                ws.receive_json()  # error
                ws.receive_json()  # done

            mock_update_task.assert_called_once()
            assert mock_update_task.call_args.args[2] == "error"
    finally:
        app.dependency_overrides.clear()


def test_ws_try_update_task_status_swallows_http_exception():
    """_try_update_task_status silently handles HTTPException (invalid transition)."""
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _make_session_mock(session_id, task_id=task_id)

    g = MagicMock()

    async def _astream(*args, **kwargs):
        yield {"__interrupt__": True}

    g.astream = _astream

    mock_update_task = AsyncMock(side_effect=HTTPException(status_code=400, detail="Invalid transition"))

    _override_db_with_mock()
    try:
        with (
            patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
            patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
            patch(f"{WS}.runtime") as mock_runtime,
            patch(f"{WS}.add_message", new_callable=AsyncMock),
            patch(f"{WS}.get_graph", return_value=g),
            patch(f"{WS}.stop_session", new_callable=AsyncMock),
            patch(f"{WS}.update_task_status", mock_update_task),
        ):
            mock_runtime.is_running.return_value = True
            mock_runtime.stop_session = AsyncMock()
            mock_runtime.get_children.return_value = set()

            client = TestClient(app)
            with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
                ws.send_json({"type": "message", "content": "trigger"})
                # Should NOT crash — HTTPException is swallowed
                ws.send_json({"type": "message", "content": "another"})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "approval" in data["error"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Workdir resolution: task → product → workspace_path
# ---------------------------------------------------------------------------


def test_ws_workdir_from_task_product():
    """Workdir is resolved from session.task.product.workspace_path."""
    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = _make_session_mock(session_id, task_id=task_id)
    # Override default workspace_path
    session.task.product.workspace_path = "/projects/my-app"

    _override_db_with_mock()
    try:
        with (
            patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
            patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
            patch(f"{WS}.runtime") as mock_runtime,
            patch(f"{WS}.get_graph", return_value=_noop_graph()),
        ):
            mock_runtime.is_running.return_value = False
            mock_runtime.start_session = AsyncMock()
            mock_runtime.stop_session = AsyncMock()

            client = TestClient(app)
            with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
                ws.send_json({"type": "stop"})
                ws.receive_json()

            call_kwargs = mock_runtime.start_session.call_args.kwargs
            assert call_kwargs["workdir"] == "/projects/my-app"
    finally:
        app.dependency_overrides.clear()


def test_ws_workdir_fallback_to_agent_config():
    """When no task_id, workdir falls back to agent.config.workdir."""
    session_id = uuid.uuid4()
    session = _make_session_mock(session_id)
    session.task_id = None  # no task
    session.agent.config = {"workdir": "/fallback/path"}

    with (
        patch(f"{WS}.get_session", new_callable=AsyncMock, return_value=session),
        patch(f"{WS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
        patch(f"{WS}.runtime") as mock_runtime,
        patch(f"{WS}.get_graph", return_value=_noop_graph()),
    ):
        mock_runtime.is_running.return_value = False
        mock_runtime.start_session = AsyncMock()
        mock_runtime.stop_session = AsyncMock()

        client = TestClient(app)
        with client.websocket_connect(f"/api/ws/sessions/{session_id}") as ws:
            ws.send_json({"type": "stop"})
            ws.receive_json()

        call_kwargs = mock_runtime.start_session.call_args.kwargs
        assert call_kwargs["workdir"] == "/fallback/path"
