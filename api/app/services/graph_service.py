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
from typing import Any, Literal, Protocol, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.event_bus import publish_notification
from app.schemas.session import SessionCreate
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
    create_session,
    get_session,
    stop_session,
)

logger = logging.getLogger(__name__)

class EventSender(Protocol):
    """Protocol for sending JSON events — works with both WebSocket and EventPublisher."""
    async def send_json(self, data: dict[str, Any]) -> None: ...


class GraphConfigurable(TypedDict):
    """Typed configurable dict passed to all graph nodes via RunnableConfig["configurable"].

    Assembled in worker.py (_run_session), consumed by graph nodes.
    All keys are required — missing keys will raise KeyError at runtime.
    """
    thread_id: str
    websocket: EventSender  # EventPublisher in Worker, WebSocket in tests
    db: AsyncSession
    task_id: uuid.UUID | None


MAX_DEPTH = 5  # Maximum nested handoff depth to prevent infinite recursion


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
    product_workspace: str | None
    messages: list


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _get_configurable(config: RunnableConfig) -> GraphConfigurable:
    """Extract typed configurable from RunnableConfig."""
    return config["configurable"]  # type: ignore[return-value]


async def run_agent_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Run the current agent via claude CLI and stream events to WebSocket.

    For depth==0 (main agent): runtime already started from ws.py.
    For depth>0 (sub-agent): runtime started in gate/auto_handoff node.
    """
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]
    db: AsyncSession = cfg["db"]
    is_sub = state["depth"] > 0 and state["current_session_id"] != state["main_session_id"]
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
            if is_sub:
                await ws.send_json({
                    **event,
                    "type": f"sub_agent_{ev_type}",
                    "agent_name": state["current_agent_name"],
                })
            else:
                await ws.send_json(event)
    except Exception as exc:
        agent_error = True
        logger.error("Agent %s error: %s", state["current_agent_name"], exc)
        if is_sub:
            await ws.send_json({
                "type": "sub_agent_error",
                "agent_name": state["current_agent_name"],
                "error": str(exc),
            })
        else:
            await ws.send_json({"type": "error", "error": str(exc)})

    # Sub-agent done — stop runtime but keep DB session active for reuse
    if is_sub:
        try:
            await runtime.stop_session(session_id)
        except Exception as cleanup_exc:
            logger.exception("Sub-agent runtime cleanup failed for %s: %s", session_id, cleanup_exc)
        finally:
            await ws.send_json({"type": "handoff_done", "agent_name": state["current_agent_name"]})

    # Early return on agent error — no handoff to process (P6)
    if agent_error:
        return {
            "messages": state["messages"],
            "handoff_result": None,
            "gateway_approved": None,
        }

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


async def _resolve_handoff(
    db: AsyncSession,
    full_text: str,
    workflow_id: str | None,
    task_id: str | None,
    agent_id: uuid.UUID,
    chain: list | None = None,
    agent_name: str = "",
) -> HandoffResult | None:
    """Parse handoff from agent text and resolve via handoff_server."""
    if not workflow_id:
        return None

    parsed = parse_handoff_from_text(full_text)
    if not parsed:
        return None

    tool_name = parsed.get("tool", "")
    tool_args = {k: v for k, v in parsed.items() if k != "tool"}

    # Pre-generate tools once and pass to avoid redundant DB query (P1)
    wf_id = uuid.UUID(workflow_id)
    tools = await generate_handoff_tools(db, agent_id, wf_id)

    return await handle_handoff_tool_call(
        db,
        tool_name=tool_name,
        tool_args=tool_args,
        task_id=uuid.UUID(task_id) if task_id else None,
        workflow_id=wf_id,
        agent_id=agent_id,
        tools=tools,
        chain=chain,
        agent_name=agent_name,
    )


def _serialize_handoff_result(result: HandoffResult | None) -> dict | None:
    """Convert HandoffResult to a JSON-serializable dict for state."""
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


async def notify_handoff_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """
    Broadcast approval_required notification (for dashboard toasts).

    Session WS event is sent separately from ws.py _handle_graph_result
    after the graph interrupts — this ensures reliable delivery.
    """
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
    """
    HITL gate: pause until human decision.

    On approve: create sub-agent session and start runtime.
    On reject: cancel handoff.
    """
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]
    db: AsyncSession = cfg["db"]

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
    cfg = _get_configurable(config)
    ws: EventSender = cfg["websocket"]
    db: AsyncSession = cfg["db"]

    hr = state["handoff_result"]
    if not hr or not hr.get("to_agent_id"):
        return {"gateway_approved": False, "handoff_result": None}

    return await _create_sub_session(db, ws, state, hr)


async def complete_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handle task completion when agent calls complete_task tool."""
    hr = state["handoff_result"]
    summary = hr.get("tool_args", {}).get("summary", "") if hr else ""

    event_data = {
        "agent_name": state["current_agent_name"],
        "summary": summary,
        "task_id": state.get("task_id", ""),
    }
    await publish_notification("task_completed", event_data)

    return {"handoff_result": None, "gateway_approved": None}


