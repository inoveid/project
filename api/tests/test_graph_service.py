"""Tests for app.services.graph_service — LangGraph nodes and routing."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.graph_service import (
    END,
    MAX_DEPTH,
    WorkflowState,
    gate_node,
    notify_handoff_node,
    route_after_agent,
    route_after_gate,
    run_agent_node,
)

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
        "task": "Implement feature",
        "depth": 0,
        "chain": [],
        "handoff_target": None,
        "handoff_message": None,
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


def _make_target_agent(name="Reviewer", role="reviewer", description="Reviews code"):
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = name
    agent.role = role
    agent.description = description
    agent.system_prompt = f"You are {name}."
    agent.config = {"workdir": "/tmp/project"}
    agent.allowed_tools = []
    return agent


# ---------------------------------------------------------------------------
# route_after_agent
# ---------------------------------------------------------------------------


def test_route_after_agent_handoff():
    """Returns 'notify_handoff' when handoff_target is set and depth < MAX_DEPTH."""
    state = _make_state(handoff_target="Reviewer", depth=0)
    assert route_after_agent(state) == "notify_handoff"


def test_route_after_agent_end():
    """Returns END when no handoff_target."""
    state = _make_state(handoff_target=None)
    assert route_after_agent(state) == END


def test_route_after_agent_max_depth():
    """Returns END when depth >= MAX_DEPTH even with handoff_target."""
    state = _make_state(handoff_target="Reviewer", depth=MAX_DEPTH)
    assert route_after_agent(state) == END


def test_route_after_agent_depth_below_max():
    """Returns 'notify_handoff' when depth is just below MAX_DEPTH."""
    state = _make_state(handoff_target="Reviewer", depth=MAX_DEPTH - 1)
    assert route_after_agent(state) == "notify_handoff"


# ---------------------------------------------------------------------------
# route_after_gate
# ---------------------------------------------------------------------------


def test_route_after_gate_approved():
    """Returns 'run_agent' when gateway_approved is True."""
    state = _make_state(gateway_approved=True)
    assert route_after_gate(state) == "run_agent"


def test_route_after_gate_rejected():
    """Returns END when gateway_approved is False."""
    state = _make_state(gateway_approved=False)
    assert route_after_gate(state) == END


def test_route_after_gate_none():
    """Returns END when gateway_approved is None."""
    state = _make_state(gateway_approved=None)
    assert route_after_gate(state) == END


# ---------------------------------------------------------------------------
# run_agent_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_node_streams_events():
    """Node streams events from runtime.send_message to WebSocket."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    # Events forwarded to WebSocket (exactly 2 streaming events)
    assert ws.send_json.call_count == 2
    sent_events = [call.args[0] for call in ws.send_json.call_args_list]
    assert sent_events[0] == {"type": "assistant_text", "content": "Hello "}
    assert sent_events[1] == {"type": "assistant_text", "content": "world"}


