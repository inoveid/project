"""
P4: LangGraph Redesign

Заменяет рекурсивный handle_handoff() из P3 граф-автоматом с:
- TypedDict State — явное состояние вместо стека вызовов
- PostgresSaver — checkpoint после каждого узла
- interrupt() — HITL gate: пауза до одобрения человека
- Conditional edges — явная маршрутизация вместо if/else
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal, TypedDict

from fastapi import WebSocket
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.session import SessionCreate
from app.services.agent_link_service import get_agent_handoff_targets
from app.services.orchestrator_service import (
    _build_agent_prompt,
    parse_handoff_block,
)
from app.services.runtime import runtime
from app.services.session_service import SessionNotFoundError, add_message, create_session, get_session

logger = logging.getLogger(__name__)

MAX_DEPTH = 5

# ---------------------------------------------------------------------------
# State — всё, что LangGraph сохраняет в checkpoint
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    """
    Состояние графа, персистируемое в PostgreSQL после каждого узла.

    Ключевые концепции:
    - main_session_id: WebSocket-сессия (не меняется)
    - current_session_id: claude CLI сессия текущего агента (меняется при handoff)
    - depth: 0 = главный агент, >0 = sub-агент
    - chain: [[from, to], ...] — для детектирования циклов
    - gateway_approved: True/False/None — исход HITL gate
    """
    main_session_id: str
    current_session_id: str
    current_agent_id: str
    current_agent_name: str
    task: str
    depth: int
    chain: list            # [[from_name, to_name], ...]
    handoff_target: str | None
    handoff_message: str | None
    gateway_approved: bool | None
    messages: list         # [{agent, text, tools}] — накопленные результаты


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def run_agent_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Запустить текущего агента через claude CLI и стримить события в WebSocket.

    Для depth==0 (главный агент): runtime уже запущен из ws.py, не останавливаем.
    Для depth>0 (sub-агент): runtime запущен в gate_node, останавливаем здесь.
    """
    ws: WebSocket = config["configurable"]["websocket"]
    db: AsyncSession = config["configurable"]["db"]
    is_sub = state["depth"] > 0
    session_id = uuid.UUID(state["current_session_id"])

    full_text = ""
    tool_uses: list[dict] = []

    try:
        async for event in runtime.send_message(session_id, state["task"]):
            ev_type = event.get("type", "")
            if ev_type == "assistant_text":
                full_text += event.get("content", "")
            elif ev_type == "tool_use":
                tool_uses.append({
                    "tool_name": event.get("tool_name", ""),
                    "tool_input": event.get("tool_input", {}),
                })
            # Sub-агенты получают префикс sub_agent_ для UI
            if is_sub:
                await ws.send_json({
                    **event,
                    "type": f"sub_agent_{ev_type}",
                    "agent_name": state["current_agent_name"],
                })
            else:
                await ws.send_json(event)
    except Exception as exc:
        logger.error("Agent %s error: %s", state["current_agent_name"], exc)
        if is_sub:
            await ws.send_json({
                "type": "sub_agent_error",
                "agent_name": state["current_agent_name"],
                "error": str(exc),
            })
        else:
            await ws.send_json({"type": "error", "error": str(exc)})

    # Sub-агент завершил работу — остановить runtime и уведомить UI
    if is_sub:
        await runtime.stop_session(session_id)
        await ws.send_json({"type": "handoff_done", "agent_name": state["current_agent_name"]})

    # Сохранить результат в БД
    if full_text or tool_uses:
        await add_message(db, session_id, "assistant", full_text, tool_uses=tool_uses or None)
        if is_sub:
            # Дублировать в основную сессию для истории
            await add_message(
                db, uuid.UUID(state["main_session_id"]), "assistant",
                f"[{state['current_agent_name']}]: {full_text}",
            )

    # Сохранить claude_session_id для resume (только главный агент)
    if not is_sub:
        claude_sid = runtime.get_claude_session_id(session_id)
        if claude_sid:
            try:
                session = await get_session(db, session_id)
                session.claude_session_id = claude_sid
                await db.commit()
            except SessionNotFoundError:
                pass

    # Разобрать handoff-блок из ответа
    block = parse_handoff_block(full_text)

    return {
        "messages": state["messages"] + [{
            "agent": state["current_agent_name"],
            "text": full_text,
            "tools": tool_uses,
        }],
        "handoff_target": block["to"] if block else None,
        "handoff_message": block["message"] if block else None,
        "gateway_approved": None,  # сбросить флаг для следующего цикла
    }


