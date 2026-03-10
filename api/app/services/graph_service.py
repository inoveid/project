"""
P5: Workflow-based handoff via MCP tools.

Replaces text-based handoff blocks with structured MCP tool calls.
Agent outgoing edges in a workflow become handoff tools. The agent calls
a tool to transition; the server checks requires_approval and max_cycles.

Graph:
    START → run_agent → [route] → notify_handoff → gate → run_agent (cycle)
                                → auto_handoff → run_agent (cycle)
                                → complete → END
                                → END
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
from app.services.handoff_server import (
    HandoffResult,
    format_handoff_tools_prompt,
    generate_handoff_tools,
    handle_handoff_tool_call,
    parse_handoff_from_text,
)
from app.services.runtime import runtime
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    create_session,
    get_session,
    stop_session,
)

logger = logging.getLogger(__name__)

MAX_DEPTH = 5


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    """
    Graph state persisted in PostgreSQL after each node.

    - main_session_id: WebSocket session (unchanged)
    - current_session_id: claude CLI session of current agent (changes on handoff)
    - workflow_id: workflow being executed (None for legacy sessions)
    - task_id: task being worked on (None for legacy sessions)
    - handoff_result: serialized HandoffResult from handle_handoff_tool_call
    """
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
    messages: list


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def run_agent_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Run the current agent via claude CLI and stream events to WebSocket.

    For depth==0 (main agent): runtime already started from ws.py.
    For depth>0 (sub-agent): runtime started in gate/auto_handoff node.
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

    # Sub-agent done — stop runtime, close DB session, notify UI
    if is_sub:
        await runtime.stop_session(session_id)
        await stop_session(db, session_id)
        await ws.send_json({"type": "handoff_done", "agent_name": state["current_agent_name"]})

    # Save result to DB
    if full_text or tool_uses:
        await add_message(db, session_id, "assistant", full_text, tool_uses=tool_uses or None)
        if is_sub:
            await add_message(
                db, uuid.UUID(state["main_session_id"]), "assistant",
                f"[{state['current_agent_name']}]: {full_text}",
            )

    # Save claude_session_id for resume (main agent only)
    if not is_sub:
        claude_sid = runtime.get_claude_session_id(session_id)
        if claude_sid:
            try:
                session = await get_session(db, session_id)
                session.claude_session_id = claude_sid
                await db.commit()
            except SessionNotFoundError:
                pass

    # Parse handoff tool call from agent response
    handoff_result = await _resolve_handoff(
        db, full_text, state.get("workflow_id"), state.get("task_id"),
        uuid.UUID(state["current_agent_id"]),
    )

    return {
        "messages": state["messages"] + [{
            "agent": state["current_agent_name"],
            "text": full_text,
            "tools": tool_uses,
        }],
        "handoff_result": _serialize_handoff_result(handoff_result),
        "gateway_approved": None,
    }


async def _resolve_handoff(
    db: AsyncSession,
    full_text: str,
    workflow_id: str | None,
    task_id: str | None,
    agent_id: uuid.UUID,
) -> HandoffResult | None:
    """Parse handoff from agent text and resolve via handoff_server."""
    if not workflow_id:
        return None

    parsed = parse_handoff_from_text(full_text)
    if not parsed:
        return None

    tool_name = parsed.get("tool", "")
    tool_args = {k: v for k, v in parsed.items() if k != "tool"}

    return await handle_handoff_tool_call(
        db,
        tool_name=tool_name,
        tool_args=tool_args,
        task_id=uuid.UUID(task_id) if task_id else None,
        workflow_id=uuid.UUID(workflow_id),
        agent_id=agent_id,
    )


def _serialize_handoff_result(result: HandoffResult | None) -> dict | None:
    """Convert HandoffResult to a JSON-serializable dict for state."""
    if result is None:
        return None
    return {
        "forwarded": result.forwarded,
        "awaiting_approval": result.awaiting_approval,
        "blocked": result.blocked,
        "completed": result.completed,
        "reason": result.reason,
        "to_agent_id": str(result.to_agent_id) if result.to_agent_id else None,
        "to_agent_name": result.to_agent_name,
        "prompt": result.prompt,
        "edge_id": str(result.edge_id) if result.edge_id else None,
        "requires_approval": result.requires_approval,
        "tool_args": result.tool_args,
    }


async def notify_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Notify WebSocket about pending handoff requiring approval.

    Runs ONCE before gate_node. On resume, gate_node reruns but not this node,
    so approval_required is sent exactly once.
    """
    ws: WebSocket = config["configurable"]["websocket"]
    hr = state["handoff_result"]
    await ws.send_json({
        "type": "approval_required",
        "from_agent": state["current_agent_name"],
        "to_agent": hr["to_agent_name"] if hr else "",
        "task": hr.get("prompt", "") if hr else "",
    })
    return {}


async def gate_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    HITL gate: pause until human decision.

    On approve: create sub-agent session and start runtime.
    On reject: cancel handoff.
    """
    db: AsyncSession = config["configurable"]["db"]
    ws: WebSocket = config["configurable"]["websocket"]

    approved: bool = interrupt("Waiting for human approval of handoff")

    if not approved:
        return {"gateway_approved": False, "handoff_result": None}

    hr = state["handoff_result"]
    if not hr or not hr.get("to_agent_id"):
        return {"gateway_approved": False, "handoff_result": None}

    return await _create_sub_session(db, ws, state, hr)


async def auto_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Automatic handoff: create sub-agent session without approval.

    Used when requires_approval=False on the workflow edge.
    """
    db: AsyncSession = config["configurable"]["db"]
    ws: WebSocket = config["configurable"]["websocket"]

    hr = state["handoff_result"]
    if not hr or not hr.get("to_agent_id"):
        return {"gateway_approved": False, "handoff_result": None}

    return await _create_sub_session(db, ws, state, hr)


