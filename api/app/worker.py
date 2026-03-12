"""
Task Worker — runs LangGraph graph in a separate process, decoupled from WebSocket.

Lifecycle:
1. API receives command (message/approve/reject/stop) via WS
2. API publishes command to Redis channel session:{id}:commands
3. Worker subscribes to commands, runs graph, publishes events to session:{id}:events
4. WS handler subscribes to events and forwards to client

The Worker uses an EventPublisher instead of WebSocket to emit events.
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

from app.config import settings
from app.database import async_session
from app.services.event_bus import (
    clear_buffer,
    publish_event,
    publish_notification,
    subscribe_commands,
)
from app.services.redis_service import init_redis, close_redis
import app.services.graph_service as graph_svc
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
    stop_session,
)
from app.services.handoff_server import (
    format_handoff_tools_prompt,
    generate_handoff_tools,
)
from app.services.task_service import update_task_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventPublisher — drop-in replacement for WebSocket in graph nodes
# ---------------------------------------------------------------------------

class EventPublisher:
    """
    Mimics WebSocket.send_json() interface but publishes to Redis.
    Graph nodes call `await ws.send_json(event)` — this makes it work
    without any changes to node signatures.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def send_json(self, data: dict[str, Any]) -> None:
        await publish_event(self.session_id, data)


# ---------------------------------------------------------------------------
# Worker session handler
# ---------------------------------------------------------------------------

async def handle_session(session_id: uuid.UUID) -> None:
    """
    Handle a single session: subscribe to commands, run graph, publish events.
    Called when a new session command arrives.
    """
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
        # Cleanup — always runs, even on crash
        for child_id in runtime.get_children(session_id):
            try:
                async with async_session() as cleanup_db:
                    await stop_session(cleanup_db, child_id)
            except SessionNotFoundError:
                pass
            except Exception as exc:
                logger.warning("Failed to stop child %s: %s", child_id, exc)
        await runtime.stop_session(session_id)
        await clear_buffer(sid)
        logger.info("Session %s cleanup complete", sid)


async def _run_session(
    session_id: uuid.UUID, sid: str, publisher: EventPublisher,
) -> None:
    """Core session logic — separated for try/finally in handle_session."""
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

        # Resolve workdir from product (primary) or agent config (fallback)
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

        # Ensure workspace directory exists
        effective_workdir = workdir or settings.workspace_path
        if not os.path.isdir(effective_workdir):
            os.makedirs(effective_workdir, exist_ok=True)
            logger.info("Created workspace directory: %s", effective_workdir)

        # Auto-init git if not present (agents need git for tracking changes)
        git_dir = os.path.join(effective_workdir, ".git")
        if not os.path.exists(git_dir):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "init",
                    cwd=effective_workdir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    logger.info("Initialized git in %s", effective_workdir)
            except Exception as exc:
                logger.warning("Failed to init git in %s: %s", effective_workdir, exc)

        # Start runtime
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
                await publish_event(sid, {"type": "error", "error": str(exc)})
                return

        # LangGraph config — EventPublisher instead of WebSocket
        graph_config = {
            "configurable": {
                "thread_id": sid,
                "websocket": publisher,  # EventPublisher implements send_json
                "db": db,
                "task_id": session.task_id,
            },
            "recursion_limit": 20,
        }
        graph = graph_svc.get_graph()
        task_id = session.task_id

        # Restore interrupt state
        interrupted = await _restore_interrupt_state(
            graph, graph_config, publisher, sid, task_id
        )

        # Listen for commands
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
                    publisher, db, task_id, *result
                )

            elif cmd_type == "approve" and interrupted:
                await _try_update_task_status(db, task_id, "in_progress")
                await publish_event(sid, {"type": "status", "status": "thinking"})
                result = await _run_graph(graph, Command(resume=True), graph_config)
                interrupted = await _handle_graph_result(
                    publisher, db, task_id, *result
                )

            elif cmd_type == "reject" and interrupted:
                await _try_update_task_status(db, task_id, "in_progress")
                result = await _run_graph(graph, Command(resume=False), graph_config)
                interrupted = await _handle_graph_result(
                    publisher, db, task_id, *result
                )

            elif cmd_type == "message" and interrupted:
                await publish_event(sid, {
                    "type": "error",
                    "error": "Agent is waiting for approval. Send approve or reject first.",
                })


# ---------------------------------------------------------------------------
# Graph execution helpers (moved from ws.py, adapted for EventPublisher)
# ---------------------------------------------------------------------------

async def _restore_interrupt_state(
    graph, graph_config: dict, publisher: EventPublisher,
    session_id: str, task_id: uuid.UUID | None,
) -> bool:
    """Check LangGraph checkpoint for pending interrupts."""
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


async def _try_update_task_status(
    db, task_id: uuid.UUID | None, new_status: str,
) -> None:
    if not task_id:
        return
    try:
        await update_task_status(db, task_id, new_status)
    except Exception as exc:
        logger.error("Task %s status update to %s failed: %s", task_id, new_status, exc)


async def _handle_graph_result(
    publisher: EventPublisher,
    db,
    task_id: uuid.UUID | None,
    interrupted: bool,
    completed: bool,
    errored: bool,
    last_state: dict | None = None,
) -> bool:
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

    if completed:
        await _try_update_task_status(db, task_id, "done")

    await publisher.send_json({"type": "done"})
    return False


async def _run_graph(graph, input, config: dict) -> tuple[bool, bool, bool, dict | None]:
    """Stream graph — same logic as ws.py but uses EventPublisher."""
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
        logger.error("Graph execution error for session %s: %s", config["configurable"]["thread_id"], exc, exc_info=True)
        await publisher.send_json({"type": "error", "error": str(exc)})
        await _try_update_task_status(db, task_id, "error")
        await publish_notification("task_error", {
            "task_id": str(task_id) if task_id else "",
            "error": str(exc),
        })
        return False, False, True, None

    # Fallback: check for pending interrupts
    try:
        graph_state = await graph.aget_state(config)
        if graph_state and graph_state.next:
            return True, False, False, graph_state.values or {}
    except Exception as exc:
        logger.warning("Failed to check graph state after stream for %s: %s", config["configurable"]["thread_id"], exc)

    return False, completed, False, None


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

async def run_worker() -> None:
    """
    Main worker loop. Initializes Redis + LangGraph, then listens for
    session start commands on the 'worker:sessions' Redis channel.

    Each session is handled in its own asyncio task.
    """
    await init_redis()

    postgres_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
        await checkpointer.setup()
        graph_svc._compiled_graph = graph_svc.build_graph(checkpointer)

        from app.services.redis_service import get_redis
        r = get_redis()

        logger.info("Worker started, listening for session commands...")

        # Subscribe to worker control channel
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

                # NOTE: No "stop" action here — Worker only stops via
                # session commands channel (explicit user "stop" command).
                # WS disconnect does NOT stop the Worker.

        finally:
            await pubsub.unsubscribe("worker:sessions")
            await pubsub.aclose()
            # Cancel all active tasks
            for task in active_tasks.values():
                task.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks.values(), return_exceptions=True)

    await close_redis()


def main() -> None:
    """CLI entry point for running the worker process."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