@pytest.mark.asyncio
async def test_run_agent_node_saves_response():
    """Node saves assistant response to DB via add_message."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        await run_agent_node(state, config)

    # First call: save assistant message
    mock_add.assert_called_once()
    args = mock_add.call_args
    assert args.args[1] == session_id  # session_id
    assert args.args[2] == "assistant"
    assert "Result text" in args.args[3]


@pytest.mark.asyncio
async def test_run_agent_node_parses_handoff():
    """Node parses handoff block and sets handoff_target in returned state."""
    ws = AsyncMock()
    db = AsyncMock()
    session_id = uuid.uuid4()
    state = _make_state(current_session_id=str(session_id), depth=0)
    config = _make_config(ws=ws, db=db)

    handoff_text = 'Done.\n```handoff\n{"to": "Reviewer", "message": "Please review"}\n```'

    async def fake_send_message(sid, content):
        yield {"type": "assistant_text", "content": handoff_text}

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    assert result["handoff_target"] == "Reviewer"
    assert result["handoff_message"] == "Please review"


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_cleanup():
    """For sub-agent (depth>0), node stops runtime and session in DB."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        result = await run_agent_node(state, config)

    # Runtime stopped for sub-agent
    mock_runtime.stop_session.assert_called_once_with(session_id)
    # DB session stopped
    mock_stop.assert_called_once_with(db, session_id)
    # handoff_done event sent
    sent = [c.args[0] for c in ws.send_json.call_args_list]
    handoff_done = [e for e in sent if e.get("type") == "handoff_done"]
    assert len(handoff_done) == 1
    assert handoff_done[0]["agent_name"] == "SubAgent"


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_prefixes_events():
    """Sub-agent events get 'sub_agent_' prefix for UI."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    first_event = ws.send_json.call_args_list[0].args[0]
    assert first_event["type"] == "sub_agent_assistant_text"
    assert first_event["agent_name"] == "SubAgent"


# ---------------------------------------------------------------------------
# notify_handoff_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_handoff_node_sends_approval_required():
    """Node sends approval_required event with from/to/task."""
    ws = AsyncMock()
    state = _make_state(
        current_agent_name="Dev",
        handoff_target="Reviewer",
        handoff_message="Please review this PR",
    )
    config = _make_config(ws=ws)

    result = await notify_handoff_node(state, config)

    ws.send_json.assert_called_once()
    event = ws.send_json.call_args.args[0]
    assert event["type"] == "approval_required"
    assert event["from_agent"] == "Dev"
    assert event["to_agent"] == "Reviewer"
    assert event["task"] == "Please review this PR"
    assert result == {}


# ---------------------------------------------------------------------------
# gate_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_node_reject_returns_end():
    """When interrupt returns False (reject), gate cancels handoff."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(handoff_target="Reviewer", handoff_message="review")
    config = _make_config(ws=ws, db=db)

    with patch(f"{GS}.interrupt", return_value=False):
        result = await gate_node(state, config)

    assert result["gateway_approved"] is False
    assert result["handoff_target"] is None
    assert result["handoff_message"] is None


@pytest.mark.asyncio
async def test_gate_node_approve_creates_sub_session():
    """When approved, gate creates sub-session, starts runtime, sends handoff_start."""
    ws = AsyncMock()
    db = AsyncMock()
    target = _make_target_agent("Reviewer")
    sub_session = MagicMock()
    sub_session.id = uuid.uuid4()

    state = _make_state(
        handoff_target="Reviewer",
        handoff_message="Please review",
        current_agent_name="Dev",
    )
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.interrupt", return_value=True),
        patch(f"{GS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[target]),
        patch(f"{GS}.create_session", new_callable=AsyncMock, return_value=sub_session),
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.build_agent_prompt", return_value="Sub prompt"),
        patch(f"{GS}.runtime") as mock_runtime,
    ):
        mock_runtime.start_session = AsyncMock()

        result = await gate_node(state, config)

    assert result["gateway_approved"] is True
    assert result["current_session_id"] == str(sub_session.id)
    assert result["current_agent_id"] == str(target.id)
    assert result["current_agent_name"] == "Reviewer"
    assert result["depth"] == 1
    assert result["task"] == "Please review"

    # Runtime started for sub-agent
    mock_runtime.start_session.assert_called_once()

    # handoff_start event sent
    sent = ws.send_json.call_args.args[0]
    assert sent["type"] == "handoff_start"
    assert sent["from_agent"] == "Dev"
    assert sent["to_agent"] == "Reviewer"