async def complete_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handle task completion when agent calls complete_task tool."""
    ws: WebSocket = config["configurable"]["websocket"]
    hr = state["handoff_result"]
    summary = hr.get("tool_args", {}).get("summary", "") if hr else ""

    await ws.send_json({
        "type": "task_completed",
        "agent_name": state["current_agent_name"],
        "summary": summary,
    })

    return {"handoff_result": None, "gateway_approved": None}


async def blocked_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handle blocked handoff (max_cycles exceeded)."""
    ws: WebSocket = config["configurable"]["websocket"]
    hr = state["handoff_result"]
    reason = hr.get("reason", "unknown") if hr else "unknown"

    await ws.send_json({
        "type": "max_cycles_reached",
        "agent_name": hr.get("to_agent_name", "") if hr else "",
        "reason": reason,
    })

    return {"handoff_result": None, "gateway_approved": None}


async def _create_sub_session(
    db: AsyncSession, ws: WebSocket, state: WorkflowState, hr: dict
) -> dict:
    """Create a sub-agent session and start its runtime."""
    from app.models.agent import Agent

    target_id = uuid.UUID(hr["to_agent_id"])
    target = await db.get(Agent, target_id)
    if not target:
        logger.warning("Handoff target agent %s not found", target_id)
        return {"gateway_approved": False, "handoff_result": None}

    prompt = hr.get("prompt", "") or hr.get("tool_args", {}).get("comment", "")

    # Create sub-session with task_id linked
    task_id = uuid.UUID(state["task_id"]) if state.get("task_id") else None
    sub_session = await create_session(db, SessionCreate(agent_id=target.id))
    if task_id:
        sub_session.task_id = task_id
        await db.commit()
        await db.refresh(sub_session)
    await add_message(db, sub_session.id, "user", prompt)

    # Build system prompt for sub-agent
    system_prompt = target.system_prompt

    # Add handoff tools for the sub-agent if workflow context exists
    workflow_id = state.get("workflow_id")
    if workflow_id:
        sub_tools = await generate_handoff_tools(db, target.id, uuid.UUID(workflow_id))
        tools_prompt = format_handoff_tools_prompt(sub_tools)
        if tools_prompt:
            system_prompt += tools_prompt

    # Add chain context
    current_pair = [state["current_agent_name"], target.name]
    chain = state["chain"] + [current_pair]
    chain_str = " → ".join(f"{a}→{b}" for a, b in chain)
    system_prompt += f"\n\n## Handoff Chain Context\nChain so far: {chain_str} → {target.name} (you)"

    # Resolve workdir
    workdir = (target.config.get("workdir") or settings.workspace_path) if target.config else settings.workspace_path

    await runtime.start_session(
        sub_session.id, workdir, system_prompt,
        parent_session_id=uuid.UUID(state["main_session_id"]),
        allowed_tools=target.allowed_tools or [],
    )

    await ws.send_json({
        "type": "handoff_start",
        "from_agent": state["current_agent_name"],
        "to_agent": target.name,
        "task": prompt,
    })

    return {
        "gateway_approved": True,
        "current_session_id": str(sub_session.id),
        "current_agent_id": str(target.id),
        "current_agent_name": target.name,
        "task": prompt,
        "depth": state["depth"] + 1,
        "chain": chain,
        "handoff_result": None,
    }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_agent(
    state: WorkflowState,
) -> Literal["notify_handoff", "auto_handoff", "complete", "blocked", "__end__"]:
    """Route based on handoff_result from handle_handoff_tool_call."""
    hr = state.get("handoff_result")
    if not hr or state["depth"] >= MAX_DEPTH:
        return END

    if hr.get("completed"):
        return "complete"
    if hr.get("blocked"):
        return "blocked"
    if hr.get("awaiting_approval"):
        return "notify_handoff"
    if hr.get("forwarded"):
        return "auto_handoff"
    return END


def route_after_gate(state: WorkflowState) -> Literal["run_agent", "__end__"]:
    """If approved → run_agent (for sub-agent). Otherwise → END."""
    if state.get("gateway_approved"):
        return "run_agent"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer: AsyncPostgresSaver):
    """
    Graph:
        START → run_agent → route_after_agent:
          - notify_handoff → gate → route_after_gate → run_agent | END
          - auto_handoff → run_agent
          - complete → END
          - blocked → END
          - END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("run_agent", run_agent_node)
    graph.add_node("notify_handoff", notify_handoff_node)
    graph.add_node("gate", gate_node)
    graph.add_node("auto_handoff", auto_handoff_node)
    graph.add_node("complete", complete_node)
    graph.add_node("blocked", blocked_node)

    graph.add_edge(START, "run_agent")
    graph.add_conditional_edges("run_agent", route_after_agent)
    graph.add_edge("notify_handoff", "gate")
    graph.add_conditional_edges("gate", route_after_gate)
    graph.add_edge("auto_handoff", "run_agent")
    graph.add_edge("complete", END)
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
