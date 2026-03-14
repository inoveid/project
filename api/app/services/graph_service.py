"""
Workflow graph — runs a SINGLE agent, detects handoff/spawn intent, returns result.

Peer handoff (Developer → Reviewer) is handled by the Worker, not the graph.
Sub-agents (spawn_agent) are handled inline within run_agent_node:
  parent runs → spawn detected → sub-agents run → results fed back → parent continues.

Graph:
    START → run_agent → [route]:
        → notify_handoff → gate → END (with handoff_result + approved flag)
        → auto_handoff → END (with handoff_result)
        → complete → END
        → blocked → END
        → END (no handoff)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal, Protocol, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.event_bus import publish_notification
from app.services.handoff_server import (
    HandoffResult,
    HandoffResultType,
    format_handoff_tools_prompt,
    generate_handoff_tools,
    handle_handoff_tool_call,
    parse_handoff_from_text,
)
from app.services.runtime import runtime
from app.services.workspace_service import workspace_service
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
)
from app.services.sub_agent_service import (
    format_sub_agent_results,
    parse_spawn_requests,
    run_spawn_requests,
)

logger = logging.getLogger(__name__)


class EventSender(Protocol):
    """Protocol for sending JSON events — works with both WebSocket and EventPublisher."""
    async def send_json(self, data: dict[str, Any]) -> None: ...


class GraphConfigurable(TypedDict):
    """Typed configurable dict passed to all graph nodes via RunnableConfig."""
    thread_id: str
    websocket: EventSender
    db: AsyncSession
    task_id: uuid.UUID | None


MAX_DEPTH = 5
MAX_SPAWN_ROUNDS = 3  # Max spawn→result→continue cycles per run_agent_node


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    main_session_id: str
    current_session_id: str
    current_agent_id: str
    current_agent_name: str
    workflow_id: str | None
    task_id: str | None
    task: str
    depth: int
    chain: list
    handoff_result: dict | None
    gateway_approved: bool | None
    product_workspace: str | None
    messages: list
    task_worktree_path: str | None
    mr_diff: str | None
    mr_approved: bool | None
    auto_merge: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_configurable(config: RunnableConfig) -> GraphConfigurable:
    return config["configurable"]  # type: ignore[return-value]


def _serialize_handoff_result(result: HandoffResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "result_type": result.result_type.value,
        "reason": result.reason,
        "to_agent_id": str(result.to_agent_id) if result.to_agent_id else None,
        "to_agent_name": result.to_agent_name,
        "prompt": result.prompt,
        "edge_id": str(result.edge_id) if result.edge_id else None,
        "requires_approval": result.requires_approval,
        "tool_args": result.tool_args,
    }


async def _resolve_handoff(
    db: AsyncSession,
    full_text: str,
    workflow_id: str | None,
    task_id: str | None,
    agent_id: uuid.UUID,
    chain: list | None = None,
    agent_name: str = "",
) -> HandoffResult | None:
    if not workflow_id:
        return None
    parsed = parse_handoff_from_text(full_text)
    if not parsed:
        return None
    tool_name = parsed.get("tool", "")
    tool_args = {k: v for k, v in parsed.items() if k != "tool"}
    wf_id = uuid.UUID(workflow_id)
    tools = await generate_handoff_tools(db, agent_id, wf_id)
    return await handle_handoff_tool_call(
        db, tool_name=tool_name, tool_args=tool_args,
        task_id=uuid.UUID(task_id) if task_id else None,
        workflow_id=wf_id, agent_id=agent_id, tools=tools,
        chain=chain, agent_name=agent_name,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def run_agent_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Run the current agent and stream events.
    
    Handles sub-agent spawning: if agent outputs spawn_agent blocks,
    runs sub-agents, feeds results back, and continues the parent agent.
    This loop runs up to MAX_SPAWN_ROUNDS times.
    """
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]
    db: AsyncSession = cfg["db"]
    session_id = uuid.UUID(state["current_session_id"])
    agent_id = uuid.UUID(state["current_agent_id"])

    # Load agent for sub-agent templates
    from app.models.agent import Agent
    agent = await db.get(Agent, agent_id)
    sub_agent_templates = agent.sub_agent_templates if agent else []

    current_task = state["task"]
    all_tool_uses: list[dict] = []
    full_text = ""
    agent_error = False

    for spawn_round in range(MAX_SPAWN_ROUNDS + 1):
        round_text = ""
        round_tool_uses: list[dict] = []

        try:
            async for event in runtime.send_message(session_id, current_task):
                ev_type = event.get("type", "")
                if ev_type == "assistant_text":
                    round_text += event.get("content", "")
                elif ev_type == "tool_use":
                    round_tool_uses.append({
                        "tool_name": event.get("tool_name", ""),
                        "tool_input": event.get("tool_input", {}),
                    })
                await ws.send_json(event)
        except Exception as exc:
            agent_error = True
            logger.error("Agent %s error: %s", state["current_agent_name"], exc)
            await ws.send_json({"type": "error", "error": str(exc)})
            break

        full_text += round_text
        all_tool_uses.extend(round_tool_uses)

        # Check for spawn_agent / spawn_custom requests
        spawn_requests = parse_spawn_requests(round_text)

        if not spawn_requests or spawn_round >= MAX_SPAWN_ROUNDS:
            break  # No spawns or max rounds reached — exit loop

        # Run sub-agents in parallel with concurrency limit
        session = await get_session(db, session_id)
        workdir = state.get("task_worktree_path") or state.get("product_workspace") or settings.workspace_path
        max_concurrent = (agent.config or {}).get("max_sub_agents", 3) if agent else 3

        results = await run_spawn_requests(
            db=db,
            parent_session=session,
            requests=spawn_requests,
            sub_agent_templates=sub_agent_templates,
            workdir=workdir,
            parent_depth=state["depth"],
            ws_session_id=state["current_session_id"],
            max_concurrent=max_concurrent,
        )

        # Format results and feed back to parent as next message
        results_text = format_sub_agent_results(results)
        if results_text:
            current_task = results_text
            # Save sub-agent results as a "user" message for context
            await add_message(db, session_id, "user", results_text)
            # Continue loop — parent agent will process results

    if agent_error:
        return {
            "messages": state["messages"],
            "handoff_result": None,
            "gateway_approved": None,
        }

    # Save result to DB
    if full_text or all_tool_uses:
        await add_message(db, session_id, "assistant", full_text, tool_uses=all_tool_uses or None)

    # Save claude_session_id for resume
    claude_sid = runtime.get_claude_session_id(session_id)
    if claude_sid:
        try:
            session = await get_session(db, session_id)
            session.claude_session_id = claude_sid
            await db.commit()
        except SessionNotFoundError:
            pass

    # Parse handoff
    handoff_result = await _resolve_handoff(
        db, full_text, state.get("workflow_id"), state.get("task_id"),
        agent_id,
        chain=state.get("chain", []),
        agent_name=state["current_agent_name"],
    )

    return {
        "messages": state["messages"] + [{
            "agent": state["current_agent_name"],
            "text": full_text,
            "tools": all_tool_uses,
        }],
        "handoff_result": _serialize_handoff_result(handoff_result),
        "gateway_approved": None,
    }


