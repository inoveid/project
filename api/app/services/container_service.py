"""
ContainerPoolService — manages Docker containers for agent isolation.

Each agent session gets its own Docker container with the git worktree
mounted at /workspace.  Containers are created from the `agent-sandbox`
image and automatically removed on stop.

Usage:
    pool = ContainerPoolService()
    info = await pool.acquire(agent_id, session_id, worktree_path, env={...})
    exit_code, output = await pool.exec_command(session_id, "python run.py")
    await pool.release(session_id)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridden by app.config.settings when available)
# ---------------------------------------------------------------------------
_DEFAULT_IMAGE = "agent-sandbox:latest"
_DEFAULT_MEMORY_MB = 512
_DEFAULT_CPU_LIMIT = 1.0


def _get_setting(name: str, default):
    """Read a setting from app.config if available, else use default."""
    try:
        from app.config import settings
        return getattr(settings, name, default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class ContainerInfo:
    """Tracks one running sandbox container."""

    container_id: str
    agent_id: str
    session_id: str
    worktree_path: str
    status: str = "running"
    created_at: datetime = field(default_factory=datetime.utcnow)


class ContainerError(Exception):
    """Raised when a container operation fails."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ContainerPoolService:
    """Singleton service that manages Docker sandbox containers.

    Uses the synchronous ``docker`` SDK wrapped in ``asyncio.to_thread``
    so it integrates cleanly with the async codebase without requiring
    ``aiodocker``.
    """

    _instance: Optional["ContainerPoolService"] = None

    def __new__(cls) -> "ContainerPoolService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._containers: dict[str, ContainerInfo] = {}
        self._client = None

    # -- helpers -------------------------------------------------------------

    def _docker_client(self):
        """Lazily create the Docker client (keeps import at runtime)."""
        if self._client is not None:
            return self._client
        try:
            import docker
            self._client = docker.from_env()
            self._client.ping()
            logger.info("Docker connection established")
            return self._client
        except ImportError:
            raise ContainerError(
                "Docker SDK not installed. Run: pip install docker"
            )
        except Exception as exc:
            raise ContainerError(
                f"Cannot connect to Docker daemon: {exc}"
            ) from exc

    # -- public API ----------------------------------------------------------

    async def acquire(
        self,
        agent_id: str,
        session_id: str,
        worktree_path: str,
        env: Optional[dict[str, str]] = None,
    ) -> ContainerInfo:
        """Create and start a sandbox container for the given session."""

        if session_id in self._containers:
            logger.warning("Container already exists for session %s", session_id)
            return self._containers[session_id]

        image = _get_setting("SANDBOX_IMAGE", _DEFAULT_IMAGE)
        memory_mb = _get_setting("SANDBOX_MEMORY_MB", _DEFAULT_MEMORY_MB)
        cpu_limit = _get_setting("SANDBOX_CPU_LIMIT", _DEFAULT_CPU_LIMIT)

        labels = {
            "managed-by": "agent-console",
            "agent-id": agent_id,
            "session-id": session_id,
        }

        environment = env or {}

        def _create():
            client = self._docker_client()
            container = client.containers.run(
                image=image,
                detach=True,
                auto_remove=True,
                working_dir="/workspace",
                volumes={
                    worktree_path: {"bind": "/workspace", "mode": "rw"},
                },
                environment=environment,
                labels=labels,
                mem_limit=f"{memory_mb}m",
                nano_cpus=int(cpu_limit * 1e9),
                network_mode="bridge",
            )
            return container

        try:
            container = await asyncio.to_thread(_create)
        except Exception as exc:
            raise ContainerError(
                f"Failed to start container for session {session_id}: {exc}"
            ) from exc

        info = ContainerInfo(
            container_id=container.id,
            agent_id=agent_id,
            session_id=session_id,
            worktree_path=worktree_path,
        )
        self._containers[session_id] = info
        logger.info(
            "Container %s started for agent=%s session=%s",
            container.short_id,
            agent_id,
            session_id,
        )
        return info

    async def release(self, session_id: str) -> None:
        """Stop and remove the container for the given session."""

        info = self._containers.pop(session_id, None)
        if info is None:
            logger.debug("No container to release for session %s", session_id)
            return

        def _stop():
            try:
                client = self._docker_client()
                container = client.containers.get(info.container_id)
                container.stop(timeout=5)
            except Exception as exc:
                # auto_remove may have already cleaned it up
                logger.debug("Container stop/remove notice: %s", exc)

        await asyncio.to_thread(_stop)
        logger.info(
            "Container %s released (session=%s)",
            info.container_id[:12],
            session_id,
        )

    async def exec_command(
        self, session_id: str, command: str
    ) -> tuple[int, str]:
        """Execute a command inside the container and return (exit_code, output)."""

        info = self._containers.get(session_id)
        if info is None:
            raise ContainerError(
                f"No active container for session {session_id}"
            )

        def _exec():
            client = self._docker_client()
            container = client.containers.get(info.container_id)
            result = container.exec_run(
                cmd=["bash", "-c", command],
                workdir="/workspace",
                demux=True,
            )
            stdout = result.output[0].decode() if result.output[0] else ""
            stderr = result.output[1].decode() if result.output[1] else ""
            output = stdout + stderr
            return result.exit_code, output

        try:
            return await asyncio.to_thread(_exec)
        except Exception as exc:
            raise ContainerError(
                f"exec_command failed in session {session_id}: {exc}"
            ) from exc

    async def release_all(self) -> None:
        """Stop and remove all managed containers (shutdown cleanup)."""

        session_ids = list(self._containers.keys())
        if not session_ids:
            return
        logger.info("Releasing %d container(s)...", len(session_ids))
        for sid in session_ids:
            try:
                await self.release(sid)
            except Exception as exc:
                logger.warning("Error releasing session %s: %s", sid, exc)

    def list_active(self) -> list[ContainerInfo]:
        """Return a list of currently tracked containers."""
        return list(self._containers.values())
