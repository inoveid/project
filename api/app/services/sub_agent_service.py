"""
Sub-agent Service — spawns and runs sub-agents from templates or custom definitions.

Supports two spawn mechanisms:
- spawn_agent(role, task) — uses a pre-defined template
- spawn_custom(name, instructions, task) — creates ad-hoc sub-agent

Sub-agents run in parallel (asyncio.gather) with a configurable slot limit.
Each spawn has its own budget. Results are collected and fed back to the parent.
"""
from __future__ import annotations

import asyncio
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
DEFAULT_MAX_CONCURRENT = 3  # Default concurrent sub-agent slots


@dataclass
class SpawnRequest:
    """Parsed spawn request from agent output."""
    role: str
    task: str
    # For spawn_custom:
    custom_name: str | None = None
    custom_instructions: str | None = None
    custom_tools: list[str] | None = None

    @property
    def is_custom(self) -> bool:
        return self.custom_instructions is not None


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
    Parse spawn blocks from agent response.

    Template spawn:
      ```spawn_agent
      {"role": "researcher", "task": "Find examples of OAuth"}
      ```

    Custom spawn:
      ```spawn_custom
      {"name": "security-auditor", "instructions": "You are a security expert...", "task": "Check for SQL injection", "tools": ["Bash", "Read"]}
      ```
    """
    requests: list[SpawnRequest] = []

    # Parse spawn_agent blocks
    for match in re.findall(r'```spawn_agent\s*\n([\s\S]*?)\n```', text):
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict) and "role" in data and "task" in data:
                requests.append(SpawnRequest(role=data["role"], task=data["task"]))
        except (json.JSONDecodeError, KeyError):
            continue

    # Parse spawn_custom blocks
    for match in re.findall(r'```spawn_custom\s*\n([\s\S]*?)\n```', text):
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict) and "instructions" in data and "task" in data:
                name = data.get("name", f"custom-{len(requests)}")
                requests.append(SpawnRequest(
                    role="custom",
                    task=data["task"],
                    custom_name=name,
                    custom_instructions=data["instructions"],
                    custom_tools=data.get("tools"),
                ))
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
    """Format sub-agent templates + custom spawn instructions for the system prompt."""
    lines = ["\n\n## Sub-agents"]
    lines.append("You can spawn sub-agents to help with specific tasks.")
    lines.append("Each sub-agent runs independently and returns its result to you.")
    lines.append("You can spawn multiple sub-agents in one response — they run in parallel.")
    lines.append("")

    if templates:
        lines.append("### Available templates:")
        for t in templates:
            role = t.get("role", "unknown")
            desc = t.get("description", "") or t.get("name", role)
            lines.append(f"- **{role}** — {desc}")
        lines.append("")
        lines.append("To spawn a template sub-agent:")
        lines.append('```spawn_agent\n{"role": "<role>", "task": "<specific task description>"}\n```')
        lines.append("")

    lines.append("### Custom sub-agents:")
    lines.append("You can also create ad-hoc sub-agents for any task:")
    lines.append('```spawn_custom\n{"name": "<name>", "instructions": "<system prompt>", "task": "<task>", "tools": ["Bash", "Read", "Grep"]}\n```')
    lines.append("")
    lines.append("Rules:")
    lines.append(f"- Max {MAX_SUB_AGENTS_PER_TURN} sub-agents per response")
    lines.append(f"- Max {DEFAULT_MAX_CONCURRENT} run in parallel")
    lines.append("- Results arrive in your next turn — continue after receiving them")
    lines.append("- Use sub-agents for parallelizable or specialized tasks")
    lines.append("- Don't spawn sub-agents for trivial tasks you can do directly")

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

    Creates an ephemeral runtime session, runs the task, collects output, cleans up.
    """
    sub_session_id = uuid.uuid4()
    sub_depth = parent_depth + 1
    sub_name = template.name

    if sub_depth > MAX_SUB_AGENT_DEPTH:
        return SubAgentResult(
            role=template.role,
            name=sub_name,
            output="",
            success=False,
            error=f"Max sub-agent depth ({MAX_SUB_AGENT_DEPTH}) exceeded",
        )

    # Notify frontend about sub-agent spawn
    await publish_event(ws_session_id, {
        "type": "sub_agent_spawned",
        "sub_session_id": str(sub_session_id),
        "role": template.role,
        "name": sub_name,
        "task": task,
    })

    output_parts: list[str] = []

    try:
        await runtime.start_session(
            session_id=sub_session_id,
            workdir=workdir,
            system_prompt=template.system_prompt,
            allowed_tools=template.allowed_tools,
            parent_session_id=parent_session.id,
        )

        async for event in runtime.send_message(sub_session_id, task):
            ev_type = event.get("type", "")

            if ev_type == "assistant_text":
                output_parts.append(event.get("content", ""))

            # Forward sub-agent events to frontend (prefixed)
            await publish_event(ws_session_id, {
                **event,
                "type": f"sub_agent_{ev_type}" if not ev_type.startswith("sub_agent_") else ev_type,
                "sub_session_id": str(sub_session_id),
                "sub_agent_name": sub_name,
                "sub_agent_role": template.role,
            })

        output = "".join(output_parts)

        await publish_event(ws_session_id, {
            "type": "sub_agent_done",
            "sub_session_id": str(sub_session_id),
            "role": template.role,
            "name": sub_name,
            "output_preview": output[:500] if output else "",
        })

        return SubAgentResult(
            role=template.role,
            name=sub_name,
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
            "name": sub_name,
            "error": error_msg,
        })

        return SubAgentResult(
            role=template.role,
            name=sub_name,
            output="",
            success=False,
            error=error_msg,
        )

    finally:
        await runtime.stop_session(sub_session_id)