async def notify_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Broadcast notification for dashboard toasts."""
    hr = state["handoff_result"]
    event_data = {
        "from_agent": state["current_agent_name"],
        "to_agent": hr["to_agent_name"] if hr else "",
        "task": hr.get("prompt", "") if hr else "",
        "task_id": state.get("task_id", ""),
    }
    await publish_notification("approval_required", event_data)
    return {}


async def gate_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """HITL gate: pause until human decision.
    
    Resume values:
    - True → approve handoff
    - {"refine": "comment"} → send comment back to current agent, re-run
    """
    decision = interrupt("Waiting for human approval of handoff")

    # Refine: user sends comment back to current agent
    if isinstance(decision, dict) and "refine" in decision:
        cfg = _get_configurable(config)
        db: AsyncSession = cfg["db"]
        session_id = uuid.UUID(state["current_session_id"])
        comment = decision["refine"]
        # Save user comment as message for context
        await add_message(db, session_id, "user", comment)
        return {
            "gateway_approved": None,
            "handoff_result": None,
            "task": comment,
        }

    # Reject (False) — should not happen in new flow, but keep as safety
    if not decision:
        return {"gateway_approved": False, "handoff_result": None}

    # Approve
    return {"gateway_approved": True}


async def auto_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Automatic handoff — no approval needed."""
    return {"gateway_approved": True}


