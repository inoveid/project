"""
WebSocket handler — uses LangGraph graph (P5) with workflow-based MCP handoff tools.

Key changes from P4:
- Handoff tools generated from workflow edges (not agent_links)
- format_handoff_instructions replaced by format_handoff_tools_prompt
- get_agent_handoff_targets removed (agent_links table deleted)
- Task completion and max_cycles events handled by graph nodes
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.graph_service import WorkflowState, get_graph
from app.services.handoff_server import (
    format_handoff_tools_prompt,
    generate_handoff_tools,
)
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
    stop_session,
)
from app.services.notification_service import broadcast_notification
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
    system_prompt = agent.system_prompt

    # Add handoff tools from workflow edges (if session has a task with workflow)
    workflow_id = None
    if session.task_id:
        await db.refresh(session, ["task"])
        if session.task and session.task.workflow_id:
            workflow_id = session.task.workflow_id
            handoff_tools = await generate_handoff_tools(db, agent.id, workflow_id)
            tools_prompt = format_handoff_tools_prompt(handoff_tools)
            if tools_prompt:
                system_prompt += tools_prompt

    # Resolve workdir: task → product → workspace_path
    workdir = ""
    if session.task_id:
        if session.task and session.task.product_id:
            await db.refresh(session.task, ["product"])
            if session.task.product:
                workdir = session.task.product.workspace_path
    # Fallback: legacy sessions without task use agent.config.workdir
    if not workdir:
        workdir = agent.config.get("workdir", "") if agent.config else ""

    # Start main agent runtime (once, lives for the session)
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

    # LangGraph config
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
        await _handle_messages(
            websocket, db, session_id, agent, graph, graph_config,
            workflow_id=workflow_id,
        )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
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
        logger.info("Task %s status update to %s skipped: %s", task_id, new_status, exc.detail)
    except Exception as exc:
        logger.error("Task %s status update to %s failed: %s", task_id, new_status, exc)


async def _handle_graph_result(
    websocket: WebSocket,
    db: AsyncSession,
    task_id: uuid.UUID | None,
    interrupted: bool,
    completed: bool,
    errored: bool,
) -> bool:
    """
    Handle graph result: update task status and send done event.

    Returns the new `interrupted` state.
    """
    if errored:
        # Error already sent by _run_graph; task status already set to "error"
        await websocket.send_json({"type": "done"})
        return False

    if interrupted:
        await _try_update_task_status(db, task_id, "awaiting_user")
        return True

    if completed:
        await _try_update_task_status(db, task_id, "done")

    await websocket.send_json({"type": "done"})
    return False


async def _handle_messages(
    websocket: WebSocket,
    db: AsyncSession,
    session_id: uuid.UUID,
    agent,
    graph,
    graph_config: dict,
    workflow_id: uuid.UUID | None = None,
) -> None:
    """
    Main WebSocket message loop.

    Supported client message types:
    - {"type": "message", "content": "..."}  — new message to agent
    - {"type": "approve"}                    — approve handoff (resume after interrupt)
    - {"type": "reject"}                     — reject handoff (resume after interrupt)
    - {"type": "stop"}                       — stop agent
    """
    interrupted = False
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
            await websocket.send_json({"type": "status", "status": "thinking"})

            initial_state: WorkflowState = {
                "main_session_id": str(session_id),
                "current_session_id": str(session_id),
                "current_agent_id": str(agent.id),
                "current_agent_name": agent.name,
                "workflow_id": str(workflow_id) if workflow_id else None,
                "task_id": str(task_id) if task_id else None,
                "task": content,
                "depth": 0,
                "chain": [],
                "handoff_result": None,
                "gateway_approved": None,
                "messages": [],
            }

            result = await _run_graph(graph, initial_state, graph_config)
            interrupted = await _handle_graph_result(
                websocket, db, task_id, *result,
            )

        elif msg_type == "approve" and interrupted:
            await _try_update_task_status(db, task_id, "in_progress")
            await websocket.send_json({"type": "status", "status": "thinking"})
            result = await _run_graph(
                graph, Command(resume=True), graph_config
            )
            interrupted = await _handle_graph_result(
                websocket, db, task_id, *result,
            )

        elif msg_type == "reject" and interrupted:
            await _try_update_task_status(db, task_id, "in_progress")
            result = await _run_graph(
                graph, Command(resume=False), graph_config
            )
            interrupted = await _handle_graph_result(
                websocket, db, task_id, *result,
            )

        elif msg_type == "message" and interrupted:
            await websocket.send_json({
                "type": "error",
                "error": "Agent is waiting for your approval. Send approve or reject first.",
            })

        else:
            await websocket.send_json({"type": "error", "error": f"Unknown type: {msg_type}"})


async def _run_graph(graph, input, config: dict) -> tuple[bool, bool, bool]:
    """
    Stream graph until completion or interrupt.

    Returns (interrupted, completed, errored):
    - (True, False, False) if graph paused at interrupt
    - (False, True, False) if task_completed event was seen
    - (False, False, True) if graph raised an exception
    - (False, False, False) if graph finished normally
    """
    websocket: WebSocket = config["configurable"]["websocket"]
    db: AsyncSession = config["configurable"]["db"]
    task_id: uuid.UUID | None = config["configurable"]["task_id"]
    completed = False

    try:
        async for chunk in graph.astream(input, config, stream_mode="values"):
            if "__interrupt__" in chunk:
                return True, False, False
            # Check if task was completed via complete_task tool
            hr = chunk.get("handoff_result")
            if isinstance(hr, dict) and hr.get("result_type") == "completed":
                completed = True
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        logger.error("Graph execution error: %s", exc)
        await websocket.send_json({"type": "error", "error": str(exc)})
        await _try_update_task_status(db, task_id, "error")
        await broadcast_notification("task_error", {
            "task_id": str(task_id) if task_id else "",
            "error": str(exc),
        })
        return False, False, True

    return False, completed, False