async def notify_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Уведомить WebSocket о предстоящем handoff и запросить одобрение.

    Этот узел выполняется ОДИН РАЗ — до gate_node.
    При resume графа (после interrupt) gate_node перезапускается, но
    notify_handoff_node — нет. Поэтому approval_required отправляется
    ровно один раз, без дублирования.
    """
    ws: WebSocket = config["configurable"]["websocket"]
    await ws.send_json({
        "type": "approval_required",
        "from_agent": state["current_agent_name"],
        "to_agent": state["handoff_target"],
        "task": state["handoff_message"],
    })
    return {}


async def gate_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    HITL gate: пауза до решения человека.

    interrupt() — ключевая концепция LangGraph:
    1. Первый запуск: сохраняет state в checkpoint и паузирует граф
    2. Resume с Command(resume=True/False): возвращает True/False
    3. Код ПОСЛЕ interrupt() продолжает выполнение

    На одобрение: создаёт сессию sub-агента, запускает runtime.
    На отклонение: отменяет handoff.
    """
    db: AsyncSession = config["configurable"]["db"]
    ws: WebSocket = config["configurable"]["websocket"]

    # Здесь граф паузируется. При resume — возвращает значение из Command(resume=...).
    approved: bool = interrupt("Waiting for human approval of handoff")

    if not approved:
        return {"gateway_approved": False, "handoff_target": None, "handoff_message": None}

    # Найти target-агента через agent_links (граф маршрутизации из БД)
    from_agent_id = uuid.UUID(state["current_agent_id"])
    targets = await get_agent_handoff_targets(db, from_agent_id)
    target = next((a for a in targets if a.name == state["handoff_target"]), None)

    if not target:
        logger.warning("Handoff target '%s' not found in agent_links", state["handoff_target"])
        return {"gateway_approved": False, "handoff_target": None, "handoff_message": None}

    # Детектирование циклов: [[from, to], ...] из state
    current_pair = [state["current_agent_name"], target.name]
    if current_pair in state["chain"]:
        await ws.send_json({
            "type": "handoff_cycle_detected",
            "message": f"Cycle detected: {state['current_agent_name']} → {target.name}",
        })
        return {"gateway_approved": False, "handoff_target": None, "handoff_message": None}

    # Создать DB Session для sub-агента (в отличие от ephemeral run_task, сохраняется в БД)
    sub_session = await create_session(db, SessionCreate(agent_id=target.id))
    await add_message(db, sub_session.id, "user", state["handoff_message"])

    # Построить системный промпт с контекстом цепочки
    sub_targets = await get_agent_handoff_targets(db, target.id)
    chain_tuples = [tuple(p) for p in state["chain"]] + [tuple(current_pair)]
    system_prompt = _build_agent_prompt(target, list(chain_tuples), sub_targets)

    # Запустить runtime sub-агента
    workdir = (target.config.get("workdir") or settings.workspace_path) if target.config else settings.workspace_path
    await runtime.start_session(sub_session.id, workdir, system_prompt, allowed_tools=target.allowed_tools or [])

    # Уведомить UI о начале handoff
    await ws.send_json({
        "type": "handoff_start",
        "from_agent": state["current_agent_name"],
        "to_agent": target.name,
        "task": state["handoff_message"],
    })

    return {
        "gateway_approved": True,
        "current_session_id": str(sub_session.id),
        "current_agent_id": str(target.id),
        "current_agent_name": target.name,
        "task": state["handoff_message"],
        "depth": state["depth"] + 1,
        "chain": state["chain"] + [current_pair],
        "handoff_target": None,
        "handoff_message": None,
    }


# ---------------------------------------------------------------------------
# Routing edges — явная маршрутизация по state
# ---------------------------------------------------------------------------

def route_after_agent(state: WorkflowState) -> Literal["notify_handoff", "__end__"]:
    """Если агент сгенерировал handoff-блок и не превышена глубина → gate."""
    if state.get("handoff_target") and state["depth"] < MAX_DEPTH:
        return "notify_handoff"
    return END


def route_after_gate(state: WorkflowState) -> Literal["run_agent", "__end__"]:
    """Если одобрено → снова run_agent (для sub-агента). Иначе → END."""
    if state.get("gateway_approved"):
        return "run_agent"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer: AsyncPostgresSaver):
    """
    Граф:
        START → run_agent → [notify_handoff → gate → run_agent (цикл)] | END

    Checkpointing: после каждого узла состояние сохраняется в PostgreSQL.
    Thread ID = session_id → отдельная история для каждой сессии.
    Time-travel: любой прошлый checkpoint можно загрузить и воспроизвести.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("run_agent", run_agent_node)
    graph.add_node("notify_handoff", notify_handoff_node)
    graph.add_node("gate", gate_node)

    graph.add_edge(START, "run_agent")
    graph.add_conditional_edges("run_agent", route_after_agent)
    graph.add_edge("notify_handoff", "gate")
    graph.add_conditional_edges("gate", route_after_gate)

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Module-level singleton (инициализируется в lifespan main.py)
# ---------------------------------------------------------------------------

_compiled_graph = None


def get_graph():
    if _compiled_graph is None:
        raise RuntimeError("Workflow graph not initialized. Call setup_graph() in app lifespan.")
    return _compiled_graph
