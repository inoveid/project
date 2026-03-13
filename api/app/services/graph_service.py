"""
Workflow graph — runs a SINGLE agent, detects handoff intent, returns result.

Peer handoff (Developer ⟶ Reviewer) is handled by the Worker, not the graph.
The graph only: runs agent → detects handoff → returns state → END.

Sub-agents (depth > 0) will be added in Stage 2-3 within run_agent_node.

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
from app.services.session_service import (
    SessionNotFoundError,
    add_message,
    get_session,
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


MAX_DEPTH = 5  # Maximum nested handoff depth (for future sub-agents)


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
    """Run the current agent and stream events. Always depth=0 for peer agents."""
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]
    db: AsyncSession = cfg["db"]
    session_id = uuid.UUID(state["current_session_id"])

    full_text = ""
    tool_uses: list[dict] = []
    agent_error = False

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
            # All events go directly — no sub_agent_* prefixing
            await ws.send_json(event)
    except Exception as exc:
        agent_error = True
        logger.error("Agent %s error: %s", state["current_agent_name"], exc)
        await ws.send_json({"type": "error", "error": str(exc)})

    if agent_error:
        return {
            "messages": state["messages"],
            "handoff_result": None,
            "gateway_approved": None,
        }

    # Save result to DB
    if full_text or tool_uses:
        await add_message(db, session_id, "assistant", full_text, tool_uses=tool_uses or None)

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
        uuid.UUID(state["current_agent_id"]),
        chain=state.get("chain", []),
        agent_name=state["current_agent_name"],
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
    """HITL gate: pause until human decision. Returns approved flag, Worker handles the rest."""
    approved: bool = interrupt("Waiting for human approval of handoff")
    if not approved:
        return {"gateway_approved": False, "handoff_result": None}
    return {"gateway_approved": True}


async def auto_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Automatic handoff — no approval needed. Worker handles session creation."""
    return {"gateway_approved": True}


async def complete_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Task completed by agent."""
    hr = state["handoff_result"]
    summary = hr.get("tool_args", {}).get("summary", "") if hr else ""
    await publish_notification("task_completed", {
        "agent_name": state["current_agent_name"],
        "summary": summary,
        "task_id": state.get("task_id", ""),
    })
    return {"handoff_result": None, "gateway_approved": None}


async def blocked_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handoff blocked (max_cycles exceeded)."""
    hr = state["handoff_result"]
    reason = hr.get("reason", "unknown") if hr else "unknown"
    await publish_notification("max_cycles_reached", {
        "agent_name": hr.get("to_agent_name", "") if hr else "",
        "reason": reason,
        "task_id": state.get("task_id", ""),
    })
    return {"handoff_result": None, "gateway_approved": None}


# ---------------------------------------------------------------------------
# Routing — handoff always leads to END, Worker handles peer transitions
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


def route_after_gate(state: WorkflowState) -> Literal["__end__"]:
    """Gate always goes to END. Worker decides what to do based on gateway_approved."""
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer: AsyncPostgresSaver):
    """
    Graph (single-agent):
        START → run_agent → route:
          - notify_handoff → gate → END
          - auto_handoff → END
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
    # auto_handoff → END (no more looping back to run_agent)
    graph.add_edge("auto_handoff", END)
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
