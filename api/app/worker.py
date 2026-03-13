"""
Task Worker — runs LangGraph graph in a separate process, decoupled from WebSocket.

Architecture (v2 — Peer Handoff):
- Graph handles ONE agent at a time, returns when done or handoff detected
- Worker manages peer transitions: graph ends with handoff → Worker creates/reuses
  session for next agent → starts new handle_session task
- Sub-agents (depth > 0) are spawned by run_agent_node when agent outputs spawn_agent blocks

Lifecycle:
1. WS handler publishes "start" to worker:sessions
2. Worker starts handle_session task for that session
3. Graph runs single agent, returns with handoff_result or done
4. If handoff: Worker creates next session, publishes new "start"
5. If done: Worker cleans up
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.agent import Agent
from app.models.session import Session as SessionModel
from app.schemas.session import SessionCreate
from app.services.event_bus import (
    clear_buffer,
    publish_command,
    publish_event,
    publish_notification,
    subscribe_commands,
)
from app.services.redis_service import init_redis, close_redis, get_redis
import app.services.graph_service as graph_svc
from app.services.graph_service import GraphConfigurable
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    create_session,
    get_session,
    stop_session,
)
from app.services.handoff_server import (
    format_handoff_tools_prompt,
    generate_handoff_tools,
)
from app.services.sub_agent_service import format_spawn_tools_prompt
from app.services.task_service import update_task_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventPublisher — drop-in for WebSocket in graph nodes
# ---------------------------------------------------------------------------

class EventPublisher:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def send_json(self, data: dict[str, Any]) -> None:
        await publish_event(self.session_id, data)


# ---------------------------------------------------------------------------
# Worker session handler
# ---------------------------------------------------------------------------

async def handle_session(session_id: uuid.UUID) -> None:
    sid = str(session_id)
    publisher = EventPublisher(sid)

    try:
        await _run_session(session_id, sid, publisher)
    except Exception as exc:
        logger.error("Session %s crashed: %s", sid, exc, exc_info=True)
        try:
            await publish_event(sid, {"type": "error", "error": f"Worker error: {exc}"})
        except Exception:
            pass
    finally:
        await runtime.stop_session(session_id)
        await clear_buffer(sid)
        logger.info("Session %s cleanup complete", sid)


async def _run_session(
    session_id: uuid.UUID, sid: str, publisher: EventPublisher,
) -> None:
    async with async_session() as db:
        try:
            session = await get_session(db, session_id)
        except SessionNotFoundError:
            await publish_event(sid, {"type": "error", "error": "Session not found"})
            return

        agent = session.agent
        system_prompt = agent.system_prompt

        # Add handoff tools from workflow edges
        workflow_id = None
        if session.task_id:
            await db.refresh(session, ["task"])
            if session.task and session.task.workflow_id:
                workflow_id = session.task.workflow_id
                handoff_tools = await generate_handoff_tools(db, agent.id, workflow_id)
                tools_prompt = format_handoff_tools_prompt(handoff_tools)
                if tools_prompt:
                    system_prompt += tools_prompt

        # Add sub-agent capabilities (templates + spawn_custom)
        # Always inject if agent has templates; spawn_custom is always available
        spawn_prompt = format_spawn_tools_prompt(agent.sub_agent_templates or [])
        if spawn_prompt:
            system_prompt += spawn_prompt

        # Resolve workdir
        workdir = ""
        product_workspace = None
        if session.task_id:
            if session.task and session.task.product_id:
                await db.refresh(session.task, ["product"])
                if session.task.product:
                    workdir = session.task.product.workspace_path
                    product_workspace = workdir
        if not workdir:
            workdir = agent.config.get("workdir", "") if agent.config else ""

        effective_workdir = workdir or settings.workspace_path
        if not os.path.isdir(effective_workdir):
            os.makedirs(effective_workdir, exist_ok=True)

        # Auto-init git
        git_dir = os.path.join(effective_workdir, ".git")
        if not os.path.exists(git_dir):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "init", cwd=effective_workdir,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            except Exception:
                pass

        # Start runtime
        if not runtime.is_running(session_id):
            try:
                await runtime.start_session(
                    session_id=session_id, workdir=workdir,
                    system_prompt=system_prompt,
                    claude_session_id=session.claude_session_id,
                    allowed_tools=agent.allowed_tools or [],
                )
            except Exception as exc:
                await publish_event(sid, {"type": "error", "error": str(exc)})
                return

        # LangGraph config
        configurable: GraphConfigurable = {
            "thread_id": sid,
            "websocket": publisher,
            "db": db,
            "task_id": session.task_id,
        }
        graph_config = {"configurable": configurable, "recursion_limit": 20}
        graph = graph_svc.get_graph()
        task_id = session.task_id

        # Restore interrupt state
        interrupted = await _restore_interrupt_state(
            graph, graph_config, publisher, sid, task_id
        )

        # Command loop
        async for command in subscribe_commands(sid):
            cmd_type = command.get("type")

            if cmd_type == "stop":
                await runtime.stop_session(session_id)
                await publish_event(sid, {"type": "done"})
                break

            if cmd_type == "message" and not interrupted:
                content = command.get("content", "")
                if not content:
                    await publish_event(sid, {"type": "error", "error": "Empty message"})
                    continue

                if not command.get("saved"):
                    await add_message(db, session_id, "user", content)
                await publish_event(sid, {"type": "status", "status": "thinking"})

                initial_state = {
                    "main_session_id": sid,
                    "current_session_id": sid,
                    "current_agent_id": str(agent.id),
                    "current_agent_name": agent.name,
                    "workflow_id": str(workflow_id) if workflow_id else None,
                    "task_id": str(task_id) if task_id else None,
                    "task": content,
                    "depth": 0,
                    "chain": [],
                    "handoff_result": None,
                    "product_workspace": product_workspace,
                    "gateway_approved": None,
                    "messages": [],
                }

                result = await _run_graph(graph, initial_state, graph_config)
                interrupted = await _handle_graph_result(
                    publisher, db, task_id, session, *result
                )

            elif cmd_type == "approve" and interrupted:
                await _try_update_task_status(db, task_id, "in_progress")
                await publish_event(sid, {"type": "status", "status": "thinking"})
                result = await _run_graph(graph, Command(resume=True), graph_config)
                interrupted = await _handle_graph_result(
                    publisher, db, task_id, session, *result
                )

            elif cmd_type == "reject" and interrupted:
                await _try_update_task_status(db, task_id, "in_progress")
                result = await _run_graph(graph, Command(resume=False), graph_config)
                interrupted = await _handle_graph_result(
                    publisher, db, task_id, session, *result
                )

            elif cmd_type == "message" and interrupted:
                await publish_event(sid, {
                    "type": "error",
                    "error": "Agent is waiting for approval. Send approve or reject first.",
                })


# ---------------------------------------------------------------------------
# Peer handoff — Worker creates next session
# ---------------------------------------------------------------------------

async def _handle_peer_handoff(
    db: AsyncSession,
    current_session: SessionModel,
    handoff_result: dict,
    chain: list,
    workflow_id: str | None,
    product_workspace: str | None,
) -> None:
    """Create/reuse peer session and tell Worker to start it."""
    target_id = uuid.UUID(handoff_result["to_agent_id"])
    target = await db.get(Agent, target_id)
    if not target:
        logger.warning("Handoff target agent %s not found", target_id)
        return

    prompt = handoff_result.get("prompt", "") or handoff_result.get("tool_args", {}).get("comment", "")
    task_id = current_session.task_id
    current_sid = str(current_session.id)

    # Emit handoff_start on current session
    await publish_event(current_sid, {
        "type": "handoff_start",
        "from_agent": current_session.agent.name,
        "to_agent": target.name,
        "task": prompt,
    })

    # Try to reuse existing session for this agent + task
    existing_session = None
    if task_id:
        stmt = (
            select(SessionModel)
            .where(
                SessionModel.agent_id == target_id,
                SessionModel.task_id == task_id,
                SessionModel.status == "active",
            )
            .order_by(SessionModel.created_at.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        existing_session = result.scalar_one_or_none()

    if existing_session:
        peer_session = existing_session
        logger.info("Reusing session %s for agent %s", peer_session.id, target.name)
    else:
        peer_session = await create_session(db, SessionCreate(agent_id=target.id))
        if task_id:
            peer_session.task_id = task_id
            await db.commit()
            await db.refresh(peer_session)

    # Add handoff prompt as user message
    await add_message(db, peer_session.id, "user", prompt)

    # Emit done on current session (this agent's work is finished)
    await publish_event(current_sid, {"type": "done"})

    # Notify worker to start the peer session
    r = get_redis()
    await r.publish("worker:sessions", json.dumps({
        "action": "start",
        "session_id": str(peer_session.id),
    }))

    logger.info(
        "Peer handoff: %s → %s (session %s)",
        current_session.agent.name, target.name, peer_session.id,
    )


# ---------------------------------------------------------------------------
# Graph execution helpers
# ---------------------------------------------------------------------------

async def _restore_interrupt_state(
    graph, graph_config: dict, publisher: EventPublisher,
    session_id: str, task_id: uuid.UUID | None,
) -> bool:
    try:
        graph_state = await graph.aget_state(graph_config)
        if graph_state and graph_state.next:
            state_values = graph_state.values or {}
            hr = state_values.get("handoff_result")
            if hr:
                steps = []
                for msg in state_values.get("messages", []):
                    if isinstance(msg, dict) and msg.get("agent"):
                        text = msg.get("text", "")
                        summary = text[:200] + "..." if len(text) > 200 else text
                        steps.append({"agent": msg["agent"], "summary": summary})
                await publisher.send_json({
                    "type": "approval_required",
                    "from_agent": state_values.get("current_agent_name", ""),
                    "to_agent": hr.get("to_agent_name", ""),
                    "task": hr.get("prompt", ""),
                    "task_id": str(task_id) if task_id else "",
                    "chain": state_values.get("chain", []),
                    "steps": steps,
                    "workflow_agents": [],
                })
            logger.info("Restored interrupted state for session %s", session_id)
            return True
    except Exception as exc:
        logger.warning("Failed to check graph state for %s: %s", session_id, exc)
    return False


async def _try_update_task_status(db, task_id, new_status):
    if not task_id:
        return
    try:
        await update_task_status(db, task_id, new_status)
    except Exception as exc:
        logger.error("Task %s status update to %s failed: %s", task_id, new_status, exc)


async def _handle_graph_result(
    publisher: EventPublisher,
    db: AsyncSession,
    task_id: uuid.UUID | None,
    session: SessionModel,
    interrupted: bool,
    completed: bool,
    errored: bool,
    last_state: dict | None = None,
) -> bool:
    """Handle graph result. Now includes peer handoff logic."""
    if errored:
        await publisher.send_json({"type": "done"})
        return False

    if interrupted:
        await _try_update_task_status(db, task_id, "awaiting_user")
        hr = (last_state or {}).get("handoff_result")
        if hr:
            steps = []
            for msg in (last_state or {}).get("messages", []):
                if isinstance(msg, dict) and msg.get("agent"):
                    text = msg.get("text", "")
                    summary = text[:200] + "..." if len(text) > 200 else text
                    steps.append({"agent": msg["agent"], "summary": summary})
            await publisher.send_json({
                "type": "approval_required",
                "from_agent": (last_state or {}).get("current_agent_name", ""),
                "to_agent": hr.get("to_agent_name", ""),
                "task": hr.get("prompt", ""),
                "task_id": str(task_id) if task_id else "",
                "chain": (last_state or {}).get("chain", []),
                "steps": steps,
                "workflow_agents": [],
            })
        return True

    # Check for peer handoff (gateway_approved=True + handoff_result)
    if last_state:
        gateway_approved = last_state.get("gateway_approved")
        hr = last_state.get("handoff_result")
        if gateway_approved and hr and hr.get("to_agent_id"):
            # Peer handoff — create next session, Worker starts it
            await _handle_peer_handoff(
                db, session, hr,
                chain=last_state.get("chain", []),
                workflow_id=last_state.get("workflow_id"),
                product_workspace=last_state.get("product_workspace"),
            )
            return False  # This session is done

    if completed:
        await _try_update_task_status(db, task_id, "done")

    await publisher.send_json({"type": "done"})
    return False


async def _run_graph(graph, input, config: dict) -> tuple[bool, bool, bool, dict | None]:
    publisher: EventPublisher = config["configurable"]["websocket"]
    db = config["configurable"]["db"]
    task_id = config["configurable"]["task_id"]
    completed = False
    last_state = None

    try:
        async for chunk in graph.astream(input, config, stream_mode="values"):
            if "__interrupt__" in chunk:
                return True, False, False, chunk
            last_state = chunk
            hr = chunk.get("handoff_result")
            if isinstance(hr, dict) and hr.get("result_type") == "completed":
                completed = True
    except Exception as exc:
        logger.error("Graph error for session %s: %s",
                     config["configurable"]["thread_id"], exc, exc_info=True)
        await publisher.send_json({"type": "error", "error": str(exc)})
        await _try_update_task_status(db, task_id, "error")
        await publish_notification("task_error", {
            "task_id": str(task_id) if task_id else "",
            "error": str(exc),
        })
        return False, False, True, None

    # Check for pending interrupts
    try:
        graph_state = await graph.aget_state(config)
        if graph_state and graph_state.next:
            return True, False, False, graph_state.values or {}
    except Exception as exc:
        logger.warning("Failed to check graph state: %s", exc)

    return False, completed, False, last_state


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

async def run_worker() -> None:
    await init_redis()

    postgres_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
        await checkpointer.setup()
        graph_svc._compiled_graph = graph_svc.build_graph(checkpointer)

        r = get_redis()
        logger.info("Worker started, listening for session commands...")

        pubsub = r.pubsub()
        await pubsub.subscribe("worker:sessions")

        active_tasks: dict[str, asyncio.Task] = {}

        try:
            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue
                try:
                    data = json.loads(raw_message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                action = data.get("action")
                sid = data.get("session_id")
                if not sid:
                    continue

                if action == "start":
                    if sid in active_tasks and not active_tasks[sid].done():
                        logger.warning("Session %s already active in worker", sid)
                        continue
                    task = asyncio.create_task(
                        handle_session(uuid.UUID(sid)),
                        name=f"worker-session-{sid}",
                    )
                    active_tasks[sid] = task
                    task.add_done_callback(lambda t, s=sid: active_tasks.pop(s, None))

        finally:
            await pubsub.unsubscribe("worker:sessions")
            await pubsub.aclose()
            for task in active_tasks.values():
                task.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks.values(), return_exceptions=True)

    await close_redis()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
