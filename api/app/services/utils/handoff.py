"""
DEPRECATED: Text-based handoff utilities.

Superseded by app.services.handoff_server which provides workflow-based
MCP handoff tools. These functions remain for backward compatibility
with existing tests and will be removed in a future cleanup task.
"""
from __future__ import annotations

import json
import re
import warnings

from app.models.agent import Agent


def format_handoff_instructions(targets: list[Agent]) -> str:
    """DEPRECATED: Use handoff_server.format_handoff_tools_prompt instead."""
    warnings.warn(
        "format_handoff_instructions is deprecated, use handoff_server.format_handoff_tools_prompt",
        DeprecationWarning,
        stacklevel=2,
    )
    lines = ["\n\n## Available Handoff Targets"]
    lines.append("You can delegate tasks to the following agents:")
    for a in targets:
        desc = f" — {a.description}" if a.description else ""
        lines.append(f"- **{a.name}** ({a.role}){desc}")
    lines.append("\nTo hand off, include at the END of your response:")
    lines.append('```handoff\n{"to": "<agent name>", "message": "<full context>"}\n```')
    lines.append("Only hand off when you have completed your part of the task.")
    return "\n".join(lines)


def parse_handoff_block(text: str) -> dict | None:
    """DEPRECATED: Use handoff_server.parse_handoff_from_text instead."""
    warnings.warn(
        "parse_handoff_block is deprecated, use handoff_server.parse_handoff_from_text",
        DeprecationWarning,
        stacklevel=2,
    )
    match = re.search(r'```handoff\s*\n([\s\S]*?)\n```', text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
        if isinstance(data.get("to"), str) and isinstance(data.get("message"), str):
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def build_agent_prompt(
    agent: Agent,
    chain: list[tuple[str, str]],
    sub_targets: list[Agent],
) -> str:
    """DEPRECATED: Prompt building is now handled by graph_service._create_sub_session."""
    warnings.warn(
        "build_agent_prompt is deprecated, prompt building moved to graph_service",
        DeprecationWarning,
        stacklevel=2,
    )
    prompt = agent.system_prompt
    if chain:
        history = " → ".join(f"{a}→{b}" for a, b in chain)
        prompt += f"\n\n## Handoff Chain Context\nChain so far: {history} → {agent.name} (you)"
    workdir = agent.config.get("workdir") if agent.config else None
    if workdir:
        prompt += f"\nWorking directory: {workdir}"
    if sub_targets:
        prompt += format_handoff_instructions(sub_targets)
    return prompt
