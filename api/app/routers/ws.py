"""
WebSocket handler — использует LangGraph граф (P4) вместо прямого вызова orchestrator.

Ключевые изменения относительно P3:
- _stream_response() + handle_handoff() заменены на graph.astream()
- interrupt() в gate_node паузирует граф до approve/reject от пользователя
- Checkpointing: при сбое LLM API можно resume с последнего checkpoint
- Time-travel: можно откатиться к любому прошлому checkpoint через DB
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.agent_link_service import get_agent_handoff_targets
from app.services.graph_service import WorkflowState, get_graph
from app.services.utils.handoff import format_handoff_instructions
from app.services.runtime import runtime
from app.services.session_service import SessionNotFoundError, add_message, get_session, stop_session
from app.services.task_service import update_task_status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await websocket.accept()

    try:
        session = await get_session(db, session_id)
    except SessionNotFoundError:
        await websocket.send_json({"type": "error", "error": "Session not found"})
        await websocket.close(code=4004)
        return

    agent = session.agent
    handoff_targets = await get_agent_handoff_targets(db, agent.id)

    system_prompt = agent.system_prompt
    if handoff_targets:
        system_prompt = system_prompt + format_handoff_instructions(handoff_targets)

    # Определить workdir: из task → product → workspace_path
    workdir = ""
    if session.task_id:
        await db.refresh(session, ["task"])
        if session.task and session.task.product_id:
            await db.refresh(session.task, ["product"])
            if session.task.product:
                workdir = session.task.product.workspace_path
    # Fallback: legacy sessions without task use agent.config.workdir
    if not workdir:
        workdir = agent.config.get("workdir", "") if agent.config else ""

    # Запустить runtime главного агента (один раз, живёт всю сессию)
    if not runtime.is_running(session_id):
        try:
            await runtime.start_session(
                session_id=session_id,
                workdir=workdir,
                system_prompt=system_prompt,
                claude_session_id=session.claude_session_id,
                allowed_tools=agent.allowed_tools or [],
            )
        except Exception as exc:
            await websocket.send_json({"type": "error", "error": str(exc)})
            await websocket.close(code=4000)
            return

    # LangGraph config: thread_id = session_id для checkpointing
    # Все non-serializable объекты (websocket, db, task_id) передаются через configurable —
    # они НЕ персистируются в checkpoint, нужно передавать при каждом astream()
    graph_config = {
        "configurable": {
            "thread_id": str(session_id),
            "websocket": websocket,
            "db": db,
            "task_id": session.task_id,
        },
        "recursion_limit": 20,
    }
    graph = get_graph()

    try:
        await _handle_messages(websocket, db, session_id, agent, graph, graph_config)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
        # Закрыть orphaned child sessions в БД до того, как stop_session очистит _children
        for child_id in runtime.get_children(session_id):
            try:
                await stop_session(db, child_id)
            except SessionNotFoundError:
                pass
        await runtime.stop_session(session_id)


async def _try_update_task_status(
    db: AsyncSession,
    task_id: uuid.UUID | None,
    new_status: str,
) -> None:
    """Update task status silently — errors must not break the WS flow."""
    if not task_id:
        return
    try:
        await update_task_status(db, task_id, new_status)
    except HTTPException as exc:
        # Expected: invalid transition (e.g. already in target status)
        logger.info("Task %s status update to %s skipped: %s", task_id, new_status, exc.detail)
    except Exception as exc:
        # Unexpected: DB error, bug — log as error for investigation
        logger.error("Task %s status update to %s failed: %s", task_id, new_status, exc)


async def _handle_messages(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    agent,
    graph,
    graph_config: dict,
) -> None:
    """
    Основной цикл WebSocket.

    Поддерживаемые типы сообщений от клиента:
    - {"type": "message", "content": "..."}  — новое сообщение агенту
    - {"type": "approve"}                    — одобрить handoff (resume после interrupt)
    - {"type": "reject"}                     — отклонить handoff (resume после interrupt)
    - {"type": "stop"}                       — остановить агента
    """
    interrupted = False  # True когда граф паузирован в gate_node (ждёт approve/reject)
    task_id = graph_config["configurable"]["task_id"]

    while True:
        raw = await websocket.receive_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "error": "Invalid JSON"})
            continue

        msg_type = data.get("type")

        if msg_type == "stop":
            await runtime.stop_session(session_id)
            await websocket.send_json({"type": "done"})
            break

        if msg_type == "message" and not interrupted:
            content = data.get("content", "")
            if not content:
                await websocket.send_json({"type": "error", "error": "Empty message content"})
                continue

            await add_message(db, session_id, "user", content)

            initial_state: WorkflowState = {
                "main_session_id": str(session_id),
                "current_session_id": str(session_id),
                "current_agent_id": str(agent.id),
                "current_agent_name": agent.name,
                "task": content,
                "depth": 0,
                "chain": [],
                "handoff_target": None,
                "handoff_message": None,
                "gateway_approved": None,
                "messages": [],
            }

            interrupted = await _run_graph(graph, initial_state, graph_config)
            if interrupted:
                await _try_update_task_status(db, task_id, "awaiting_user")
            else:
                await websocket.send_json({"type": "done"})

        elif msg_type == "approve" and interrupted:
            # Возобновить граф с approval=True
            # gate_node: interrupt() вернёт True → создаст sub-агента → run_agent
            await _try_update_task_status(db, task_id, "in_progress")
            interrupted = await _run_graph(
                graph, Command(resume=True), graph_config
            )
            if interrupted:
                await _try_update_task_status(db, task_id, "awaiting_user")
            else:
                await websocket.send_json({"type": "done"})

        elif msg_type == "reject" and interrupted:
            # Возобновить граф с approval=False
            # gate_node: interrupt() вернёт False → отменит handoff → END
            interrupted = await _run_graph(
                graph, Command(resume=False), graph_config
            )
            if not interrupted:
                await websocket.send_json({"type": "done"})

        elif msg_type == "message" and interrupted:
            await websocket.send_json({
                "type": "error",
                "error": "Agent is waiting for your approval. Send approve or reject first.",
            })

        else:
            await websocket.send_json({"type": "error", "error": f"Unknown type: {msg_type}"})


async def _run_graph(graph, input, config: dict) -> bool:
    """
    Стримить граф до завершения или interrupt().

    Возвращает True если граф паузировался (interrupt), False если завершился.
    """
    websocket: WebSocket = config["configurable"]["websocket"]
    db: AsyncSession = config["configurable"]["db"]
    task_id: uuid.UUID | None = config["configurable"]["task_id"]

    try:
        async for chunk in graph.astream(input, config, stream_mode="values"):
            if "__interrupt__" in chunk:
                # Граф паузирован — ждём approve/reject от пользователя
                return True
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        logger.error("Graph execution error: %s", exc)
        await websocket.send_json({"type": "error", "error": str(exc)})
        await _try_update_task_status(db, task_id, "error")

    return False
