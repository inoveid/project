"""
MCP Handoff Server — generates and handles handoff tools from workflow edges.

Replaces text-based handoff blocks (=== HANDOFF ===) with structured MCP tool calls.
Each outgoing edge of an agent in a workflow becomes an MCP tool that the agent
can call to transition to the next agent.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.session import Session
from app.models.task import Task
from app.models.workflow_edge import WorkflowEdge

logger = logging.getLogger(__name__)


@dataclass
class HandoffTool:
    """MCP tool definition generated from a workflow edge."""

    name: str
    description: str
    to_agent_name: str
    requires_approval: bool
    edge_id: uuid.UUID | None = None
    to_agent_id: uuid.UUID | None = None
    prompt_template: str | None = None


class HandoffResultType(str, Enum):
    """Discriminated type for handoff outcomes — exactly one per result."""

    FORWARDED = "forwarded"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass
class HandoffResult:
    """Result of handling a handoff tool call."""

    result_type: HandoffResultType
    reason: str = ""
    to_agent_id: uuid.UUID | None = None
    to_agent_name: str = ""
    prompt: str = ""
    edge_id: uuid.UUID | None = None
    requires_approval: bool = False
    tool_args: dict = field(default_factory=dict)


COMPLETE_TASK_TOOL_NAME = "complete_task"


def parse_handoff_from_text(text: str) -> dict | None:
    """
    Parse ```handoff {...} ``` block from agent response.

    Expected format:
      ```handoff
      {"tool": "forward_to_reviewer", "comment": "Please review"}
      ```
    Returns the parsed dict or None if no valid block found.
    """
    match = re.search(r'```handoff\s*\n([\s\S]*?)\n```', text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
        if isinstance(data, dict) and isinstance(data.get("tool"), str):
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _to_snake_case(text: str) -> str:
    """Convert a condition/label text to a valid snake_case tool name."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", text.strip().lower())
    parts = cleaned.split()
    return "_".join(parts) if parts else ""


async def generate_handoff_tools(
    db: AsyncSession, agent_id: uuid.UUID, workflow_id: uuid.UUID
) -> list[HandoffTool]:
    """
    Generate MCP tools from outgoing edges of an agent in a workflow.

    For each edge (from_agent_id == agent_id), creates a tool:
    - name: snake_case from condition or "forward_to_{agent_name}"
    - description: condition text + target agent name

    If agent is a terminal node (no outgoing edges), adds:
    - complete_task(summary: str) — finish the task
    """
    stmt = (
        select(WorkflowEdge)
        .where(
            WorkflowEdge.workflow_id == workflow_id,
            WorkflowEdge.from_agent_id == agent_id,
        )
        .options(selectinload(WorkflowEdge.to_agent))
        .order_by(WorkflowEdge.order)
    )
    result = await db.execute(stmt)
    edges = list(result.scalars().all())

    tools: list[HandoffTool] = []
    used_names: set[str] = set()

    for edge in edges:
        to_name = edge.to_agent.name if edge.to_agent else "unknown"

        if edge.condition:
            name = _to_snake_case(edge.condition)
        else:
            name = f"forward_to_{_to_snake_case(to_name)}"

        if not name:
            name = f"forward_to_agent_{len(tools)}"

        # Ensure unique names
        base_name = name
        counter = 2
        while name in used_names:
            name = f"{base_name}_{counter}"
            counter += 1
        used_names.add(name)

        description = f"Hand off to {to_name}"
        if edge.condition:
            description = f"{edge.condition} — forward to {to_name}"

        tools.append(HandoffTool(
            name=name,
            description=description,
            edge_id=edge.id,
            to_agent_id=edge.to_agent_id,
            to_agent_name=to_name,
            requires_approval=edge.requires_approval,
            prompt_template=edge.prompt_template,
        ))

    # Add complete_task only if agent has the permission
    agent = await db.get(Agent, agent_id)
    if agent and agent.can_complete_task:
        tools.append(HandoffTool(
            name=COMPLETE_TASK_TOOL_NAME,
            description="Complete the current task. Call when your work is done.",
            to_agent_name="",
            requires_approval=False,
        ))

    return tools


