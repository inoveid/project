"""
AgentRuntime — manages Claude Agent SDK sessions.

Replaces the old subprocess-based runtime with the official Agent SDK.
Uses ClaudeSDKClient for multi-turn conversations with session continuity.

Key changes from subprocess approach:
- No more stdout JSON parsing — SDK provides typed Python objects
- No more process management — SDK handles CLI lifecycle
- Session resume via SDK's built-in session_id tracking
- OAuth token passed via env dict in ClaudeAgentOptions
"""
from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk.types import StreamEvent

from app.config import settings
from app.services.budget import BudgetTracker
from app.services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class AgentRuntimeError(Exception):
    pass


class TransientAgentError(Exception):
    """Transient error — can retry (rate limit, timeout, network)."""
    pass


@dataclass
class AgentSession:
    """Tracks state for one agent session."""
    session_id: uuid.UUID
    workdir: str
    system_prompt: str
    claude_session_id: Optional[str] = None
    allowed_tools: list[str] = field(default_factory=list)
    client: Optional[ClaudeSDKClient] = field(default=None, repr=False)


class AgentRuntime:
    """Manages Claude Agent SDK sessions for agents."""

    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, AgentSession] = {}
        self._children: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._budget = BudgetTracker(
            default_session_limit=settings.budget_session_limit_usd,
        )
        self._breaker = CircuitBreaker(
            failure_threshold=settings.cb_failure_threshold,
            recovery_timeout=settings.cb_recovery_timeout,
            failure_window=settings.cb_failure_window,
            name="claude_sdk",
        )

    async def start_session(
        self,
        session_id: uuid.UUID,
        workdir: str,
        system_prompt: str,
        claude_session_id: Optional[str] = None,
        allowed_tools: list[str] = None,
        parent_session_id: Optional[uuid.UUID] = None,
        max_tokens: int = 0,
    ) -> None:
        if session_id in self._sessions:
            raise AgentRuntimeError(f"Session {session_id} already running")

        effective_workdir = workdir or settings.workspace_path

        # Stop stale sessions using the same workdir
        stale = [
            sid for sid, s in self._sessions.items()
            if s.workdir == effective_workdir
        ]
        for sid in stale:
            logger.info("Stopping stale session %s (workdir reused by %s)", sid, session_id)
            await self.stop_session(sid)

        self._sessions[session_id] = AgentSession(
            session_id=session_id,
            workdir=effective_workdir,
            system_prompt=system_prompt,
            claude_session_id=claude_session_id,
            allowed_tools=allowed_tools or [],
        )
        if parent_session_id:
            self._children.setdefault(parent_session_id, set()).add(session_id)
        self._budget.start_session(str(session_id), max_tokens=max_tokens)

    async def send_message(
        self, session_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Send a message and yield events compatible with the existing event format."""
        agent_session = self._sessions.get(session_id)
        if not agent_session:
            raise AgentRuntimeError(f"Session {session_id} not running")

        from app.services.auth_service import get_current_access_token

        token = await get_current_access_token()
        if not token:
            raise AgentRuntimeError("Not authenticated. Please login first.")

        # Budget check
        self._budget.check_budget(str(session_id))

        # Circuit breaker
        self._breaker.check()

        # Build SDK options
        options = ClaudeAgentOptions(
            system_prompt=agent_session.system_prompt,
            allowed_tools=agent_session.allowed_tools,
            permission_mode="bypassPermissions",
            cwd=agent_session.workdir,
            env={"CLAUDE_CODE_OAUTH_TOKEN": token},
            include_partial_messages=True,
            max_budget_usd=self._budget.get_budget(str(session_id)).remaining_usd
            if self._budget.get_budget(str(session_id))
            else None,
        )

        # Resume existing session if we have a claude_session_id
        if agent_session.claude_session_id:
            options.resume = agent_session.claude_session_id

        # Disconnect previous client if any
        if agent_session.client:
            try:
                await agent_session.client.disconnect()
            except Exception:
                pass

        from app.services.telemetry import get_langfuse
        lf = get_langfuse()
        trace = lf.trace(
            name="agent.send_message",
            session_id=str(session_id),
            input=content,
        ) if lf else None
        generation = trace.generation(
            name="claude_sdk",
            input=content,
        ) if trace else None

        output_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        cost_usd = None
        call_succeeded = False

        try:
            client = ClaudeSDKClient(options=options)
            agent_session.client = client

            await client.connect()
            await client.query(content)

            async for message in client.receive_response():
                # AssistantMessage — contains text and tool use blocks
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            output_parts.append(block.text)
                            yield {"type": "assistant_text", "content": block.text}
                        elif hasattr(block, "name"):
                            # ToolUseBlock
                            yield {
                                "type": "tool_use",
                                "tool_name": block.name,
                                "tool_input": block.input,
                            }
                        elif hasattr(block, "tool_use_id"):
                            # ToolResultBlock
                            yield {
                                "type": "tool_result",
                                "content": str(block.content) if block.content else "",
                            }

                # StreamEvent — partial streaming updates
                elif isinstance(message, StreamEvent):
                    event = message.event or {}
                    ev_type = event.get("type", "")
                    # Forward content_block_delta for real-time text streaming
                    if ev_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield {"type": "assistant_text", "content": text}
                                output_parts.append(text)

                # ResultMessage — final message with usage/cost
                elif isinstance(message, ResultMessage):
                    agent_session.claude_session_id = message.session_id
                    cost_usd = message.total_cost_usd
                    usage = message.usage or {}
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    call_succeeded = True

                    # Record budget usage
                    budget_event = self._budget.record_usage(
                        session_id=str(session_id),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model=None,
                        reported_cost=cost_usd,
                    )
                    if budget_event:
                        yield budget_event

        except Exception as exc:
            error_msg = str(exc).lower()
            if any(w in error_msg for w in ["rate limit", "timeout", "connection"]):
                self._breaker.record_failure()
                raise TransientAgentError(str(exc)) from exc
            raise
        else:
            if call_succeeded:
                self._breaker.record_success()
        finally:
            output_text = "".join(output_parts)
            if generation:
                generation.end(
                    output=output_text,
                    usage={
                        "input": input_tokens,
                        "output": output_tokens,
                        "unit": "TOKENS",
                    },
                    metadata={"cost_usd": cost_usd},
                )
            if trace:
                trace.update(output=output_text)
            if lf:
                lf.flush()

    async def kill_active_process(self, session_id: uuid.UUID) -> None:
        """Interrupt the SDK client for this session."""
        agent_session = self._sessions.get(session_id)
        if agent_session and agent_session.client:
            try:
                await agent_session.client.interrupt()
            except Exception:
                pass

    def get_children(self, session_id: uuid.UUID) -> set[uuid.UUID]:
        return set(self._children.get(session_id, set()))

    async def stop_session(self, session_id: uuid.UUID) -> None:
        # Recursively stop children
        for child_id in self._children.pop(session_id, set()):
            await self.stop_session(child_id)

        agent_session = self._sessions.pop(session_id, None)
        if agent_session and agent_session.client:
            try:
                await agent_session.client.disconnect()
            except Exception:
                pass

        self._budget.remove_session(str(session_id))
        for parent_children in self._children.values():
            parent_children.discard(session_id)

    def is_running(self, session_id: uuid.UUID) -> bool:
        return session_id in self._sessions

    def get_claude_session_id(self, session_id: uuid.UUID) -> Optional[str]:
        agent_session = self._sessions.get(session_id)
        if agent_session:
            return agent_session.claude_session_id
        return None


runtime = AgentRuntime()
