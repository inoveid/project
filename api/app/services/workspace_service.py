"""
WorkspaceService — manages git worktrees for agent isolation.

Each agent in a workflow chain gets its own git worktree (branch + directory),
so agents can edit files in parallel without conflicts.

Flow:
1. create_worktree(repo_path, agent_id) → creates branch + worktree dir
2. Agent works in its own directory (cwd = worktree path)
3. commit_changes(worktree_path) → commits agent's work
4. merge_into(worktree_path, target_branch) → merges results back
5. cleanup(worktree_path) → removes worktree + optionally the branch
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKTREE_BASE = "/tmp/agent-worktrees"


@dataclass
class WorktreeInfo:
    """Tracks one agent's worktree."""

    agent_id: str
    session_id: str
    worktree_path: str
    branch_name: str
    repo_path: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class WorkspaceError(Exception):
    pass


class WorkspaceService:
    """Manages git worktrees for isolated agent execution."""

    def __init__(self) -> None:
        self._worktrees: dict[str, WorktreeInfo] = {}

    async def _run_git(
        self, *args: str, cwd: str, check: bool = True
    ) -> str:
        cmd = ["git"] + list(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if check and proc.returncode != 0:
            raise WorkspaceError(
                f"git {' '.join(args)} failed (rc={proc.returncode}): "
                f"{stderr.decode().strip()}"
            )
        return stdout.decode().strip()

    async def ensure_repo_initialized(self, repo_path: str) -> None:
        """Make sure repo_path is a valid git repo with at least one commit."""
        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir):
            await self._run_git("init", cwd=repo_path)
            await self._run_git(
                "config", "user.email", "agent@console.local", cwd=repo_path
            )
            await self._run_git(
                "config", "user.name", "Agent Console", cwd=repo_path
            )

        # Ensure at least one commit (worktree requires it)
        has_commits = await self._run_git(
            "rev-parse", "HEAD", cwd=repo_path, check=False
        )
        if not has_commits:
            # Create initial commit
            gitkeep = os.path.join(repo_path, ".gitkeep")
            Path(gitkeep).touch()
            await self._run_git("add", ".gitkeep", cwd=repo_path)
            await self._run_git(
                "commit", "-m", "initial commit", "--allow-empty", cwd=repo_path
            )

    async def create_worktree(
        self,
        repo_path: str,
        agent_id: str,
        session_id: str,
        branch_prefix: str = "agent",
    ) -> WorktreeInfo:
        """Create an isolated git worktree for an agent.

        Args:
            repo_path: Path to the main git repository.
            agent_id: UUID of the agent.
            session_id: UUID of the session (for uniqueness).
            branch_prefix: Prefix for branch name.

        Returns:
            WorktreeInfo with path and branch details.
        """
        await self.ensure_repo_initialized(repo_path)

        short_id = str(session_id)[:8]
        branch_name = f"{branch_prefix}/{agent_id[:8]}-{short_id}"
        worktree_dir = os.path.join(
            WORKTREE_BASE, f"{agent_id[:8]}-{short_id}"
        )

        # Clean up stale worktree at same path
        if os.path.exists(worktree_dir):
            await self._run_git(
                "worktree", "remove", worktree_dir, "--force",
                cwd=repo_path, check=False,
            )
            if os.path.exists(worktree_dir):
                shutil.rmtree(worktree_dir, ignore_errors=True)

        # Remove stale branch if exists
        await self._run_git(
            "branch", "-D", branch_name, cwd=repo_path, check=False
        )

        # Create worktree with new branch from current HEAD
        os.makedirs(WORKTREE_BASE, exist_ok=True)
        await self._run_git(
            "worktree", "add", "-b", branch_name, worktree_dir,
            cwd=repo_path,
        )

        # Configure git user in worktree
        await self._run_git(
            "config", "user.email", "agent@console.local", cwd=worktree_dir
        )
        await self._run_git(
            "config", "user.name", "Agent Console", cwd=worktree_dir
        )

        info = WorktreeInfo(
            agent_id=agent_id,
            session_id=session_id,
            worktree_path=worktree_dir,
            branch_name=branch_name,
            repo_path=repo_path,
        )
        self._worktrees[session_id] = info

        logger.info(
            "Created worktree for agent %s: %s (branch: %s)",
            agent_id[:8], worktree_dir, branch_name,
        )
        return info

    async def commit_changes(
        self,
        session_id: str,
        message: Optional[str] = None,
    ) -> Optional[str]:
        """Commit all changes in an agent's worktree.

        Returns commit hash or None if nothing to commit.
        """
        info = self._worktrees.get(session_id)
        if not info:
            raise WorkspaceError(f"No worktree for session {session_id}")

        # Check for changes
        status = await self._run_git("status", "--porcelain", cwd=info.worktree_path)
        if not status.strip():
            logger.debug("No changes to commit for session %s", session_id[:8])
            return None

        await self._run_git("add", "-A", cwd=info.worktree_path)

        commit_msg = message or f"[agent:{info.agent_id[:8]}] work result"
        await self._run_git("commit", "-m", commit_msg, cwd=info.worktree_path)

        commit_hash = await self._run_git(
            "rev-parse", "HEAD", cwd=info.worktree_path
        )
        logger.info(
            "Committed changes for session %s: %s",
            session_id[:8], commit_hash[:8],
        )
        return commit_hash

    async def get_diff(self, session_id: str, base_branch: str = "main") -> str:
        """Get diff of agent's changes vs base branch."""
        info = self._worktrees.get(session_id)
        if not info:
            raise WorkspaceError(f"No worktree for session {session_id}")

        # First commit any uncommitted changes
        await self.commit_changes(session_id)

        # Get diff against the base
        diff = await self._run_git(
            "diff", f"{base_branch}...{info.branch_name}",
            cwd=info.repo_path, check=False,
        )
        return diff

    async def merge_into(
        self,
        session_id: str,
        target_branch: str = "main",
        strategy: str = "theirs",
    ) -> bool:
        """Merge agent's worktree branch into target branch.

        Args:
            session_id: Session whose worktree to merge.
            target_branch: Branch to merge into.
            strategy: Merge strategy for conflicts ('theirs' = agent wins).

        Returns:
            True if merge succeeded.
        """
        info = self._worktrees.get(session_id)
        if not info:
            raise WorkspaceError(f"No worktree for session {session_id}")

        # Commit any remaining changes
        await self.commit_changes(session_id)

        # Switch to target branch in main repo
        await self._run_git("checkout", target_branch, cwd=info.repo_path)

        # Merge agent's branch
        try:
            await self._run_git(
                "merge", info.branch_name,
                "-m", f"Merge {info.branch_name} into {target_branch}",
                f"--strategy-option={strategy}",
                cwd=info.repo_path,
            )
            logger.info(
                "Merged %s into %s for session %s",
                info.branch_name, target_branch, session_id[:8],
            )
            return True
        except WorkspaceError as e:
            logger.error("Merge failed for session %s: %s", session_id[:8], e)
            # Abort merge on failure
            await self._run_git(
                "merge", "--abort", cwd=info.repo_path, check=False
            )
            return False

    async def cleanup(self, session_id: str, delete_branch: bool = True) -> None:
        """Remove worktree and optionally its branch."""
        info = self._worktrees.pop(session_id, None)
        if not info:
            return

        # Remove worktree
        try:
            await self._run_git(
                "worktree", "remove", info.worktree_path, "--force",
                cwd=info.repo_path, check=False,
            )
        except Exception:
            pass

        # Fallback: remove directory directly
        if os.path.exists(info.worktree_path):
            shutil.rmtree(info.worktree_path, ignore_errors=True)

        # Delete branch
        if delete_branch:
            await self._run_git(
                "branch", "-D", info.branch_name,
                cwd=info.repo_path, check=False,
            )

        logger.info(
            "Cleaned up worktree for session %s (branch: %s, deleted: %s)",
            session_id[:8], info.branch_name, delete_branch,
        )

    async def cleanup_all(self) -> None:
        """Remove all managed worktrees (shutdown cleanup)."""
        sessions = list(self._worktrees.keys())
        for sid in sessions:
            await self.cleanup(sid)

    def get_worktree_path(self, session_id: str) -> Optional[str]:
        """Get worktree path for a session, if exists."""
        info = self._worktrees.get(session_id)
        return info.worktree_path if info else None

    def get_info(self, session_id: str) -> Optional[WorktreeInfo]:
        """Get full worktree info for a session."""
        return self._worktrees.get(session_id)

    def list_active(self) -> list[WorktreeInfo]:
        """List all active worktrees."""
        return list(self._worktrees.values())


# Singleton
workspace_service = WorkspaceService()
