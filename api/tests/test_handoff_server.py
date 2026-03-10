"""Tests for app.services.handoff_server — MCP handoff tools."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.handoff_server import (
    COMPLETE_TASK_TOOL_NAME,
    HandoffResult,
    HandoffTool,
    count_agent_visits,
    format_handoff_tools_prompt,
    generate_handoff_tools,
    handle_handoff_tool_call,
    parse_handoff_from_text,
    render_prompt,
    resolve_handoff_prompt,
)

HS = "app.services.handoff_server"


# ---------------------------------------------------------------------------
# parse_handoff_from_text
# ---------------------------------------------------------------------------


def test_parse_handoff_from_text_valid():
    text = 'Done.\n```handoff\n{"tool": "forward_to_reviewer", "comment": "Please review"}\n```'
    result = parse_handoff_from_text(text)
    assert result == {"tool": "forward_to_reviewer", "comment": "Please review"}


def test_parse_handoff_from_text_complete_task():
    text = '```handoff\n{"tool": "complete_task", "summary": "All done"}\n```'
    result = parse_handoff_from_text(text)
    assert result == {"tool": "complete_task", "summary": "All done"}


def test_parse_handoff_from_text_no_block():
    assert parse_handoff_from_text("Just a regular response.") is None


def test_parse_handoff_from_text_invalid_json():
    text = "```handoff\n{not valid}\n```"
    assert parse_handoff_from_text(text) is None


def test_parse_handoff_from_text_missing_tool():
    text = '```handoff\n{"comment": "no tool field"}\n```'
    assert parse_handoff_from_text(text) is None


def test_parse_handoff_from_text_tool_not_string():
    text = '```handoff\n{"tool": 123}\n```'
    assert parse_handoff_from_text(text) is None


# ---------------------------------------------------------------------------
# render_prompt
# ---------------------------------------------------------------------------


def test_render_prompt_substitutes_variables():
    task = MagicMock()
    task.title = "Fix bug"
    task.description = "There is a bug in login"
    result = render_prompt("Review: {{task_title}}. Details: {{task_description}}", task)
    assert result == "Review: Fix bug. Details: There is a bug in login"


def test_render_prompt_handles_none_fields():
    task = MagicMock()
    task.title = None
    task.description = None
    result = render_prompt("Task: {{task_title}}", task)
    assert result == "Task: "


# ---------------------------------------------------------------------------
# format_handoff_tools_prompt
# ---------------------------------------------------------------------------


def test_format_handoff_tools_prompt_with_tools():
    tools = [
        HandoffTool(
            name="approve_and_forward",
            description="Approved — forward to QA",
            edge_id=uuid.uuid4(),
            to_agent_id=uuid.uuid4(),
            to_agent_name="QA",
            requires_approval=True,
        ),
    ]
    result = format_handoff_tools_prompt(tools)
    assert "approve_and_forward" in result
    assert "Available Actions" in result


def test_format_handoff_tools_prompt_complete_only():
    tools = [
        HandoffTool(
            name=COMPLETE_TASK_TOOL_NAME,
            description="Complete the task",
            edge_id=uuid.UUID(int=0),
            to_agent_id=uuid.UUID(int=0),
            to_agent_name="",
            requires_approval=False,
        ),
    ]
    result = format_handoff_tools_prompt(tools)
    assert "complete_task" in result
    assert "When your work is done:" in result


def test_format_handoff_tools_prompt_empty():
    assert format_handoff_tools_prompt([]) == ""


# ---------------------------------------------------------------------------
# generate_handoff_tools
# ---------------------------------------------------------------------------


def _make_edge(
    from_id, to_id, workflow_id, condition=None,
    requires_approval=True, prompt_template=None, prompt_id=None,
    to_name="Reviewer",
):
    edge = MagicMock()
    edge.id = uuid.uuid4()
    edge.workflow_id = workflow_id
    edge.from_agent_id = from_id
    edge.to_agent_id = to_id
    edge.condition = condition
    edge.requires_approval = requires_approval
    edge.prompt_template = prompt_template
    edge.prompt_id = prompt_id
    edge.order = 0

    to_agent = MagicMock()
    to_agent.name = to_name
    edge.to_agent = to_agent

    return edge


@pytest.mark.asyncio
async def test_generate_handoff_tools_from_edges():
    agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    to_id = uuid.uuid4()

    edge = _make_edge(agent_id, to_id, workflow_id, condition="review passed")

    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [edge]
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result

    tools = await generate_handoff_tools(db, agent_id, workflow_id)
    assert len(tools) == 1
    assert tools[0].name == "review_passed"
    assert tools[0].to_agent_name == "Reviewer"
    assert tools[0].requires_approval is True


@pytest.mark.asyncio
async def test_generate_handoff_tools_terminal_node():
    """Agent with no outgoing edges gets complete_task tool."""
    agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result

    tools = await generate_handoff_tools(db, agent_id, workflow_id)
    assert len(tools) == 1
    assert tools[0].name == COMPLETE_TASK_TOOL_NAME


@pytest.mark.asyncio
async def test_generate_handoff_tools_no_condition_uses_agent_name():
    agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    to_id = uuid.uuid4()

    edge = _make_edge(agent_id, to_id, workflow_id, condition=None, to_name="QA Agent")

    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [edge]
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result

    tools = await generate_handoff_tools(db, agent_id, workflow_id)
    assert tools[0].name == "forward_to_qa_agent"


# ---------------------------------------------------------------------------
# count_agent_visits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_agent_visits():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3
    db.execute.return_value = mock_result

    count = await count_agent_visits(db, uuid.uuid4(), uuid.uuid4())
    assert count == 3


@pytest.mark.asyncio
async def test_count_agent_visits_none_returns_zero():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    db.execute.return_value = mock_result

    count = await count_agent_visits(db, uuid.uuid4(), uuid.uuid4())
    assert count == 0


# ---------------------------------------------------------------------------
# resolve_handoff_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_prompt_from_template():
    tool = HandoffTool(
        name="forward",
        description="Forward",
        edge_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        to_agent_name="QA",
        requires_approval=False,
        prompt_template="Review {{task_title}}",
    )
    task = MagicMock()
    task.title = "Login fix"
    task.description = "Fixed login bug"

    db = AsyncMock()
    result = await resolve_handoff_prompt(db, tool, task, {})
    assert result == "Review Login fix"


@pytest.mark.asyncio
async def test_resolve_prompt_fallback_to_args():
    tool = HandoffTool(
        name="forward",
        description="Forward",
        edge_id=uuid.uuid4(),
        to_agent_id=uuid.uuid4(),
        to_agent_name="QA",
        requires_approval=False,
    )
    db = AsyncMock()
    result = await resolve_handoff_prompt(db, tool, None, {"comment": "Please test"})
    assert result == "Please test"


@pytest.mark.asyncio
async def test_resolve_prompt_from_prompt_id():
    to_agent_id = uuid.uuid4()
    tool = HandoffTool(
        name="forward",
        description="Forward",
        edge_id=uuid.uuid4(),
        to_agent_id=to_agent_id,
        to_agent_name="QA",
        requires_approval=False,
        prompt_id="review-prompt",
    )

    agent = MagicMock()
    agent.prompts = [{"id": "review-prompt", "content": "Review: {{task_title}}"}]

    task = MagicMock()
    task.title = "My task"
    task.description = ""

    db = AsyncMock()
    db.get.return_value = agent

    result = await resolve_handoff_prompt(db, tool, task, {})
    assert result == "Review: My task"


# ---------------------------------------------------------------------------
# handle_handoff_tool_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_complete_task():
    db = AsyncMock()
    result = await handle_handoff_tool_call(
        db,
        tool_name="complete_task",
        tool_args={"summary": "All done"},
        task_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
    )
    assert result.completed is True
    assert result.tool_args == {"summary": "All done"}


@pytest.mark.asyncio
async def test_handle_unknown_tool():
    db = AsyncMock()
    # Mock generate_handoff_tools to return empty
    with patch(f"{HS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[]):
        result = await handle_handoff_tool_call(
            db,
            tool_name="nonexistent",
            tool_args={},
            task_id=None,
            workflow_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
        )
    assert result.blocked is True
    assert "Unknown" in result.reason


@pytest.mark.asyncio
async def test_handle_requires_approval():
    agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    tool = HandoffTool(
        name="forward_to_reviewer",
        description="Forward to Reviewer",
        edge_id=uuid.uuid4(),
        to_agent_id=to_agent_id,
        to_agent_name="Reviewer",
        requires_approval=True,
    )

    db = AsyncMock()
    db.get.return_value = None  # no task

    with patch(f"{HS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[tool]):
        result = await handle_handoff_tool_call(
            db,
            tool_name="forward_to_reviewer",
            tool_args={"comment": "Review this"},
            task_id=None,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )

    assert result.awaiting_approval is True
    assert result.to_agent_name == "Reviewer"


@pytest.mark.asyncio
async def test_handle_auto_forward():
    agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    tool = HandoffTool(
        name="forward_to_qa",
        description="Forward to QA",
        edge_id=uuid.uuid4(),
        to_agent_id=to_agent_id,
        to_agent_name="QA",
        requires_approval=False,
    )

    db = AsyncMock()
    db.get.return_value = None  # no task

    with patch(f"{HS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[tool]):
        result = await handle_handoff_tool_call(
            db,
            tool_name="forward_to_qa",
            tool_args={"comment": "Run tests"},
            task_id=None,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )

    assert result.forwarded is True
    assert result.to_agent_name == "QA"


@pytest.mark.asyncio
async def test_handle_max_cycles_exceeded():
    agent_id = uuid.uuid4()
    to_agent_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    task_id = uuid.uuid4()

    tool = HandoffTool(
        name="forward_to_dev",
        description="Forward to Dev",
        edge_id=uuid.uuid4(),
        to_agent_id=to_agent_id,
        to_agent_name="Dev",
        requires_approval=False,
    )

    target_agent = MagicMock()
    target_agent.max_cycles = 2

    db = AsyncMock()
    db.get.return_value = target_agent

    with (
        patch(f"{HS}.generate_handoff_tools", new_callable=AsyncMock, return_value=[tool]),
        patch(f"{HS}.count_agent_visits", new_callable=AsyncMock, return_value=2),
    ):
        result = await handle_handoff_tool_call(
            db,
            tool_name="forward_to_dev",
            tool_args={"comment": "Fix bug"},
            task_id=task_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )

    assert result.blocked is True
    assert "max_cycles" in result.reason
