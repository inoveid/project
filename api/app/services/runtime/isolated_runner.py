"""
IsolatedAgentRunner — wraps AgentRuntime with workspace isolation.

Adds git worktree and Docker container isolation on top of the existing
AgentRuntime.  Three isolation modes:

- NONE:      no isolation, agent runs in the original workdir (current behavior)
- WORKTREE:  agent runs in its own git worktree (parallel-safe, no container)
- CONTAINER: git worktree + Docker sandbox (full isolation)

The runner coordinates AgentRuntime, WorkspaceService, and ContainerPoolService
to provide a single entrypoint for isolated agent sessions.
"""
from __future__ import annotations

import enum
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.container_service import ContainerInfo, ContainerPoolService
from app.services.workspace_service import WorkspaceService, WorktreeInfo

from .agent_runner import AgentRuntime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Isolation mode
# ---------------------------------------------------------------------------

class IsolationMode(enum.Enum):
    """Level of workspace isolation for an agent session."""

    NONE = "none"           # inline — original workdir, no isolation
    WORKTREE = "worktree"   # git worktree only, no container
    CONTAINER = "container" # git worktree + Docker sandbox


# ---------------------------------------------------------------------------
# Session tracking
# ---------------------------------------------------------------------------

@dataclass
class IsolatedSessionInfo:
    """Tracks isolation state for one agent session."""

    session_id: str
    agent_id: str
    isolation_mode: IsolationMode
    repo_path: Optional[str] = None
    worktree_info: Optional[WorktreeInfo] = None
    container_info: Optional[ContainerInfo] = None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class IsolatedAgentRunner:
    """Wraps AgentRuntime with workspace isolation via worktrees / containers.

    This is a *wrapper*, not a replacement — every SDK call still goes
    through the underlying AgentRuntime.
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        workspace: WorkspaceService,
        container_pool: ContainerPoolService,
    ) -> None:
        self._runtime = runtime
        self._workspace = workspace
        self._container_pool = container_pool
        self._isolated_sessions: dict[str, IsolatedSessionInfo] = {}

    # -- public API ----------------------------------------------------------

    async def start_isolated_session(
        self,
        session_id: uuid.UUID,
        agent_id: str,
        repo_path: str,
        system_prompt: str,
        isolation_mode: IsolationMode = IsolationMode.NONE,
        *,
        claude_session_id: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        parent_session_id: Optional[uuid.UUID] = None,
        max_tokens: int = 0,
        container_env: Optional[dict[str, str]] = None,
    ) -> IsolatedSessionInfo:
        """Start a session with the requested isolation level.

        Args:
            session_id:      unique id for this session.
            agent_id:        agent definition id.
            repo_path:       path to the git repository (used as workdir for NONE).
            system_prompt:   system prompt forwarded to the runtime.
            isolation_mode:  NONE / WORKTREE / CONTAINER.
            claude_session_id: optional SDK session id for resume.
            allowed_tools:   tool allowlist forwarded to the runtime.
            parent_session_id: parent session for hierarchy tracking.
            max_tokens:      budget cap forwarded to the runtime.
            container_env:   extra env vars passed to the Docker container.

        Returns:
            IsolatedSessionInfo with worktree / container details.
        """
        sid = str(session_id)
        info = IsolatedSessionInfo(
            session_id=sid,
            agent_id=agent_id,
            isolation_mode=isolation_mode,
            repo_path=repo_path,
        )

        workdir = repo_path

        # -- WORKTREE / CONTAINER: create worktree ----------------------------
        if isolation_mode in (IsolationMode.WORKTREE, IsolationMode.CONTAINER):
            wt = await self._workspace.create_worktree(
                repo_path=repo_path,
                agent_id=agent_id,
                session_id=sid,
            )
            info.worktree_info = wt
            workdir = wt.worktree_path

        # -- CONTAINER: acquire sandbox container ----------------------------
        if isolation_mode is IsolationMode.CONTAINER:
            ct = await self._container_pool.acquire(
                agent_id=agent_id,
                session_id=sid,
                worktree_path=workdir,
                env=container_env,
            )
            info.container_info = ct
            # NOTE: for now the runtime still runs in the worker process
            # with cwd = worktree_path (mounted into the container).
            # Future: start the SDK *inside* the container.

        # -- delegate to AgentRuntime ----------------------------------------
        await self._runtime.start_session(
            session_id=session_id,
            workdir=workdir,
            system_prompt=system_prompt,
            claude_session_id=claude_session_id,
            allowed_tools=allowed_tools,
            parent_session_id=parent_session_id,
            max_tokens=max_tokens,
        )

        self._isolated_sessions[sid] = info
        logger.info(
            "Started isolated session %s (agent=%s, mode=%s, workdir=%s)",
            sid[:8], agent_id[:8], isolation_mode.value, workdir,
        )
        return info

    async def send_message(
        self, session_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Forward a message to the runtime — events go through Redis as usual."""
        return self._runtime.send_message(session_id, content)

    async def stop_isolated_session(self, session_id: uuid.UUID) -> None:
        """Stop the runtime session and commit worktree changes.

        Does NOT cleanup the worktree — call ``finalize_session`` when you
        are ready to merge / discard.
        """
        sid = str(session_id)

        # 1. Stop the runtime
        await self._runtime.stop_session(session_id)

        info = self._isolated_sessions.get(sid)
        if info is None:
            return

        # 2. Commit outstanding changes in the worktree
        if info.worktree_info is not None:
            try:
                await self._workspace.commit_changes(sid)
            except Exception as exc:
                logger.warning(
                    "Could not commit worktree changes for session %s: %s",
                    sid[:8], exc,
                )

        # 3. Release container (if CONTAINER mode)
        if info.container_info is not None:
            try:
                await self._container_pool.release(sid)
            except Exception as exc:
                logger.warning(
                    "Could not release container for session %s: %s",
                    sid[:8], exc,
                )

        logger.info("Stopped isolated session %s", sid[:8])

    async def finalize_session(
        self,
        session_id: uuid.UUID,
        merge_target: Optional[str] = None,
    ) -> bool:
        """Merge worktree results (if requested) and cleanup.

        Args:
            session_id:   session to finalize.
            merge_target: branch name to merge into (e.g. ``"main"``).
                          If ``None``, the worktree is cleaned up without merging.

        Returns:
            ``True`` if merge was performed and succeeded (or no merge requested),
            ``False`` if merge failed.
        """
        sid = str(session_id)
        info = self._isolated_sessions.pop(sid, None)
        if info is None:
            logger.debug("No isolated session to finalize: %s", sid[:8])
            return True

        merged = True

        if info.worktree_info is not None:
            # Merge if requested
            if merge_target:
                merged = await self._workspace.merge_into(
                    session_id=sid,
                    target_branch=merge_target,
                )
                if merged:
                    logger.info(
                        "Merged session %s into %s", sid[:8], merge_target,
                    )
                else:
                    logger.warning(
                        "Merge failed for session %s into %s",
                        sid[:8], merge_target,
                    )

            # Cleanup worktree
            await self._workspace.cleanup(sid)

        return merged

    def get_isolation_info(self, session_id: uuid.UUID) -> Optional[dict[str, Any]]:
        """Return isolation details for a session.

        Returns:
            dict with mode, worktree_path, container_id, branch_name
            or ``None`` if the session is not tracked.
        """
        sid = str(session_id)
        info = self._isolated_sessions.get(sid)
        if info is None:
            return None

        result: dict[str, Any] = {
            "session_id": info.session_id,
            "agent_id": info.agent_id,
            "mode": info.isolation_mode.value,
            "worktree_path": None,
            "branch_name": None,
            "container_id": None,
        }

        if info.worktree_info is not None:
            result["worktree_path"] = info.worktree_info.worktree_path
            result["branch_name"] = info.worktree_info.branch_name

        if info.container_info is not None:
            result["container_id"] = info.container_info.container_id

        return result

    def is_isolated(self, session_id: uuid.UUID) -> bool:
        """Check whether a session is tracked by this runner."""
        return str(session_id) in self._isolated_sessions

    def list_active(self) -> list[IsolatedSessionInfo]:
        """Return all currently tracked isolated sessions."""
        return list(self._isolated_sessions.values())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def _build_isolated_runner() -> IsolatedAgentRunner:
    from app.services.container_service import ContainerPoolService
    from app.services.workspace_service import workspace_service

    from .agent_runner import runtime

    return IsolatedAgentRunner(
        runtime=runtime,
        workspace=workspace_service,
        container_pool=ContainerPoolService(),
    )


isolated_runner = _build_isolated_runner()