async def complete_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Task completed by agent."""
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]

    # Check if task has a worktree — if so, generate MR diff
    task_id = state.get("task_id")
    if task_id and state.get("task_worktree_path"):
        try:
            diff = await workspace_service.get_task_diff(task_id)
            if diff.strip():
                # Publish MR event for frontend
                await ws.send_json({
                    "type": "mr_ready",
                    "task_id": task_id,
                    "diff_preview": diff[:2000],
                    "diff_lines": len(diff.splitlines()),
                })
                if state.get("auto_merge"):
                    # Auto-merge: skip MR gate
                    try:
                        await workspace_service.merge_task_branch(task_id)
                        await workspace_service.cleanup_task(task_id)
                        await ws.send_json({
                            "type": "mr_status",
                            "status": "merged",
                            "message": f"Merge Request автоматически принят. Изменения ({len(diff.splitlines())} строк) влиты в main.",
                            "task_id": task_id,
                        })
                    except Exception as merge_exc:
                        logger.warning("Auto-merge failed: %s", merge_exc)
                        await ws.send_json({
                            "type": "mr_status",
                            "status": "error",
                            "message": f"Ошибка auto-merge: {merge_exc}",
                            "task_id": task_id,
                        })
                    await publish_notification("task_completed", {
                        "agent_name": state["current_agent_name"],
                        "summary": "Auto-merged task branch",
                        "task_id": task_id,
                    })
                    return {"handoff_result": None, "gateway_approved": None}
                return {
                    "mr_diff": diff,
                    "mr_approved": None,  # waiting for approval
                }
        except Exception as exc:
            logger.warning("Failed to get task diff: %s", exc)

    hr = state["handoff_result"]
    summary = hr.get("tool_args", {}).get("summary", "") if hr else ""
    await publish_notification("task_completed", {
        "agent_name": state["current_agent_name"],
        "summary": summary,
        "task_id": state.get("task_id", ""),
    })
    return {"handoff_result": None, "gateway_approved": None}



async def mr_gate_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """HITL gate for MR approval. Pauses until user approves or rejects."""
    decision = interrupt({
        "type": "mr_approval",
        "task_id": state.get("task_id"),
        "diff_preview": (state.get("mr_diff") or "")[:2000],
    })

    approved = decision.get("approved", False)
    comment = decision.get("comment", "")

    if approved:
        # Merge task branch
        task_id = state.get("task_id")
        cfg2 = _get_configurable(config)
        ws2: EventSender = cfg2["websocket"]
        if task_id:
            try:
                await workspace_service.merge_task_branch(task_id)
                await workspace_service.cleanup_task(task_id)
                await ws2.send_json({
                    "type": "mr_status",
                    "status": "merged",
                    "message": "Merge Request одобрен. Изменения влиты в main.",
                    "task_id": task_id,
                })
            except Exception as exc:
                logger.error("MR merge failed: %s", exc)
                await ws2.send_json({
                    "type": "mr_status",
                    "status": "error",
                    "message": f"Ошибка при мерже: {exc}",
                    "task_id": task_id,
                })
        return {"mr_approved": True}
    else:
        # Rejected — return to first agent with comment
        return {
            "mr_approved": False,
            "task": f"MR отклонён. Комментарий: {comment}\n\nВнеси исправления.",
        }


async def blocked_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handoff blocked (max_cycles exceeded) — set task to error."""
    cfg = _get_configurable(config)
    db: AsyncSession = cfg["db"]
    hr = state["handoff_result"]
    reason = hr.get("reason", "unknown") if hr else "unknown"

    # Human-readable error message
    from_name = state.get("current_agent_name", "")
    to_name = hr.get("to_agent_name", "") if hr else ""
    max_r = ""
    if hr and "max_rounds" in hr.get("reason", ""):
        import re as _re
        m = _re.search(r"max_rounds \((\d+)\)", reason)
        max_r = m.group(1) if m else "3"
    readable = f"Агенты {from_name} и {to_name} обменялись {max_r or 3} раза без результата. Цикл остановлен."

    task_id = state.get("task_id")
    if task_id:
        from app.services.task_service import set_task_error
        await set_task_error(db, uuid.UUID(task_id), readable)

    await publish_notification("max_cycles_reached", {
        "agent_name": to_name,
        "reason": readable,
        "task_id": task_id or "",
    })
    return {"handoff_result": None, "gateway_approved": None}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_agent(
    state: WorkflowState,
) -> Literal["notify_handoff", "auto_handoff", "complete", "blocked", "__end__"]:
    hr = state.get("handoff_result")
    if not hr:
        return END
    rt = hr.get("result_type")
    if rt == HandoffResultType.COMPLETED:
        return "complete"
    if rt == HandoffResultType.BLOCKED:
        return "blocked"
    if rt == HandoffResultType.AWAITING_APPROVAL:
        return "notify_handoff"
    if rt == HandoffResultType.FORWARDED:
        return "auto_handoff"
    return END


def route_after_gate(state: WorkflowState) -> Literal["run_agent", "__end__"]:
    """After gate: approve → END (worker handles peer handoff), refine → run_agent again."""
    if state.get("gateway_approved") is None and state.get("handoff_result") is None:
        # Refine path — gate cleared handoff_result and set new task
        return "run_agent"
    return END



def route_after_complete(state: WorkflowState) -> str:
    if state.get("mr_diff") and state.get("mr_approved") is None:
        return "mr_gate"
    return END


def route_after_mr_gate(state: WorkflowState) -> str:
    if state.get("mr_approved"):
        return END
    return "run_agent"  # rejected, go back to first agent


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer: AsyncPostgresSaver):
    graph = StateGraph(WorkflowState)

    graph.add_node("run_agent", run_agent_node)
    graph.add_node("notify_handoff", notify_handoff_node)
    graph.add_node("gate", gate_node)
    graph.add_node("auto_handoff", auto_handoff_node)
    graph.add_node("complete", complete_node)
    graph.add_node("blocked", blocked_node)
    graph.add_node("mr_gate", mr_gate_node)

    graph.add_edge(START, "run_agent")
    graph.add_conditional_edges("run_agent", route_after_agent)
    graph.add_edge("notify_handoff", "gate")
    graph.add_conditional_edges("gate", route_after_gate)
    graph.add_edge("auto_handoff", END)
    graph.add_conditional_edges("complete", route_after_complete)
    graph.add_conditional_edges("mr_gate", route_after_mr_gate)
    graph.add_edge("blocked", END)

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_compiled_graph = None


def get_graph():
    if _compiled_graph is None:
        raise RuntimeError("Workflow graph not initialized. Call setup_graph() in app lifespan.")
    return _compiled_graph
