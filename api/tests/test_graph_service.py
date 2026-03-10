"""Tests for app.services.graph_service — LangGraph nodes and routing (P5)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.graph_service import (
    END,
    MAX_DEPTH,
    WorkflowState,
    _has_repeated_cycle,
    auto_handoff_node,
    blocked_node,
    complete_node,
    gate_node,
    notify_handoff_node,
    route_after_agent,
    route_after_gate,
    run_agent_node,
)
from app.services.handoff_server import HandoffResultType

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
        "messages": [],
    }
    base.update(overrides)
    return base


def _make_config(ws=None, db=None) -> dict:
    """Create a RunnableConfig-like dict with configurable keys."""
    return {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "websocket": ws or AsyncMock(),
            "db": db or AsyncMock(),
        },
    }


def _make_handoff_result(**overrides) -> dict:
    """Create a serialized HandoffResult dict with result_type enum."""
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


# ---------------------------------------------------------------------------
# route_after_agent
# ---------------------------------------------------------------------------


def test_route_after_agent_no_handoff():
    state = _make_state(handoff_result=None)
    assert route_after_agent(state) == END


def test_route_after_agent_awaiting_approval():
    hr = _make_handoff_result(result_type=HandoffResultType.AWAITING_APPROVAL.value)
    state = _make_state(handoff_result=hr)
    assert route_after_agent(state) == "notify_handoff"


def test_route_after_agent_auto_forward():
    hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
    state = _make_state(handoff_result=hr)
    assert route_after_agent(state) == "auto_handoff"


def test_route_after_agent_completed():
    hr = _make_handoff_result(result_type=HandoffResultType.COMPLETED.value)
    state = _make_state(handoff_result=hr)
    assert route_after_agent(state) == "complete"


def test_route_after_agent_blocked():
    hr = _make_handoff_result(result_type=HandoffResultType.BLOCKED.value)
    state = _make_state(handoff_result=hr)
    assert route_after_agent(state) == "blocked"


def test_route_after_agent_max_depth():
    hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
    state = _make_state(handoff_result=hr, depth=MAX_DEPTH)
    assert route_after_agent(state) == END


def test_route_after_agent_depth_below_max():
    hr = _make_handoff_result(result_type=HandoffResultType.FORWARDED.value)
    state = _make_state(handoff_result=hr, depth=MAX_DEPTH - 1)
    assert route_after_agent(state) == "auto_handoff"


# ---------------------------------------------------------------------------
# route_after_gate
# ---------------------------------------------------------------------------


def test_route_after_gate_approved():
    state = _make_state(gateway_approved=True)
    assert route_after_gate(state) == "run_agent"


def test_route_after_gate_rejected():
    state = _make_state(gateway_approved=False)
    assert route_after_gate(state) == END


def test_route_after_gate_none():
    state = _make_state(gateway_approved=None)
    assert route_after_gate(state) == END


# ---------------------------------------------------------------------------
# _has_repeated_cycle (P8)
# ---------------------------------------------------------------------------


def test_has_repeated_cycle_detects_repeat():
    chain = [["Dev", "Reviewer"], ["Reviewer", "Dev"]]
    assert _has_repeated_cycle(chain, "Dev", "Reviewer") is True


def test_has_repeated_cycle_no_repeat():
    chain = [["Dev", "Reviewer"]]
    assert _has_repeated_cycle(chain, "Reviewer", "QA") is False


def test_has_repeated_cycle_empty_chain():
    assert _has_repeated_cycle([], "Dev", "Reviewer") is False


# ---------------------------------------------------------------------------
# run_agent_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_node_streams_events():
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    state = _make_state(current_session_id=str(session_id), depth=0)
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "Hello "}
        yield {"type": "assistant_text", "content": "world"}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    assert ws.send_json.call_count == 2
    sent_events = [call.args[0] for call in ws.send_json.call_args_list]
    assert sent_events[0] == {"type": "assistant_text", "content": "Hello "}
    assert sent_events[1] == {"type": "assistant_text", "content": "world"}


@pytest.mark.asyncio
async def test_run_agent_node_saves_response():
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    state = _make_state(current_session_id=str(session_id), depth=0)
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "Result text"}
        yield {"type": "result", "cost_usd": 0.01}

    mock_add = AsyncMock()
    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", mock_add),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        await run_agent_node(state, config)

    mock_add.assert_called_once()
    args = mock_add.call_args
    assert args.args[1] == session_id
    assert args.args[2] == "assistant"
    assert "Result text" in args.args[3]


@pytest.mark.asyncio
async def test_run_agent_node_resolves_handoff():
    """Node resolves handoff via _resolve_handoff and returns serialized result."""
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    state = _make_state(current_session_id=str(session_id), depth=0)
    config = _make_config(ws=ws, db=db)

    from app.services.handoff_server import HandoffResult
    mock_hr = HandoffResult(
        result_type=HandoffResultType.FORWARDED,
        to_agent_name="Reviewer",
        prompt="Review it",
    )

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "Done"}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=mock_hr),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    assert result["handoff_result"]["result_type"] == "forwarded"
    assert result["handoff_result"]["to_agent_name"] == "Reviewer"


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_cleanup():
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    main_session_id = uuid.uuid4()
    state = _make_state(
        current_session_id=str(session_id),
        main_session_id=str(main_session_id),
        depth=1,
        current_agent_name="SubAgent",
    )
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "Sub result"}

    mock_stop = AsyncMock()
    mock_add = AsyncMock()

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", mock_add),
        patch(f"{GS}.stop_session", mock_stop),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    mock_runtime.stop_session.assert_called_once_with(session_id)
    mock_stop.assert_called_once_with(db, session_id)
    sent = [c.args[0] for c in ws.send_json.call_args_list]
    handoff_done = [e for e in sent if e.get("type") == "handoff_done"]
    assert len(handoff_done) == 1


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_prefixes_events():
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=1, current_agent_name="SubAgent")
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "hello"}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.stop_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    first_event = ws.send_json.call_args_list[0].args[0]
    assert first_event["type"] == "sub_agent_assistant_text"
    assert first_event["agent_name"] == "SubAgent"


@pytest.mark.asyncio
async def test_run_agent_node_error_returns_early():
    """P6: On error, node returns early with no handoff — graph routes to END."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=0)
    config = _make_config(ws=ws, db=db)

    async def failing_send_message(sid, content):
        raise RuntimeError("API rate limit")
        yield  # noqa: unreachable

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock) as mock_add,
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_runtime.send_message = failing_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    # Error event sent
    sent = [c.args[0] for c in ws.send_json.call_args_list]
    error_events = [e for e in sent if e.get("type") == "error"]
    assert len(error_events) == 1
    assert "rate limit" in error_events[0]["error"].lower()

    # Early return: no DB save, no handoff resolution
    mock_add.assert_not_called()
    mock_resolve.assert_not_called()
    assert result["handoff_result"] is None


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_cleanup_on_error():
    """P7: Sub-agent cleanup uses try/finally — handoff_done always sent."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=1, current_agent_name="SubAgent")
    config = _make_config(ws=ws, db=db)

    async def failing_send_message(sid, content):
        raise RuntimeError("Sub-agent crashed")
        yield  # noqa: unreachable

    mock_stop = AsyncMock(side_effect=RuntimeError("Cleanup also failed"))

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.stop_session", mock_stop),
    ):
        mock_runtime.send_message = failing_send_message
        mock_runtime.stop_session = AsyncMock()

        result = await run_agent_node(state, config)

    # handoff_done sent even though cleanup failed
    sent = [c.args[0] for c in ws.send_json.call_args_list]
    handoff_done = [e for e in sent if e.get("type") == "handoff_done"]
    assert len(handoff_done) == 1
    assert result["handoff_result"] is None


@pytest.mark.asyncio
async def test_run_agent_node_empty_response_not_saved():
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=0)
    config = _make_config(ws=ws, db=db)

    async def empty_send_message(sid, content):
        yield {"type": "result", "cost_usd": 0.01}

    mock_add = AsyncMock()
    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", mock_add),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = empty_send_message
        mock_runtime.get_claude_session_id.return_value = None

        await run_agent_node(state, config)

    mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_run_agent_node_collects_tool_uses():
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=0)
    config = _make_config(ws=ws, db=db)

    async def tool_send_message(sid, content):
        yield {"type": "tool_use", "tool_name": "read_file", "tool_input": {"path": "/x"}}
        yield {"type": "assistant_text", "content": "Done"}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = tool_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    msg = result["messages"][0]
    assert len(msg["tools"]) == 1
    assert msg["tools"][0]["tool_name"] == "read_file"


@pytest.mark.asyncio
async def test_run_agent_node_preserves_existing_messages():
    ws = AsyncMock()
    db = AsyncMock()
    existing_msg = {"agent": "OldAgent", "text": "old output", "tools": []}
    state = _make_state(depth=0, messages=[existing_msg])
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "new"}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    assert len(result["messages"]) == 2
    assert result["messages"][0] == existing_msg
    assert result["messages"][1]["text"] == "new"


@pytest.mark.asyncio
async def test_run_agent_node_saves_claude_session_id():
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    state = _make_state(current_session_id=str(session_id), depth=0)
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "reply"}

    mock_session_obj = MagicMock()
    mock_session_obj.claude_session_id = None

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock, return_value=mock_session_obj),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = "claude-abc-123"

        await run_agent_node(state, config)

    assert mock_session_obj.claude_session_id == "claude-abc-123"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_duplicates_to_main_session():
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    main_session_id = uuid.uuid4()
    state = _make_state(
        current_session_id=str(session_id),
        main_session_id=str(main_session_id),
        depth=1,
        current_agent_name="SubAgent",
    )
    config = _make_config(ws=ws, db=db)

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": "sub result"}

    mock_add = AsyncMock()
    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", mock_add),
        patch(f"{GS}.stop_session", new_callable=AsyncMock),
        patch(f"{GS}._resolve_handoff", new_callable=AsyncMock, return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    assert mock_add.call_count == 2
    main_call = mock_add.call_args_list[1]
    assert main_call.args[1] == main_session_id
    assert "[SubAgent]" in main_call.args[3]


# ---------------------------------------------------------------------------
# notify_handoff_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_handoff_node_sends_approval_required():
    ws = AsyncMock()
    hr = _make_handoff_result(
        result_type=HandoffResultType.AWAITING_APPROVAL.value,
        to_agent_name="Reviewer",
        prompt="Review PR",
    )
    state = _make_state(
        current_agent_name="Dev",
        handoff_result=hr,
    )
    config = _make_config(ws=ws)

    result = await notify_handoff_node(state, config)

    ws.send_json.assert_called_once()
    event = ws.send_json.call_args.args[0]
    assert event["type"] == "approval_required"
    assert event["from_agent"] == "Dev"
    assert event["to_agent"] == "Reviewer"
    assert result == {}


# ---------------------------------------------------------------------------
# gate_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_node_reject_returns_end():
    ws = AsyncMock()
    db = AsyncMock()
    hr = _make_handoff_result(result_type=HandoffResultType.AWAITING_APPROVAL.value)
    state = _make_state(handoff_result=hr)
    config = _make_config(ws=ws, db=db)

    with patch(f"{GS}.interrupt", return_value=False):
        result = await gate_node(state, config)

    assert result["gateway_approved"] is False
    assert result["handoff_result"] is None


@pytest.mark.asyncio
async def test_gate_node_approve_creates_sub_session():
    ws = AsyncMock()
    db = AsyncMock()
    target = MagicMock()
    target.id = uuid.uuid4()
    target.name = "Reviewer"
    target.system_prompt = "You are Reviewer."
    target.config = {"workdir": "/tmp/project"}
    target.allowed_tools = []
    target.prompts = []
    sub_session = MagicMock()
    sub_session.id = uuid.uuid4()
    sub_session.task_id = None

    hr = _make_handoff_result(
        result_type=HandoffResultType.AWAITING_APPROVAL.value,
        to_agent_id=str(target.id),
        to_agent_name="Reviewer",
        prompt="Please review",
    )
    state = _make_state(
        handoff_result=hr,
        current_agent_name="Dev",
    )
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.interrupt", return_value=True),
        patch(f"{GS}.create_session", new_callable=AsyncMock, return_value=sub_session),
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[]),
        patch(f"{GS}.format_handoff_tools_prompt", return_value=""),
        patch(f"{GS}.runtime") as mock_runtime,
    ):
        mock_runtime.start_session = AsyncMock()
        db.get.return_value = target

        result = await gate_node(state, config)

    assert result["gateway_approved"] is True
    assert result["current_session_id"] == str(sub_session.id)
    assert result["current_agent_name"] == "Reviewer"
    assert result["depth"] == 1
    mock_runtime.start_session.assert_called_once()

    sent = ws.send_json.call_args.args[0]
    assert sent["type"] == "handoff_start"
    assert sent["from_agent"] == "Dev"
    assert sent["to_agent"] == "Reviewer"


@pytest.mark.asyncio
async def test_gate_node_target_not_found():
    ws = AsyncMock()
    db = AsyncMock()
    hr = _make_handoff_result(
        result_type=HandoffResultType.AWAITING_APPROVAL.value,
        to_agent_id=str(uuid.uuid4()),
    )
    state = _make_state(handoff_result=hr)
    config = _make_config(ws=ws, db=db)

    with patch(f"{GS}.interrupt", return_value=True):
        db.get.return_value = None
        result = await gate_node(state, config)

    assert result["gateway_approved"] is False


# ---------------------------------------------------------------------------
# auto_handoff_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_handoff_creates_sub_session():
    ws = AsyncMock()
    db = AsyncMock()
    target = MagicMock()
    target.id = uuid.uuid4()
    target.name = "QA"
    target.system_prompt = "You are QA."
    target.config = {}
    target.allowed_tools = []
    target.prompts = []
    sub_session = MagicMock()
    sub_session.id = uuid.uuid4()
    sub_session.task_id = None

    hr = _make_handoff_result(
        result_type=HandoffResultType.FORWARDED.value,
        to_agent_id=str(target.id),
        to_agent_name="QA",
        prompt="Run tests",
        requires_approval=False,
    )
    state = _make_state(handoff_result=hr, current_agent_name="Dev")
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.create_session", new_callable=AsyncMock, return_value=sub_session),
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[]),
        patch(f"{GS}.format_handoff_tools_prompt", return_value=""),
        patch(f"{GS}.runtime") as mock_runtime,
    ):
        mock_runtime.start_session = AsyncMock()
        db.get.return_value = target

        result = await auto_handoff_node(state, config)

    assert result["gateway_approved"] is True
    assert result["current_agent_name"] == "QA"
    mock_runtime.start_session.assert_called_once()


@pytest.mark.asyncio
async def test_auto_handoff_cycle_detected():
    """P8: Repeated cycle in chain blocks the handoff."""
    ws = AsyncMock()
    db = AsyncMock()
    target = MagicMock()
    target.id = uuid.uuid4()
    target.name = "Reviewer"
    target.system_prompt = "You review."
    target.config = {}
    target.allowed_tools = []

    hr = _make_handoff_result(
        result_type=HandoffResultType.FORWARDED.value,
        to_agent_id=str(target.id),
        to_agent_name="Reviewer",
    )
    # Chain already contains Dev→Reviewer
    state = _make_state(
        handoff_result=hr,
        current_agent_name="Dev",
        chain=[["Dev", "Reviewer"], ["Reviewer", "Dev"]],
    )
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.create_session", new_callable=AsyncMock) as mock_create,
        patch(f"{GS}.runtime") as mock_runtime,
    ):
        mock_runtime.start_session = AsyncMock()
        db.get.return_value = target

        result = await auto_handoff_node(state, config)

    assert result["gateway_approved"] is False
    mock_create.assert_not_called()
    # max_cycles_reached event sent
    sent = [c.args[0] for c in ws.send_json.call_args_list]
    cycle_events = [e for e in sent if e.get("type") == "max_cycles_reached"]
    assert len(cycle_events) == 1
    assert "Cycle" in cycle_events[0]["reason"]


# ---------------------------------------------------------------------------
# complete_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_node_sends_task_completed():
    ws = AsyncMock()
    hr = _make_handoff_result(
        result_type=HandoffResultType.COMPLETED.value,
        tool_args={"summary": "All done"},
    )
    state = _make_state(handoff_result=hr, current_agent_name="Dev")
    config = _make_config(ws=ws)

    result = await complete_node(state, config)

    ws.send_json.assert_called_once()
    event = ws.send_json.call_args.args[0]
    assert event["type"] == "task_completed"
    assert event["summary"] == "All done"
    assert result["handoff_result"] is None


# ---------------------------------------------------------------------------
# blocked_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_node_sends_max_cycles():
    ws = AsyncMock()
    hr = _make_handoff_result(
        result_type=HandoffResultType.BLOCKED.value,
        reason="max_cycles (3) reached for agent Dev",
        to_agent_name="Dev",
    )
    state = _make_state(handoff_result=hr)
    config = _make_config(ws=ws)

    result = await blocked_node(state, config)

    ws.send_json.assert_called_once()
    event = ws.send_json.call_args.args[0]
    assert event["type"] == "max_cycles_reached"
    assert event["agent_name"] == "Dev"
    assert result["handoff_result"] is None
