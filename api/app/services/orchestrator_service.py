from __future__ import annotations

import json
import logging
import re
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.schemas.session import SessionCreate
from app.services.agent_link_service import get_agent_handoff_targets
from app.services.runtime import runtime
from app.services.session_service import add_message, create_session

logger = logging.getLogger(__name__)

MAX_HANDOFF_HOPS = 5


# ---------------------------------------------------------------------------
# Prompt helpers (moved from ws.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def handle_handoff(
    websocket: WebSocket,
    db: AsyncSession,
    main_session_id: uuid.UUID,
    from_agent: Agent,
    response_text: str,
    handoff_targets: list[Agent],
    chain: list[tuple[str, str]],
    depth: int,
) -> None:
    """
    Автоматически запускает следующего агента если в ответе есть handoff-блок.

    Ключевые концепции P3:
    - Routing: target ищется в handoff_targets (граф из БД через agent_links)
    - Session creation: для каждого агента создаётся DB Session (не ephemeral run_task)
    - Cycle detection: chain отслеживает уже пройденные пары
    - Нет feedback loop: main-агент не вызывается повторно с результатами sub-агента
    """
    if depth >= MAX_HANDOFF_HOPS:
        logger.warning("Max handoff depth %d reached", MAX_HANDOFF_HOPS)
        return

    block = parse_handoff_block(response_text)
    if not block:
        return

    target_name = block["to"]
    task_message = block["message"]

    # --- Routing: найти target в таблице маршрутизации (agent_links из БД) ---
    target = next((a for a in handoff_targets if a.name == target_name), None)
    if not target:
        logger.warning("Handoff target '%s' not found in agent_links", target_name)
        return

    # --- Cycle detection: предотвратить бесконечные петли ---
    current_pair = (from_agent.name, target.name)
    if chain.count(current_pair) >= 1:
        await websocket.send_json({
            "type": "handoff_cycle_detected",
            "message": f"Cycle detected: {from_agent.name} → {target.name}",
        })
        return

    await websocket.send_json({
        "type": "handoff_start",
        "from_agent": from_agent.name,
        "to_agent": target.name,
        "task": task_message,
    })

    # --- Session creation: создать DB Session для target-агента ---
    # В отличие от run_task() (ephemeral), сессия сохраняется в БД.
    # Результат работы Reviewer виден в интерфейсе как отдельная сессия.
    sub_targets = await get_agent_handoff_targets(db, target.id)
    system_prompt = _build_agent_prompt(target, chain + [current_pair], sub_targets)

    target_db_session = await create_session(db, SessionCreate(agent_id=target.id))
    await add_message(db, target_db_session.id, "user", task_message)

    workdir = (
        (target.config.get("workdir") or settings.workspace_path)
        if target.config
        else settings.workspace_path
    )
    await runtime.start_session(
        session_id=target_db_session.id,
        workdir=workdir,
        system_prompt=system_prompt,
    )

    # --- Execution: запустить агента и стримить события в WebSocket ---
    sub_text = ""
    sub_tools: list[dict] = []
    try:
        async for event in runtime.send_message(target_db_session.id, task_message):
            ev_type = event.get("type")
            if ev_type == "assistant_text":
                sub_text += event.get("content", "")
            if ev_type == "tool_use":
                sub_tools.append({
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input", {}),
                })
            await websocket.send_json({
                **event,
                "type": f"sub_agent_{ev_type}",
                "agent_name": target.name,
            })
    except WebSocketDisconnect:
        await runtime.stop_session(target_db_session.id)
        raise
    except Exception as exc:
        logger.error("Sub-agent %s error: %s", target.name, exc)
        await websocket.send_json({
            "type": "sub_agent_error",
            "agent_name": target.name,
            "error": str(exc),
        })

    await runtime.stop_session(target_db_session.id)
    await websocket.send_json({"type": "handoff_done", "agent_name": target.name})

    # Сохранить результат в сессии target-агента и в основной сессии
    if sub_text or sub_tools:
        await add_message(
            db, target_db_session.id, "assistant",
            sub_text,
            tool_uses=sub_tools or None,
        )
        await add_message(
            db, main_session_id, "assistant",
            f"[{target.name}]: {sub_text}",
            tool_uses=sub_tools or None,
        )

    # Рекурсия: проверить, хочет ли target-агент сам передать дальше
    if sub_text and sub_targets:
        await handle_handoff(
            websocket=websocket,
            db=db,
            main_session_id=main_session_id,
            from_agent=target,
            response_text=sub_text,
            handoff_targets=sub_targets,
            chain=chain + [current_pair],
            depth=depth + 1,
        )


def _build_agent_prompt(
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