def format_handoff_tools_prompt(tools: list[HandoffTool]) -> str:
    """
    Format handoff tools as instructions appended to the agent's system prompt.

    The agent sees these as available actions to take after completing its work.
    """
    if not tools:
        return ""

    lines = ["\n\n## Available Actions"]

    has_complete = any(t.name == COMPLETE_TASK_TOOL_NAME for t in tools)
    handoff_tools = [t for t in tools if t.name != COMPLETE_TASK_TOOL_NAME]

    if handoff_tools:
        lines.append("When your work is done, choose ONE of these actions:")
        for tool in handoff_tools:
            lines.append(f"- **{tool.name}**(comment: str) — {tool.description}")
        lines.append("")
        lines.append(
            "To hand off, include at the END of your response a tool call block:"
        )
        lines.append(
            '```handoff\n{"tool": "<tool_name>", "comment": "<context for next agent>"}\n```'
        )

    if has_complete:
        if handoff_tools:
            lines.append("")
            lines.append(
                "If the task is fully complete and no further handoff is needed:"
            )
        else:
            lines.append("When your work is done:")
        lines.append(
            '```handoff\n{"tool": "complete_task", "summary": "<summary of what was done>"}\n```'
        )

    return "\n".join(lines)


async def count_agent_visits(
    db: AsyncSession, task_id: uuid.UUID, agent_id: uuid.UUID
) -> int:
    """Count how many sessions with this agent_id already exist for task_id."""
    stmt = select(func.count()).select_from(Session).where(
        Session.task_id == task_id,
        Session.agent_id == agent_id,
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


def render_prompt(template: str, task: Task) -> str:
    """Substitute variables in a prompt template."""
    result = template
    result = result.replace("{{task_title}}", task.title or "")
    result = result.replace("{{task_description}}", task.description or "")
    return result


async def resolve_handoff_prompt(
    db: AsyncSession,
    tool: HandoffTool,
    task: Task | None,
    tool_args: dict,
) -> str:
    """
    Determine the prompt for the next agent.

    Priority:
    1. edge.prompt_template with variable substitution
    3. Fallback: comment/notes from tool call args
    """
    if tool.prompt_template and task:
        return render_prompt(tool.prompt_template, task)

    if tool.prompt_template:
        return tool.prompt_template

    # Fallback: use comment/notes/summary from tool args
    return (
        tool_args.get("comment")
        or tool_args.get("notes")
        or tool_args.get("summary")
        or ""
    )


async def handle_handoff_tool_call(
    db: AsyncSession,
    tool_name: str,
    tool_args: dict,
    task_id: uuid.UUID | None,
    workflow_id: uuid.UUID,
    agent_id: uuid.UUID,
    tools: list[HandoffTool] | None = None,
    chain: list | None = None,
    agent_name: str = "",
) -> HandoffResult:
    """
    Handle a handoff tool call from an agent.

    Args:
        tools: Pre-generated handoff tools. If None, will be generated (extra DB query).

    Flow:
    1. Find edge by tool_name
    2. Check max_cycles for to_agent
    3. If max_cycles exceeded → blocked
    4. If requires_approval → awaiting_approval
    5. If auto → forwarded
    """
    # Handle complete_task
    if tool_name == COMPLETE_TASK_TOOL_NAME:
        return HandoffResult(
            result_type=HandoffResultType.COMPLETED,
            reason="Task completed by agent",
            tool_args=tool_args,
        )

    # Use pre-generated tools or generate fresh
    if tools is None:
        tools = await generate_handoff_tools(db, agent_id, workflow_id)
    tool = next((t for t in tools if t.name == tool_name), None)

    if not tool:
        return HandoffResult(
            result_type=HandoffResultType.BLOCKED,
            reason=f"Unknown handoff tool: {tool_name}",
        )

    # Check max_rounds on the edge (loaded via edge_id from tool)
    if tool.edge_id:
        from app.models.workflow_edge import WorkflowEdge
        edge = await db.get(WorkflowEdge, tool.edge_id)
        if edge:
            max_rounds = edge.max_rounds
            # Count how many times this exact pair appears in chain
            pair_count = chain.count([agent_name, tool.to_agent_name]) if chain else 0
            if pair_count >= max_rounds:
                return HandoffResult(
                    result_type=HandoffResultType.BLOCKED,
                    reason=f"max_rounds ({max_rounds}) reached for {agent_name} → {tool.to_agent_name}",
                    to_agent_id=tool.to_agent_id,
                    to_agent_name=tool.to_agent_name,
                )

    # Resolve prompt for next agent
    task = None
    if task_id:
        task = await db.get(Task, task_id)
    prompt = await resolve_handoff_prompt(db, tool, task, tool_args)

    if tool.requires_approval:
        return HandoffResult(
            result_type=HandoffResultType.AWAITING_APPROVAL,
            to_agent_id=tool.to_agent_id,
            to_agent_name=tool.to_agent_name,
            prompt=prompt,
            edge_id=tool.edge_id,
            requires_approval=True,
            tool_args=tool_args,
        )

    return HandoffResult(
        result_type=HandoffResultType.FORWARDED,
        to_agent_id=tool.to_agent_id,
        to_agent_name=tool.to_agent_name,
        prompt=prompt,
        edge_id=tool.edge_id,
        requires_approval=False,
        tool_args=tool_args,
    )
