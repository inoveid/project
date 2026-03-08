from __future__ import annotations

import json
import re

from app.models.agent import Agent


def format_handoff_instructions(targets: list[Agent]) -> str:
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
    """Parse ```handoff {...} ``` block from agent response."""
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
