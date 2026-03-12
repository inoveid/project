"""Tests for app.services.graph_service — LangGraph nodes and routing (P5).

Synced with graph_service.py as of 2026-03-12:
- notify_handoff_node, complete_node, blocked_node use publish_notification (Redis),
  NOT ws.send_json
- auto_handoff_node delegates to _create_sub_session (no cycle detection in this layer)
- _has_repeated_cycle does not exist in graph_service.py
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.graph_service import (
    END,
    MAX_DEPTH,
    WorkflowState,
    auto_handoff_node,
    blocked_node,
    complete_node,
    gate_node,
    notify_handoff_node,
    route_after_agent,
    route_after_gate,
    run_agent_node,
    _get_configurable,
    _serialize_handoff_result,
    _build_sub_agent_prompt,
    _resolve_sub_agent_workdir,
)
from app.services.handoff_server import HandoffResult, HandoffResultType

GS = "app.services.graph_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    """Create a minimal WorkflowState with sensible defaults."""
    base: WorkflowState = {
        "main_session_id": str(uuid.uuid4()),
        "current_session_id": str(uuid.uuid4()),
        "current_agent_id": str(uuid.uuid4()),
        "current_agent_name": "Dev",
        "workflow_id": str(uuid.uuid4()),
        "task_id": str(uuid.uuid4()),
        "task": "Implement feature",
        "depth": 0,
        "chain": [],
        "handoff_result": None,
        "gateway_approved": None,
        "product_workspace": None,
        "messages": [],
    }
    base.update(overrides)
    return base


def _make_config(ws=None, db=None, task_id=None) -> dict:
    """Create a RunnableConfig-like dict with GraphConfigurable keys."""
    return {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "websocket": ws or AsyncMock(),
            "db": db or AsyncMock(),
            "task_id": task_id,
        },
    }


def _make_handoff_result(**overrides) -> dict:
    """Create a serialized HandoffResult dict with result_type as string value."""
    base = {
        "result_type": HandoffResultType.FORWARDED.value,
        "reason": "",
        "to_agent_id": str(uuid.uuid4()),
        "to_agent_name": "Reviewer",
        "prompt": "Please review",
        "edge_id": str(uuid.uuid4()),
        "requires_approval": True,
        "tool_args": {"comment": "Review this"},
    }
    base.update(overrides)
    return base


# ===========================================================================
# route_after_agent
# ===========================================================================


class TestRouteAfterAgent:
    def test_no_handoff_result(self):
        state = _make_state(handoff_result=None)
        assert route_after_agent(state) == END

    def test_awaiting_approval(self):
        hr = _make_handoff_result(result_type=HandoffResultType.AWAITING_APPROVAL.value)
        state = _make_state(handoff_result=hr)
        assert route_after_agent(state) == "notify_handoff"

    def test_auto_forward(self):
        hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
        state = _make_state(handoff_result=hr)
        assert route_after_agent(state) == "auto_handoff"

    def test_completed(self):
        hr = _make_handoff_result(result_type=HandoffResultType.COMPLETED.value)
        state = _make_state(handoff_result=hr)
        assert route_after_agent(state) == "complete"

    def test_blocked(self):
        hr = _make_handoff_result(result_type=HandoffResultType.BLOCKED.value)
        state = _make_state(handoff_result=hr)
        assert route_after_agent(state) == "blocked"

    def test_max_depth_returns_end(self):
        hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
        state = _make_state(handoff_result=hr, depth=MAX_DEPTH)
        assert route_after_agent(state) == END

    def test_depth_below_max_routes_normally(self):
        hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
        state = _make_state(handoff_result=hr, depth=MAX_DEPTH - 1)
        assert route_after_agent(state) == "auto_handoff"

    def test_unknown_result_type_returns_end(self):
        hr = _make_handoff_result(result_type="some_unknown_type")
        state = _make_state(handoff_result=hr)
        assert route_after_agent(state) == END


# ===========================================================================
# route_after_gate
# ===========================================================================


class TestRouteAfterGate:
    def test_approved(self):
        state = _make_state(gateway_approved=True)
        assert route_after_gate(state) == "run_agent"

    def test_rejected(self):
        state = _make_state(gateway_approved=False)
        assert route_after_gate(state) == END

    def test_none(self):
        state = _make_state(gateway_approved=None)
        assert route_after_gate(state) == END


# ===========================================================================
# _get_configurable
# ===========================================================================


class TestGetConfigurable:
    def test_extracts_configurable(self):
        config = _make_config()
        cfg = _get_configurable(config)
        assert "thread_id" in cfg
        assert "websocket" in cfg
        assert "db" in cfg


# ===========================================================================
# _serialize_handoff_result
# ===========================================================================


class TestSerializeHandoffResult:
    def test_none_returns_none(self):
        assert _serialize_handoff_result(None) is None

    def test_serializes_all_fields(self):
        agent_id = uuid.uuid4()
        edge_id = uuid.uuid4()
        hr = HandoffResult(
            result_type=HandoffResultType.FORWARDED,
            reason="test reason",
            to_agent_id=agent_id,
            to_agent_name="Reviewer",
            prompt="Review this",
            edge_id=edge_id,
            requires_approval=True,
            tool_args={"comment": "please"},
        )
        result = _serialize_handoff_result(hr)

        assert result["result_type"] == "forwarded"
        assert result["reason"] == "test reason"
        assert result["to_agent_id"] == str(agent_id)
        assert result["to_agent_name"] == "Reviewer"
        assert result["prompt"] == "Review this"
        assert result["edge_id"] == str(edge_id)
        assert result["requires_approval"] is True
        assert result["tool_args"] == {"comment": "please"}

    def test_none_ids_serialize_as_none(self):
        hr = HandoffResult(
            result_type=HandoffResultType.COMPLETED,
            to_agent_id=None,
            edge_id=None,
        )
        result = _serialize_handoff_result(hr)
        assert result["to_agent_id"] is None
        assert result["edge_id"] is None


# ===========================================================================
# _resolve_sub_agent_workdir
# ===========================================================================


class TestResolveSubAgentWorkdir:
    def test_product_workspace_takes_priority(self):
        target = MagicMock()
        target.config = {"workdir": "/agent/dir"}
        state = _make_state(product_workspace="/product/ws")
        assert _resolve_sub_agent_workdir(target, state) == "/product/ws"

    def test_agent_config_workdir_when_no_product_ws(self):
        target = MagicMock()
        target.config = {"workdir": "/agent/dir"}
        state = _make_state(product_workspace=None)
        assert _resolve_sub_agent_workdir(target, state) == "/agent/dir"

    @patch(f"{GS}.settings")
    def test_falls_back_to_settings(self, mock_settings):
        mock_settings.workspace_path = "/default/workspace"
        target = MagicMock()
        target.config = None
        state = _make_state(product_workspace=None)
        assert _resolve_sub_agent_workdir(target, state) == "/default/workspace"

    @patch(f"{GS}.settings")
    def test_empty_workdir_falls_back(self, mock_settings):
        mock_settings.workspace_path = "/default/workspace"
        target = MagicMock()
        target.config = {"workdir": ""}
        state = _make_state(product_workspace=None)
        assert _resolve_sub_agent_workdir(target, state) == "/default/workspace"


# ===========================================================================
# _build_sub_agent_prompt
# ===========================================================================


class TestBuildSubAgentPrompt:
    def test_includes_system_prompt(self):
        target = MagicMock()
        target.system_prompt = "You are a reviewer."
        target.name = "Reviewer"
        state = _make_state(current_agent_name="Coder", chain=[])
        result = _build_sub_agent_prompt(target, state, "")
        assert result.startswith("You are a reviewer.")

    def test_appends_tools_prompt(self):
        target = MagicMock()
        target.system_prompt = "Base prompt."
        target.name = "Reviewer"
        state = _make_state(chain=[])
        result = _build_sub_agent_prompt(target, state, "\n## Tools\nforward_to_qa")
        assert "## Tools" in result
        assert "forward_to_qa" in result

    def test_includes_chain_context(self):
        target = MagicMock()
        target.system_prompt = "Prompt."
        target.name = "QA"
        state = _make_state(
            current_agent_name="Reviewer",
            chain=[["Coder", "Reviewer"]],
        )
        result = _build_sub_agent_prompt(target, state, "")
        assert "Handoff Chain Context" in result
        assert "Coder\u2192Reviewer" in result
        assert "Reviewer\u2192QA" in result


# ===========================================================================
# MAX_DEPTH constant
# ===========================================================================


class TestConstants:
    def test_max_depth_is_positive(self):
        assert MAX_DEPTH > 0

    def test_max_depth_is_reasonable(self):
        assert MAX_DEPTH <= 20


# ===========================================================================
# notify_handoff_node — uses publish_notification (Redis), NOT ws
# ===========================================================================


class TestNotifyHandoffNode:
    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_publishes_approval_required(self, mock_notify):
        hr = _make_handoff_result(
            result_type=HandoffResultType.AWAITING_APPROVAL.value,
            to_agent_name="Reviewer",
            prompt="Review PR",
        )
        state = _make_state(current_agent_name="Dev", handoff_result=hr)
        config = _make_config()

        result = await notify_handoff_node(state, config)

        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0] == "approval_required"
        assert args[1]["from_agent"] == "Dev"
        assert args[1]["to_agent"] == "Reviewer"
        assert args[1]["task"] == "Review PR"

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_returns_empty_dict(self, mock_notify):
        state = _make_state(handoff_result=_make_handoff_result())
        result = await notify_handoff_node(state, _make_config())
        assert result == {}

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_includes_task_id(self, mock_notify):
        state = _make_state(
            handoff_result=_make_handoff_result(),
            task_id="task-42",
        )
        await notify_handoff_node(state, _make_config())
        event_data = mock_notify.call_args[0][1]
        assert event_data["task_id"] == "task-42"


# ===========================================================================
# complete_node — uses publish_notification (Redis), NOT ws
# ===========================================================================


class TestCompleteNode:
    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_publishes_task_completed(self, mock_notify):
        hr = _make_handoff_result(
            result_type=HandoffResultType.COMPLETED.value,
            tool_args={"summary": "All done"},
        )
        state = _make_state(handoff_result=hr, current_agent_name="Dev")
        result = await complete_node(state, _make_config())

        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0] == "task_completed"
        assert args[1]["summary"] == "All done"
        assert args[1]["agent_name"] == "Dev"

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_clears_handoff_state(self, mock_notify):
        state = _make_state(handoff_result=_make_handoff_result())
        result = await complete_node(state, _make_config())
        assert result["handoff_result"] is None
        assert result["gateway_approved"] is None

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_no_handoff_result_empty_summary(self, mock_notify):
        state = _make_state(handoff_result=None)
        await complete_node(state, _make_config())
        args = mock_notify.call_args[0]
        assert args[1]["summary"] == ""


# ===========================================================================
# blocked_node — uses publish_notification (Redis), NOT ws
# ===========================================================================


class TestBlockedNode:
    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_publishes_max_cycles_reached(self, mock_notify):
        hr = _make_handoff_result(
            result_type=HandoffResultType.BLOCKED.value,
            reason="max_cycles (3) reached for agent Dev",
            to_agent_name="Dev",
        )
        state = _make_state(handoff_result=hr)
        result = await blocked_node(state, _make_config())

        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert args[0] == "max_cycles_reached"
        assert args[1]["agent_name"] == "Dev"
        assert "max_cycles" in args[1]["reason"]

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_clears_handoff_state(self, mock_notify):
        state = _make_state(handoff_result=_make_handoff_result())
        result = await blocked_node(state, _make_config())
        assert result["handoff_result"] is None
        assert result["gateway_approved"] is None

    @pytest.mark.asyncio
    @patch(f"{GS}.publish_notification", new_callable=AsyncMock)
    async def test_no_handoff_result_uses_unknown(self, mock_notify):
        state = _make_state(handoff_result=None)
        await blocked_node(state, _make_config())
        args = mock_notify.call_args[0]
        assert args[1]["reason"] == "unknown"
        assert args[1]["agent_name"] == ""


# ===========================================================================
# gate_node
# ===========================================================================


class TestGateNode:
    @pytest.mark.asyncio
    @patch(f"{GS}.interrupt", return_value=False)
    async def test_reject_clears_handoff(self, mock_interrupt):
        hr = _make_handoff_result(result_type=HandoffResultType.AWAITING_APPROVAL.value)
        state = _make_state(handoff_result=hr)
        result = await gate_node(state, _make_config())

        assert result["gateway_approved"] is False
        assert result["handoff_result"] is None

    @pytest.mark.asyncio
    @patch(f"{GS}.interrupt", return_value=True)
    async def test_approve_no_target_returns_false(self, mock_interrupt):
        hr = _make_handoff_result(to_agent_id=None)
        state = _make_state(handoff_result=hr)
        result = await gate_node(state, _make_config())
        assert result["gateway_approved"] is False

    @pytest.mark.asyncio
    @patch(f"{GS}.interrupt", return_value=True)
    async def test_approve_no_handoff_result_returns_false(self, mock_interrupt):
        state = _make_state(handoff_result=None)
        result = await gate_node(state, _make_config())
        assert result["gateway_approved"] is False

    @pytest.mark.asyncio
    @patch(f"{GS}._create_sub_session", new_callable=AsyncMock)
    @patch(f"{GS}.interrupt", return_value=True)
    async def test_approve_delegates_to_create_sub_session(self, mock_interrupt, mock_create):
        mock_create.return_value = {
            "gateway_approved": True,
            "current_session_id": "new-sid",
            "current_agent_name": "Reviewer",
            "depth": 1,
        }
        ws = AsyncMock()
        db = AsyncMock()
        hr = _make_handoff_result(
            result_type=HandoffResultType.AWAITING_APPROVAL.value,
            to_agent_id=str(uuid.uuid4()),
            to_agent_name="Reviewer",
        )
        state = _make_state(handoff_result=hr)
        config = _make_config(ws=ws, db=db)

        result = await gate_node(state, config)

        mock_create.assert_called_once_with(db, ws, state, hr)
        assert result["gateway_approved"] is True
        assert result["current_agent_name"] == "Reviewer"


# ===========================================================================
# auto_handoff_node
# ===========================================================================


class TestAutoHandoffNode:
    @pytest.mark.asyncio
    async def test_no_handoff_result_returns_false(self):
        state = _make_state(handoff_result=None)
        result = await auto_handoff_node(state, _make_config())
        assert result["gateway_approved"] is False

    @pytest.mark.asyncio
    async def test_no_target_agent_returns_false(self):
        hr = _make_handoff_result(to_agent_id=None)
        state = _make_state(handoff_result=hr)
        result = await auto_handoff_node(state, _make_config())
        assert result["gateway_approved"] is False

    @pytest.mark.asyncio
    @patch(f"{GS}._create_sub_session", new_callable=AsyncMock)
    async def test_delegates_to_create_sub_session(self, mock_create):
        mock_create.return_value = {"gateway_approved": True, "depth": 1}
        ws = AsyncMock()
        db = AsyncMock()
        hr = _make_handoff_result(
            result_type=HandoffResultType.FORWARDED.value,
            to_agent_id=str(uuid.uuid4()),
        )
        state = _make_state(handoff_result=hr)
        config = _make_config(ws=ws, db=db)

        result = await auto_handoff_node(state, config)
        mock_create.assert_called_once_with(db, ws, state, hr)
        assert result["gateway_approved"] is True


# ===========================================================================
# run_agent_node — main agent (depth=0)
# ===========================================================================


class TestRunAgentNodeMain:
    @pytest.mark.asyncio
    async def test_streams_events_to_ws(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )
        config = _make_config(ws=ws, db=db)

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "Hello "}
            yield {"type": "assistant_text", "content": "world"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            result = await run_agent_node(state, config)

        assert ws.send_json.call_count == 2
        sent = [c.args[0] for c in ws.send_json.call_args_list]
        assert sent[0] == {"type": "assistant_text", "content": "Hello "}
        assert sent[1] == {"type": "assistant_text", "content": "world"}

    @pytest.mark.asyncio
    async def test_saves_response_to_db(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )
        config = _make_config(ws=ws, db=db)

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "Result text"}

        mock_add = AsyncMock()
        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", mock_add),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            await run_agent_node(state, config)

        mock_add.assert_called_once()
        args = mock_add.call_args
        assert args.args[1] == session_id
        assert args.args[2] == "assistant"
        assert "Result text" in args.args[3]

    @pytest.mark.asyncio
    async def test_resolves_handoff_and_serializes(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )

        mock_hr = HandoffResult(
            result_type=HandoffResultType.FORWARDED,
            to_agent_name="Reviewer",
            prompt="Review it",
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "Done"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=mock_hr),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            result = await run_agent_node(state, _make_config(ws=ws, db=db))

        assert result["handoff_result"]["result_type"] == "forwarded"
        assert result["handoff_result"]["to_agent_name"] == "Reviewer"

    @pytest.mark.asyncio
    async def test_collects_tool_uses(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )

        async def fake_send(sid, content):
            yield {"type": "tool_use", "tool_name": "read_file", "tool_input": {"path": "/x"}}
            yield {"type": "assistant_text", "content": "Done"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            result = await run_agent_node(state, _make_config(ws=ws, db=db))

        assert len(result["messages"][0]["tools"]) == 1
        assert result["messages"][0]["tools"][0]["tool_name"] == "read_file"

    @pytest.mark.asyncio
    async def test_preserves_existing_messages(self):
        ws = AsyncMock()
        db = AsyncMock()
        existing = {"agent": "OldAgent", "text": "old", "tools": []}
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
            messages=[existing],
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "new"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            result = await run_agent_node(state, _make_config(ws=ws, db=db))

        assert len(result["messages"]) == 2
        assert result["messages"][0] == existing
        assert result["messages"][1]["text"] == "new"

    @pytest.mark.asyncio
    async def test_saves_claude_session_id(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "reply"}

        mock_session = MagicMock()
        mock_session.claude_session_id = None

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}.get_session", new_callable=AsyncMock, return_value=mock_session),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = "claude-abc-123"
            await run_agent_node(state, _make_config(ws=ws, db=db))

        assert mock_session.claude_session_id == "claude-abc-123"
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_response_not_saved(self):
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )

        async def fake_send(sid, content):
            yield {"type": "result", "cost_usd": 0.01}

        mock_add = AsyncMock()
        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", mock_add),
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.get_claude_session_id.return_value = None
            await run_agent_node(state, _make_config(ws=ws, db=db))

        mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_returns_early_no_handoff(self):
        """On error, node returns early -- no DB save, no handoff resolution."""
        ws = AsyncMock()
        db = AsyncMock()
        session_id = uuid.uuid4()
        state = _make_state(
            current_session_id=str(session_id),
            main_session_id=str(session_id),
            depth=0,
        )

        async def failing_send(sid, content):
            raise RuntimeError("API rate limit")
            yield  # noqa: unreachable

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock) as mock_add,
            patch(f"{GS}.get_session", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock) as mock_resolve,
        ):
            mock_runtime.send_message = failing_send
            result = await run_agent_node(state, _make_config(ws=ws, db=db))

        # Error event sent to WS
        sent = [c.args[0] for c in ws.send_json.call_args_list]
        errors = [e for e in sent if e.get("type") == "error"]
        assert len(errors) == 1
        assert "rate limit" in errors[0]["error"].lower()

        # Early return: no DB save, no handoff
        mock_add.assert_not_called()
        mock_resolve.assert_not_called()
        assert result["handoff_result"] is None


# ===========================================================================
# run_agent_node — sub-agent (depth > 0)
# ===========================================================================


class TestRunAgentNodeSub:
    @pytest.mark.asyncio
    async def test_prefixes_events_with_sub_agent(self):
        ws = AsyncMock()
        db = AsyncMock()
        main_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        state = _make_state(
            main_session_id=str(main_id),
            current_session_id=str(sub_id),
            current_agent_name="SubAgent",
            depth=1,
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "hello"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.stop_session = AsyncMock()
            await run_agent_node(state, _make_config(ws=ws, db=db))

        first = ws.send_json.call_args_list[0].args[0]
        assert first["type"] == "sub_agent_assistant_text"
        assert first["agent_name"] == "SubAgent"

    @pytest.mark.asyncio
    async def test_stops_runtime_and_sends_handoff_done(self):
        ws = AsyncMock()
        db = AsyncMock()
        main_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        state = _make_state(
            main_session_id=str(main_id),
            current_session_id=str(sub_id),
            depth=1,
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "result"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.stop_session = AsyncMock()
            await run_agent_node(state, _make_config(ws=ws, db=db))

        mock_runtime.stop_session.assert_called_once_with(sub_id)
        sent = [c.args[0] for c in ws.send_json.call_args_list]
        done = [e for e in sent if e.get("type") == "handoff_done"]
        assert len(done) == 1

    @pytest.mark.asyncio
    async def test_duplicates_message_to_main_session(self):
        ws = AsyncMock()
        db = AsyncMock()
        main_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        state = _make_state(
            main_session_id=str(main_id),
            current_session_id=str(sub_id),
            current_agent_name="SubAgent",
            depth=1,
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "sub result"}

        mock_add = AsyncMock()
        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", mock_add),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.stop_session = AsyncMock()
            await run_agent_node(state, _make_config(ws=ws, db=db))

        # Two add_message calls: sub session + main session
        assert mock_add.call_count == 2
        main_call = mock_add.call_args_list[1]
        assert main_call.args[1] == main_id
        assert "[SubAgent]" in main_call.args[3]

    @pytest.mark.asyncio
    async def test_error_sends_sub_agent_error(self):
        ws = AsyncMock()
        db = AsyncMock()
        main_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        state = _make_state(
            main_session_id=str(main_id),
            current_session_id=str(sub_id),
            current_agent_name="SubAgent",
            depth=1,
        )

        async def failing_send(sid, content):
            raise RuntimeError("crashed")
            yield

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
        ):
            mock_runtime.send_message = failing_send
            mock_runtime.stop_session = AsyncMock()
            result = await run_agent_node(state, _make_config(ws=ws, db=db))

        sent = [c.args[0] for c in ws.send_json.call_args_list]
        errors = [e for e in sent if e.get("type") == "sub_agent_error"]
        assert len(errors) == 1
        assert errors[0]["agent_name"] == "SubAgent"

        # handoff_done still sent (finally block)
        done = [e for e in sent if e.get("type") == "handoff_done"]
        assert len(done) == 1

    @pytest.mark.asyncio
    async def test_runtime_cleanup_failure_still_sends_handoff_done(self):
        """try/finally ensures handoff_done even if runtime.stop_session fails."""
        ws = AsyncMock()
        db = AsyncMock()
        main_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        state = _make_state(
            main_session_id=str(main_id),
            current_session_id=str(sub_id),
            depth=1,
        )

        async def fake_send(sid, content):
            yield {"type": "assistant_text", "content": "ok"}

        with (
            patch(f"{GS}.runtime") as mock_runtime,
            patch(f"{GS}.add_message", new_callable=AsyncMock),
            patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
        ):
            mock_runtime.send_message = fake_send
            mock_runtime.stop_session = AsyncMock(side_effect=RuntimeError("cleanup failed"))
            await run_agent_node(state, _make_config(ws=ws, db=db))

        sent = [c.args[0] for c in ws.send_json.call_args_list]
        done = [e for e in sent if e.get("type") == "handoff_done"]
        assert len(done) == 1


# ===========================================================================
# build_graph
# ===========================================================================


class TestBuildGraph:
    def test_has_all_nodes(self):
        from app.services.graph_service import build_graph
        checkpointer = MagicMock()
        graph = build_graph(checkpointer)

        node_names = set(graph.nodes.keys())
        expected = {"run_agent", "notify_handoff", "gate", "auto_handoff", "complete", "blocked"}
        assert expected.issubset(node_names), f"Missing: {expected - node_names}"