async def blocked_node(state: WorkflowState, config: RunnableConfig) -> dict:
    """Handle blocked handoff (max_cycles exceeded)."""
    hr = state["handoff_result"]
    reason = hr.get("reason", "unknown") if hr else "unknown"

    event_data = {
        "agent_name": hr.get("to_agent_name", "") if hr else "",
        "reason": reason,
        "task_id": state.get("task_id", ""),
    }
    await publish_notification("max_cycles_reached", event_data)

    return {"handoff_result": None, "gateway_approved": None}


# ---------------------------------------------------------------------------
# Sub-session creation (decomposed — P5)
# ---------------------------------------------------------------------------

async def _create_sub_session(
    db: AsyncSession, ws: EventSender, state: WorkflowState, hr: dict
) -> dict:
    """Create or reuse a session for the target agent."""
    from app.models.agent import Agent
    from app.models.session import Session as SessionModel
    from sqlalchemy import select

    target_id = uuid.UUID(hr["to_agent_id"])
    target = await db.get(Agent, target_id)
    if not target:
        logger.warning("Handoff target agent %s not found", target_id)
        return {"gateway_approved": False, "handoff_result": None}

    current_name = state["current_agent_name"]
    prompt = hr.get("prompt", "") or hr.get("tool_args", {}).get("comment", "")
    task_id = uuid.UUID(state["task_id"]) if state.get("task_id") else None
    main_session_id = uuid.UUID(state["main_session_id"])

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
        sub_session = existing_session
        logger.info("Reusing session %s for agent %s", sub_session.id, target.name)
    else:
        sub_session = await create_session(db, SessionCreate(agent_id=target.id))
        if task_id:
            sub_session.task_id = task_id
            await db.commit()
            await db.refresh(sub_session)

    await add_message(db, sub_session.id, "user", prompt)

    # Start runtime if not already running (reused sessions may have stopped runtime)
    if not runtime.is_running(sub_session.id):
        tools_prompt = await _generate_sub_tools(db, target.id, state.get("workflow_id"))
        system_prompt = _build_sub_agent_prompt(target, state, tools_prompt)
        workdir = _resolve_sub_agent_workdir(target, state)

        await runtime.start_session(
            sub_session.id, workdir, system_prompt,
            parent_session_id=main_session_id,
            allowed_tools=target.allowed_tools or [],
        )

    await ws.send_json({
        "type": "handoff_start",
        "from_agent": current_name,
        "to_agent": target.name,
        "task": prompt,
    })

    chain = state["chain"] + [[current_name, target.name]]
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


def _build_sub_agent_prompt(target, state: WorkflowState, tools_prompt: str) -> str:
    """Build system prompt for a sub-agent including handoff tools and chain context."""
    system_prompt = target.system_prompt

    if tools_prompt:
        system_prompt += tools_prompt

    current_pair = [state["current_agent_name"], target.name]
    chain = state["chain"] + [current_pair]
    chain_str = " → ".join(f"{a}→{b}" for a, b in chain)
    system_prompt += f"\n\n## Handoff Chain Context\nChain so far: {chain_str} → {target.name} (you)"

    return system_prompt


async def _generate_sub_tools(db: AsyncSession, agent_id, workflow_id: str | None) -> str:
    """Generate handoff tools prompt for a sub-agent."""
    if not workflow_id:
        return ""
    sub_tools = await generate_handoff_tools(db, agent_id, uuid.UUID(workflow_id))
    return format_handoff_tools_prompt(sub_tools)


def _resolve_sub_agent_workdir(target, state: WorkflowState) -> str:
    """Determine workdir for a sub-agent.
    
    Priority: product_workspace (from task) > agent.config.workdir > global workspace.
    All agents in a workflow share the product workspace for isolation.
    """
    # Product workspace propagates through the entire workflow
    product_ws = state.get("product_workspace")
    if product_ws:
        return product_ws
    if target.config:
        return target.config.get("workdir") or settings.workspace_path
    return settings.workspace_path





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
    """Return the compiled LangGraph workflow graph (module-level singleton).

    Initialized in BOTH main.py lifespan (API process) and worker.py run_worker()
    (Worker process). Both MUST use the same database URL for checkpoints,
    otherwise interrupt/resume state will be lost.
    """
    if _compiled_graph is None:
        raise RuntimeError("Workflow graph not initialized. Call setup_graph() in app lifespan.")
    return _compiled_graph
