"""
Sub-agent Service — spawns and runs sub-agents from templates.

Flow:
1. Parent agent outputs ```spawn_agent block
2. graph_service detects it, calls spawn_sub_agent()
3. We create a child session, start runtime, run to completion
4. Return sub-agent output to the caller (graph_service feeds it back to parent)

Sub-agents run at depth > 0, inherit parent's workspace, have their own budget.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.schemas.agent import SubAgentTemplate
from app.services.event_bus import publish_event
from app.services.runtime import runtime
from app.services.session_service import add_message

logger = logging.getLogger(__name__)

MAX_SUB_AGENT_DEPTH = 3
MAX_SUB_AGENTS_PER_TURN = 5


@dataclass
class SpawnRequest:
    """Parsed spawn_agent request from agent output."""
    role: str
    task: str


@dataclass
class SubAgentResult:
    """Result of running a sub-agent."""
    role: str
    name: str
    output: str
    success: bool
    error: str | None = None


def parse_spawn_requests(text: str) -> list[SpawnRequest]:
    """
    Parse ```spawn_agent blocks from agent response.

    Expected format:
      ```spawn_agent
      {"role": "researcher", "task": "Find examples of OAuth in FastAPI"}
      ```
    """
    pattern = r'```spawn_agent\s*\n([\s\S]*?)\n```'
    matches = re.findall(pattern, text)
    requests = []
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict) and "role" in data and "task" in data:
                requests.append(SpawnRequest(role=data["role"], task=data["task"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return requests[:MAX_SUB_AGENTS_PER_TURN]


def find_template(templates: list[dict], role: str) -> SubAgentTemplate | None:
    """Find a sub-agent template by role name (case-insensitive)."""
    for t in templates:
        if t.get("role", "").lower() == role.lower():
            return SubAgentTemplate(**t)
    return None


def format_spawn_tools_prompt(templates: list[dict]) -> str:
    """
    Format sub-agent templates as instructions appended to the agent's system prompt.
    """
    if not templates:
        return ""

    lines = ["\n\n## Sub-agents"]
    lines.append("You can spawn sub-agents to help with specific tasks.")
    lines.append("Each sub-agent runs independently and returns its result to you.")
    lines.append("")
    lines.append("Available sub-agents:")

    for t in templates:
        role = t.get("role", "unknown")
        desc = t.get("description", "") or t.get("name", role)
        lines.append(f"- **{role}** — {desc}")

    lines.append("")
    lines.append("To spawn a sub-agent, include this block in your response:")
    lines.append('```spawn_agent\n{"role": "<role>", "task": "<specific task description>"}\n```')
    lines.append("")
    lines.append("You can spawn multiple sub-agents in one response.")
    lines.append("Their results will be provided to you in your next turn.")
    lines.append("Continue your work after receiving the results.")

    return "\n".join(lines)


async def spawn_sub_agent(
    db: AsyncSession,
    parent_session: Session,
    template: SubAgentTemplate,
    task: str,
    workdir: str,
    parent_depth: int,
    ws_session_id: str,
) -> SubAgentResult:
    """
    Spawn and run a sub-agent to completion.

    Creates an ephemeral runtime session (no DB agent record needed),
    runs the task, collects output, cleans up.
    """
    sub_session_id = uuid.uuid4()
    sub_depth = parent_depth + 1
    sub_name = f"{template.name} (sub-agent)"

    if sub_depth > MAX_SUB_AGENT_DEPTH:
        return SubAgentResult(
            role=template.role,
            name=template.name,
            output="",
            success=False,
            error=f"Max sub-agent depth ({MAX_SUB_AGENT_DEPTH}) exceeded",
        )

    # Notify frontend about sub-agent spawn
    await publish_event(ws_session_id, {
        "type": "sub_agent_spawned",
        "sub_session_id": str(sub_session_id),
        "role": template.role,
        "name": template.name,
        "task": task,
    })

    output_parts: list[str] = []
    tool_uses: list[dict] = []

    try:
        # Start sub-agent runtime session
        await runtime.start_session(
            session_id=sub_session_id,
            workdir=workdir,
            system_prompt=template.system_prompt,
            allowed_tools=template.allowed_tools,
            parent_session_id=parent_session.id,
        )

        # Run sub-agent
        async for event in runtime.send_message(sub_session_id, task):
            ev_type = event.get("type", "")

            if ev_type == "assistant_text":
                output_parts.append(event.get("content", ""))

            elif ev_type == "tool_use":
                tool_uses.append({
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input", {}),
                })

            # Forward sub-agent events to frontend (prefixed)
            await publish_event(ws_session_id, {
                **event,
                "type": f"sub_agent_{ev_type}" if not ev_type.startswith("sub_agent_") else ev_type,
                "sub_session_id": str(sub_session_id),
                "sub_agent_name": template.name,
                "sub_agent_role": template.role,
            })

        output = "".join(output_parts)

        # Notify completion
        await publish_event(ws_session_id, {
            "type": "sub_agent_done",
            "sub_session_id": str(sub_session_id),
            "role": template.role,
            "name": template.name,
            "output_preview": output[:500] if output else "",
        })

        return SubAgentResult(
            role=template.role,
            name=template.name,
            output=output,
            success=True,
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Sub-agent %s error: %s", sub_name, error_msg, exc_info=True)

        await publish_event(ws_session_id, {
            "type": "sub_agent_error",
            "sub_session_id": str(sub_session_id),
            "role": template.role,
            "name": template.name,
            "error": error_msg,
        })

        return SubAgentResult(
            role=template.role,
            name=template.name,
            output="",
            success=False,
            error=error_msg,
        )

    finally:
        # Always clean up sub-agent session
        await runtime.stop_session(sub_session_id)


def format_sub_agent_results(results: list[SubAgentResult]) -> str:
    """Format sub-agent results as a message to feed back to the parent agent."""
    if not results:
        return ""

    parts = ["## Sub-agent Results\n"]
    for r in results:
        parts.append(f"### {r.name} ({r.role})")
        if r.success:
            parts.append(r.output if r.output else "(no output)")
        else:
            parts.append(f"**Error**: {r.error}")
        parts.append("")

    return "\n".join(parts)