@pytest.mark.asyncio
async def test_gate_node_target_not_found():
    """When target agent not in agent_links, gate rejects."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(handoff_target="NonExistent")
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.interrupt", return_value=True),
        patch(f"{GS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[]),
    ):
        result = await gate_node(state, config)

    assert result["gateway_approved"] is False


@pytest.mark.asyncio
async def test_gate_node_cycle_detection():
    """When handoff pair already in chain, gate detects cycle and rejects."""
    ws = AsyncMock()
    db = AsyncMock()
    target = _make_target_agent("Reviewer")

    state = _make_state(
        handoff_target="Reviewer",
        current_agent_name="Dev",
        chain=[["Dev", "Reviewer"]],  # already visited
    )
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.interrupt", return_value=True),
        patch(f"{GS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[target]),
    ):
        result = await gate_node(state, config)

    assert result["gateway_approved"] is False
    # Cycle detection event sent
    sent = ws.send_json.call_args.args[0]
    assert sent["type"] == "handoff_cycle_detected"
    assert "cycle" in sent["message"].lower()


# ---------------------------------------------------------------------------
# run_agent_node — error handling & edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_node_error_sends_error_event():
    """When runtime.send_message raises, error event is sent to WebSocket."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=0)
    config = _make_config(ws=ws, db=db)

    async def failing_send_message(sid, content):
        raise RuntimeError("API rate limit")
        yield  # noqa: unreachable

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.get_session", new_callable=AsyncMock),
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = failing_send_message
        mock_runtime.get_claude_session_id.return_value = None

        await run_agent_node(state, config)

    sent = [c.args[0] for c in ws.send_json.call_args_list]
    error_events = [e for e in sent if e.get("type") == "error"]
    assert len(error_events) == 1
    assert "rate limit" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_error_sends_sub_agent_error():
    """Sub-agent error sends sub_agent_error event, not plain error."""
    ws = AsyncMock()
    db = AsyncMock()
    state = _make_state(depth=1, current_agent_name="SubAgent")
    config = _make_config(ws=ws, db=db)

    async def failing_send_message(sid, content):
        raise RuntimeError("CLI crashed")
        yield  # noqa: unreachable

    with (
        patch(f"{GS}.runtime") as mock_runtime,
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.stop_session", new_callable=AsyncMock),
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = failing_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    sent = [c.args[0] for c in ws.send_json.call_args_list]
    error_events = [e for e in sent if e.get("type") == "sub_agent_error"]
    assert len(error_events) == 1
    assert error_events[0]["agent_name"] == "SubAgent"


@pytest.mark.asyncio
async def test_run_agent_node_empty_response_not_saved():
    """When agent produces no text and no tools, add_message is NOT called."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = empty_send_message
        mock_runtime.get_claude_session_id.return_value = None

        await run_agent_node(state, config)

    mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_run_agent_node_collects_tool_uses():
    """tool_use events are collected and included in result messages."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = tool_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    msg = result["messages"][0]
    assert len(msg["tools"]) == 1
    assert msg["tools"][0]["tool_name"] == "read_file"


@pytest.mark.asyncio
async def test_run_agent_node_preserves_existing_messages():
    """Result messages list includes previous messages from state."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = None

        result = await run_agent_node(state, config)

    assert len(result["messages"]) == 2
    assert result["messages"][0] == existing_msg
    assert result["messages"][1]["text"] == "new"


@pytest.mark.asyncio
async def test_run_agent_node_saves_claude_session_id():
    """For main agent (depth=0), claude_session_id is saved to DB session."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.get_claude_session_id.return_value = "claude-abc-123"

        await run_agent_node(state, config)

    assert mock_session_obj.claude_session_id == "claude-abc-123"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_node_sub_agent_duplicates_to_main_session():
    """Sub-agent result is duplicated to main session for history."""
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
        patch(f"{GS}.parse_handoff_block", return_value=None),
    ):
        mock_runtime.send_message = fake_send_message
        mock_runtime.stop_session = AsyncMock()

        await run_agent_node(state, config)

    # Two add_message calls: one for sub-session, one duplicate for main
    assert mock_add.call_count == 2
    # Second call is the duplicate to main session
    main_call = mock_add.call_args_list[1]
    assert main_call.args[1] == main_session_id
    assert "[SubAgent]" in main_call.args[3]


@pytest.mark.asyncio
async def test_gate_node_approve_updates_chain():
    """Approved gate adds current pair to chain in result."""
    ws = AsyncMock()
    db = AsyncMock()
    target = _make_target_agent("Reviewer")
    sub_session = MagicMock()
    sub_session.id = uuid.uuid4()

    state = _make_state(
        handoff_target="Reviewer",
        handoff_message="review",
        current_agent_name="Dev",
        chain=[["Planner", "Dev"]],
    )
    config = _make_config(ws=ws, db=db)

    with (
        patch(f"{GS}.interrupt", return_value=True),
        patch(f"{GS}.get_agent_handoff_targets", new_callable=AsyncMock, return_value=[target]),
        patch(f"{GS}.create_session", new_callable=AsyncMock, return_value=sub_session),
        patch(f"{GS}.add_message", new_callable=AsyncMock),
        patch(f"{GS}.build_agent_prompt", return_value="prompt"),
        patch(f"{GS}.runtime") as mock_runtime,
    ):
        mock_runtime.start_session = AsyncMock()
        result = await gate_node(state, config)

    assert result["chain"] == [["Planner", "Dev"], ["Dev", "Reviewer"]]
