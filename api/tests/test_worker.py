"""Tests for app.worker — Task Worker session lifecycle and graph dispatch."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

WORKER = "app.worker"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_mock(session_id, agent_name="TestAgent", task_id=None):
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = agent_name
    agent.system_prompt = "You are a test agent."
    agent.config = {"workdir": "/tmp/test"}
    agent.allowed_tools = []

    session = MagicMock()
    session.id = session_id
    session.agent_id = agent.id
    session.agent = agent
    session.task_id = task_id
    session.claude_session_id = None
    return session


def _make_graph_mock(interrupted=False, completed=False, error=None):
    """Create a mock graph that returns predictable stream results."""
    graph = AsyncMock()

    async def fake_stream(input, config, stream_mode=None):
        if error:
            raise Exception(error)
        chunk = {"task": "test", "handoff_result": None}
        if interrupted:
            chunk["__interrupt__"] = True
        if completed:
            chunk["handoff_result"] = {"result_type": "completed"}
        yield chunk

    graph.astream = fake_stream
    state_mock = MagicMock()
    state_mock.next = [] if not interrupted else ["gate"]
    state_mock.values = {}
    graph.aget_state = AsyncMock(return_value=state_mock)
    return graph


# ---------------------------------------------------------------------------
# EventPublisher tests
# ---------------------------------------------------------------------------

class TestEventPublisher:
    @pytest.mark.asyncio
    @patch(f"{WORKER}.publish_event", new_callable=AsyncMock)
    async def test_send_json_publishes_to_redis(self, mock_publish):
        from app.worker import EventPublisher
        publisher = EventPublisher("test-session-id")
        await publisher.send_json({"type": "done"})
        mock_publish.assert_called_once_with("test-session-id", {"type": "done"})

    @pytest.mark.asyncio
    @patch(f"{WORKER}.publish_event", new_callable=AsyncMock)
    async def test_session_id_propagated(self, mock_publish):
        from app.worker import EventPublisher
        sid = str(uuid.uuid4())
        publisher = EventPublisher(sid)
        await publisher.send_json({"type": "status", "status": "thinking"})
        assert mock_publish.call_args[0][0] == sid


# ---------------------------------------------------------------------------
# _handle_graph_result tests
# ---------------------------------------------------------------------------

class TestHandleGraphResult:
    @pytest.mark.asyncio
    @patch(f"{WORKER}._try_update_task_status", new_callable=AsyncMock)
    async def test_errored_sends_done_returns_false(self, mock_update):
        from app.worker import _handle_graph_result, EventPublisher
        publisher = MagicMock(spec=EventPublisher)
        publisher.send_json = AsyncMock()

        result = await _handle_graph_result(
            publisher, MagicMock(), None,
            interrupted=False, completed=False, errored=True,
        )
        assert result is False
        publisher.send_json.assert_called_once_with({"type": "done"})

    @pytest.mark.asyncio
    @patch(f"{WORKER}._try_update_task_status", new_callable=AsyncMock)
    async def test_interrupted_returns_true_and_sends_approval(self, mock_update):
        from app.worker import _handle_graph_result, EventPublisher
        publisher = MagicMock(spec=EventPublisher)
        publisher.send_json = AsyncMock()
        task_id = uuid.uuid4()

        last_state = {
            "handoff_result": {"to_agent_name": "Reviewer", "prompt": "Review this"},
            "current_agent_name": "Coder",
            "chain": [],
            "messages": [],
        }

        result = await _handle_graph_result(
            publisher, MagicMock(), task_id,
            interrupted=True, completed=False, errored=False,
            last_state=last_state,
        )
        assert result is True
        # Should send approval_required event
        sent = publisher.send_json.call_args[0][0]
        assert sent["type"] == "approval_required"
        assert sent["to_agent"] == "Reviewer"

    @pytest.mark.asyncio
    @patch(f"{WORKER}._try_update_task_status", new_callable=AsyncMock)
    async def test_completed_sends_done(self, mock_update):
        from app.worker import _handle_graph_result, EventPublisher
        publisher = MagicMock(spec=EventPublisher)
        publisher.send_json = AsyncMock()
        task_id = uuid.uuid4()

        result = await _handle_graph_result(
            publisher, MagicMock(), task_id,
            interrupted=False, completed=True, errored=False,
        )
        assert result is False
        publisher.send_json.assert_called_once_with({"type": "done"})


# ---------------------------------------------------------------------------
# _try_update_task_status tests
# ---------------------------------------------------------------------------

class TestTryUpdateTaskStatus:
    @pytest.mark.asyncio
    @patch(f"{WORKER}.update_task_status", new_callable=AsyncMock)
    async def test_skips_if_no_task_id(self, mock_update):
        from app.worker import _try_update_task_status
        await _try_update_task_status(MagicMock(), None, "done")
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{WORKER}.update_task_status", new_callable=AsyncMock)
    async def test_calls_update_with_correct_args(self, mock_update):
        from app.worker import _try_update_task_status
        db = MagicMock()
        task_id = uuid.uuid4()
        await _try_update_task_status(db, task_id, "awaiting_user")
        mock_update.assert_called_once_with(db, task_id, "awaiting_user")

    @pytest.mark.asyncio
    @patch(f"{WORKER}.update_task_status", new_callable=AsyncMock, side_effect=Exception("DB error"))
    async def test_suppresses_errors(self, mock_update):
        """Errors should be logged, not raised — auto-update must not crash session."""
        from app.worker import _try_update_task_status
        await _try_update_task_status(MagicMock(), uuid.uuid4(), "error")


# ---------------------------------------------------------------------------
# _run_graph tests
# ---------------------------------------------------------------------------

class TestRunGraph:
    @pytest.mark.asyncio
    @patch(f"{WORKER}.publish_notification", new_callable=AsyncMock)
    @patch(f"{WORKER}._try_update_task_status", new_callable=AsyncMock)
    async def test_normal_completion(self, mock_status, mock_notif):
        from app.worker import _run_graph, EventPublisher
        publisher = MagicMock(spec=EventPublisher)
        publisher.send_json = AsyncMock()

        graph = _make_graph_mock(completed=True)
        config = {"configurable": {
            "thread_id": "test", "websocket": publisher, "db": MagicMock(), "task_id": None
        }, "recursion_limit": 20}

        interrupted, completed, errored, state = await _run_graph(graph, {}, config)
        assert not interrupted
        assert completed
        assert not errored

    @pytest.mark.asyncio
    @patch(f"{WORKER}.publish_notification", new_callable=AsyncMock)
    @patch(f"{WORKER}._try_update_task_status", new_callable=AsyncMock)
    async def test_graph_error_publishes_error_event(self, mock_status, mock_notif):
        from app.worker import _run_graph, EventPublisher
        publisher = MagicMock(spec=EventPublisher)
        publisher.send_json = AsyncMock()

        graph = _make_graph_mock(error="LangGraph exploded")
        config = {"configurable": {
            "thread_id": "test", "websocket": publisher, "db": MagicMock(), "task_id": uuid.uuid4()
        }, "recursion_limit": 20}

        interrupted, completed, errored, state = await _run_graph(graph, {}, config)
        assert errored
        assert not interrupted
        assert not completed
        publisher.send_json.assert_called()
        error_event = publisher.send_json.call_args[0][0]
        assert error_event["type"] == "error"
        assert "LangGraph exploded" in error_event["error"]


# ---------------------------------------------------------------------------
# handle_session cleanup tests
# ---------------------------------------------------------------------------

class TestHandleSessionCleanup:
    @pytest.mark.asyncio
    @patch(f"{WORKER}.clear_buffer", new_callable=AsyncMock)
    @patch(f"{WORKER}.runtime")
    @patch(f"{WORKER}.async_session")
    @patch(f"{WORKER}.get_session", new_callable=AsyncMock, side_effect=Exception("boom"))
    @patch(f"{WORKER}.publish_event", new_callable=AsyncMock)
    async def test_cleanup_runs_on_crash(
        self, mock_publish, mock_get_session, mock_async_session, mock_runtime, mock_clear
    ):
        """Cleanup (stop_session, clear_buffer) must run even if _run_session crashes."""
        from app.worker import handle_session

        mock_runtime.get_children.return_value = []
        mock_runtime.stop_session = AsyncMock()

        # Mock async_session context manager
        mock_db = AsyncMock()
        mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

        session_id = uuid.uuid4()
        await handle_session(session_id)

        # Cleanup should always run
        mock_runtime.stop_session.assert_called_once_with(session_id)
        mock_clear.assert_called_once_with(str(session_id))