async def run_spawn_requests(
    db: AsyncSession,
    parent_session: Session,
    requests: list[SpawnRequest],
    sub_agent_templates: list[dict],
    workdir: str,
    parent_depth: int,
    ws_session_id: str,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
) -> list[SubAgentResult]:
    """
    Run multiple spawn requests with concurrency limit.

    Uses asyncio.Semaphore to limit parallel sub-agents.
    Template spawns use find_template(); custom spawns create ephemeral templates.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[SubAgentResult] = []

    async def _run_one(req: SpawnRequest) -> SubAgentResult:
        async with semaphore:
            if req.is_custom:
                # Build ephemeral template from custom request
                template = SubAgentTemplate(
                    id=f"custom-{uuid.uuid4().hex[:8]}",
                    role="custom",
                    name=req.custom_name or "custom-agent",
                    system_prompt=req.custom_instructions or "You are a helpful assistant.",
                    allowed_tools=req.custom_tools or ["Read", "Bash", "Grep", "Glob"],
                    max_budget_usd=0.5,
                    description=f"Custom sub-agent: {req.custom_name}",
                )
            else:
                template = find_template(sub_agent_templates, req.role)
                if not template:
                    return SubAgentResult(
                        role=req.role,
                        name=req.role,
                        output="",
                        success=False,
                        error=f"No template found for role '{req.role}'",
                    )

            return await spawn_sub_agent(
                db=db,
                parent_session=parent_session,
                template=template,
                task=req.task,
                workdir=workdir,
                parent_depth=parent_depth,
                ws_session_id=ws_session_id,
            )

    # Run all requests with concurrency limit
    tasks = [_run_one(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    return list(results)


def format_sub_agent_results(results: list[SubAgentResult]) -> str:
    """Format sub-agent results as a message to feed back to the parent agent."""
    if not results:
        return ""

    parts = ["## Sub-agent Results\n"]
    for r in results:
        status = "OK" if r.success else "FAILED"
        parts.append(f"### {r.name} ({r.role}) — {status}")
        if r.success:
            parts.append(r.output if r.output else "(no output)")
        else:
            parts.append(f"**Error**: {r.error}")
        parts.append("")

    return "\n".join(parts)
