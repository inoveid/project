"""
WorkspaceService — manages git worktrees for task-level isolation.

One branch per task. All agents in the chain work in the same worktree.
Sub-agents get forks (child branches) from the task branch.

Flow:
1. create_task_worktree(repo_path, task_id) → one branch for the whole task
2. All agents in chain work in this directory (cwd = worktree path)
3. Sub-agents fork from task branch, merge back after completion
4. On task completion → MR (merge request) into target branch
5. cleanup(task_id) → removes worktree + branch
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_GITIGNORE = """# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
venv/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Env
.env
.env.local
"""


def _ensure_gitignore(repo_path: str) -> bool:
    """Create .gitignore if missing. Returns True if created."""
    gi_path = os.path.join(repo_path, ".gitignore")
    if os.path.exists(gi_path):
        return False
    with open(gi_path, "w") as f:
        f.write(DEFAULT_GITIGNORE)
    return True

WORKTREE_BASE = "/workspace/.agent-worktrees"


@dataclass
class WorktreeInfo:
    """Tracks a worktree (task-level or sub-agent fork)."""

    worktree_id: str  # task_id for main, sub_session_id for forks
    worktree_path: str
    branch_name: str
    repo_path: str
    parent_branch: Optional[str] = None  # set for sub-agent forks
    created_at: datetime = field(default_factory=datetime.utcnow)


class WorkspaceError(Exception):
    pass


class WorkspaceService:
    """Manages git worktrees: one per task, forks for sub-agents."""

    def __init__(self) -> None:
        self._task_worktrees: dict[str, WorktreeInfo] = {}  # task_id → info
        self._sub_worktrees: dict[str, WorktreeInfo] = {}   # sub_session_id → info

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
            await self._run_git("init", "-b", "main", cwd=repo_path)

        # Always ensure git config is set (may be missing if .git was created externally)
        current_email = await self._run_git(
            "config", "--get", "user.email", cwd=repo_path, check=False
        )
        if not current_email:
            await self._run_git(
                "config", "user.email", "agent@console.local", cwd=repo_path
            )
            await self._run_git(
                "config", "user.name", "Agent Console", cwd=repo_path
            )

        _ensure_gitignore(repo_path)

        # Ensure at least one commit (worktree requires it)
        has_commits = await self._run_git(
            "rev-parse", "HEAD", cwd=repo_path, check=False
        )
        if not has_commits or len(has_commits) != 40:
            logger.info("No commits in %s, creating initial commit", repo_path)
            gitkeep = os.path.join(repo_path, ".gitkeep")
            Path(gitkeep).touch()
            await self._run_git("add", ".", cwd=repo_path)
            await self._run_git(
                "commit", "-m", "initial commit", cwd=repo_path
            )
            logger.info("Initial commit created in %s", repo_path)

    # ── Task-level worktree ──────────────────────────────────────

    async def create_task_worktree(
        self,
        repo_path: str,
        task_id: str,
        agent_name: str = "Agent",
    ) -> WorktreeInfo:
        """Create a worktree for a task. One branch for the whole task.

        All agents in the chain share this worktree.
        Called once when the first writing agent starts.
        """
        # Return existing if already created for this task
        if task_id in self._task_worktrees:
            return self._task_worktrees[task_id]

        await self.ensure_repo_initialized(repo_path)

        short_id = task_id[:8]
        branch_name = f"task/{short_id}"
        worktree_dir = os.path.join(WORKTREE_BASE, f"task-{short_id}")

        # Check if worktree dir already exists with work (survives restart)
        if os.path.exists(worktree_dir) and os.path.exists(os.path.join(worktree_dir, ".git")):
            # Worktree dir survived restart — reuse it
            info = WorktreeInfo(
                worktree_id=task_id,
                worktree_path=worktree_dir,
                branch_name=branch_name,
                repo_path=repo_path,
            )
            self._task_worktrees[task_id] = info
            logger.info("Reusing existing worktree for task %s at %s", short_id, worktree_dir)
            return info

        # Check if branch exists with commits (worktree dir was lost but branch survived)
        branch_exists = False
        try:
            await self._run_git("rev-parse", "--verify", branch_name, cwd=repo_path)
            branch_exists = True
        except Exception:
            pass

        os.makedirs(WORKTREE_BASE, exist_ok=True)

        if branch_exists:
            # Prune stale worktree references, then recreate worktree from existing branch
            await self._run_git("worktree", "prune", cwd=repo_path, check=False)
            await self._run_git(
                "worktree", "add", worktree_dir, branch_name,
                cwd=repo_path,
            )
            logger.info("Restored worktree for task %s from existing branch", short_id)
        else:
            # Fresh start — create new branch from HEAD
            await self._run_git(
                "worktree", "add", "-b", branch_name, worktree_dir,
                cwd=repo_path,
            )

        # Configure git user in worktree (use agent name)
        await self._run_git(
            "config", "user.email", "agent@console.local", cwd=worktree_dir
        )
        await self._run_git(
            "config", "user.name", agent_name, cwd=worktree_dir
        )

        info = WorktreeInfo(
            worktree_id=task_id,
            worktree_path=worktree_dir,
            branch_name=branch_name,
            repo_path=repo_path,
        )
        self._task_worktrees[task_id] = info

        logger.info(
            "Created task worktree %s: %s (branch: %s)",
            short_id, worktree_dir, branch_name,
        )
        return info

    def get_task_worktree(self, task_id: str) -> Optional[WorktreeInfo]:
        """Get worktree for a task, if exists."""
        return self._task_worktrees.get(task_id)

    def get_task_worktree_path(self, task_id: str) -> Optional[str]:
        """Get worktree path for a task."""
        info = self._task_worktrees.get(task_id)
        return info.worktree_path if info else None

    # ── Sub-agent forks ──────────────────────────────────────────

    async def create_sub_agent_fork(
        self,
        task_id: str,
        sub_session_id: str,
    ) -> WorktreeInfo:
        """Create a fork (child worktree) from the task branch for a sub-agent.

        Sub-agent works in its own branch, then merges back into the task branch.
        """
        task_info = self._task_worktrees.get(task_id)
        if not task_info:
            raise WorkspaceError(f"No task worktree for task {task_id}")

        # Commit any uncommitted changes in task worktree first
        await self._commit_worktree(task_info)

        short_id = sub_session_id[:8]
        branch_name = f"sub/{task_id[:8]}-{short_id}"
        worktree_dir = os.path.join(WORKTREE_BASE, f"sub-{short_id}")

        # Clean up stale
        if os.path.exists(worktree_dir):
            await self._run_git(
                "worktree", "remove", worktree_dir, "--force",
                cwd=task_info.repo_path, check=False,
            )
            if os.path.exists(worktree_dir):
                shutil.rmtree(worktree_dir, ignore_errors=True)

        await self._run_git(
            "branch", "-D", branch_name, cwd=task_info.repo_path, check=False
        )

        # Create worktree branching from the task branch
        await self._run_git(
            "worktree", "add", "-b", branch_name, worktree_dir,
            task_info.branch_name,
            cwd=task_info.repo_path,
        )

        await self._run_git(
            "config", "user.email", "agent@console.local", cwd=worktree_dir
        )
        await self._run_git(
            "config", "user.name", "Agent Console", cwd=worktree_dir
        )

        info = WorktreeInfo(
            worktree_id=sub_session_id,
            worktree_path=worktree_dir,
            branch_name=branch_name,
            repo_path=task_info.repo_path,
            parent_branch=task_info.branch_name,
        )
        self._sub_worktrees[sub_session_id] = info

        logger.info(
            "Created sub-agent fork %s from %s (branch: %s)",
            short_id, task_info.branch_name, branch_name,
        )
        return info

    async def merge_sub_agent_fork(
        self,
        sub_session_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Merge a sub-agent's fork back into the task branch.

        Returns (success, conflict_diff_or_none).
        If conflict: returns (False, diff_text) for parent agent to resolve.
        """
        info = self._sub_worktrees.get(sub_session_id)
        if not info:
            raise WorkspaceError(f"No sub-agent fork for {sub_session_id}")

        # Commit sub-agent's changes
        await self._commit_worktree(info, message=f"[sub-agent:{sub_session_id[:8]}] work result")

        # Check if there are actual changes vs parent
        diff = await self._run_git(
            "diff", f"{info.parent_branch}...{info.branch_name}",
            cwd=info.repo_path, check=False,
        )
        if not diff.strip():
            logger.debug("Sub-agent %s made no changes", sub_session_id[:8])
            return True, None

        # Try merge into parent (task) branch worktree
        task_info = None
        for ti in self._task_worktrees.values():
            if ti.branch_name == info.parent_branch:
                task_info = ti
                break

        if not task_info:
            raise WorkspaceError(f"Parent branch {info.parent_branch} not found")

        try:
            await self._run_git(
                "merge", info.branch_name,
                "-m", f"Merge sub-agent {sub_session_id[:8]}",
                cwd=task_info.worktree_path,
            )
            logger.info("Merged sub-agent %s into %s", sub_session_id[:8], info.parent_branch)
            return True, None
        except WorkspaceError:
            # Get conflict diff for parent agent to resolve
            conflict_diff = await self._run_git(
                "diff", cwd=task_info.worktree_path, check=False,
            )
            await self._run_git(
                "merge", "--abort", cwd=task_info.worktree_path, check=False,
            )
            logger.warning("Conflict merging sub-agent %s", sub_session_id[:8])
            return False, conflict_diff

    def get_sub_worktree_path(self, sub_session_id: str) -> Optional[str]:
        """Get worktree path for a sub-agent fork."""
        info = self._sub_worktrees.get(sub_session_id)
        return info.worktree_path if info else None

    # ── Task completion (MR) ─────────────────────────────────────

    async def get_task_diff(self, task_id: str) -> str:
        """Get full diff of task branch vs base (for MR review)."""
        info = self._task_worktrees.get(task_id)
        if not info:
            raise WorkspaceError(f"No task worktree for {task_id}")

        await self._commit_worktree(info)

        # Get current base branch
        base = await self._run_git(
            "rev-parse", "--abbrev-ref", "HEAD",
            cwd=info.repo_path, check=False,
        )
        if not base or base == info.branch_name or base == "HEAD":
            base = "main"

        # Debug: check branch exists and has commits
        branch_log = await self._run_git(
            "log", "--oneline", "-5", info.branch_name,
            cwd=info.repo_path, check=False,
        )
        base_log = await self._run_git(
            "log", "--oneline", "-5", base,
            cwd=info.repo_path, check=False,
        )
        logger.info(
            "get_task_diff: base=%s, branch=%s, repo=%s, branch_log: %s, base_log: %s",
            base, info.branch_name, info.repo_path,
            branch_log[:200] if branch_log else "(empty)",
            base_log[:200] if base_log else "(empty)",
        )

        diff = await self._run_git(
            "diff", f"{base}...{info.branch_name}",
            cwd=info.repo_path, check=False,
        )
        logger.info("get_task_diff: three-dot diff length=%d", len(diff))

        if not diff.strip():
            # Fallback: try two-dot diff
            diff = await self._run_git(
                "diff", f"{base}..{info.branch_name}",
                cwd=info.repo_path, check=False,
            )
            logger.info("get_task_diff: two-dot diff length=%d", len(diff))

        if not diff.strip():
            # Last resort: diff worktree against base
            diff = await self._run_git(
                "diff", base,
                cwd=info.worktree_path, check=False,
            )
            logger.info("get_task_diff: worktree diff length=%d", len(diff))

        return diff

    async def merge_task_branch(
        self,
        task_id: str,
        target_branch: str | None = None,
    ) -> bool:
        """Merge task branch into target (final MR merge).

        Called after approval.
        """
        info = self._task_worktrees.get(task_id)
        if not info:
            raise WorkspaceError(f"No task worktree for {task_id}")

        await self._commit_worktree(info)

        # Detect default branch if not specified
        if not target_branch:
            target_branch = await self._get_default_branch(info.repo_path)

        # Switch to target branch in main repo
        await self._run_git("checkout", target_branch, cwd=info.repo_path)

        try:
            await self._run_git(
                "merge", info.branch_name,
                "-m", f"Merge task {task_id[:8]} into {target_branch}",
                cwd=info.repo_path,
            )
            logger.info("Merged task %s into %s", task_id[:8], target_branch)
            return True
        except WorkspaceError as e:
            logger.error("Task merge failed for %s: %s", task_id[:8], e)
            await self._run_git(
                "merge", "--abort", cwd=info.repo_path, check=False,
            )
            return False

    # ── Cleanup ──────────────────────────────────────────────────

    async def cleanup_sub_fork(self, sub_session_id: str) -> None:
        """Remove a sub-agent's fork worktree and branch."""
        info = self._sub_worktrees.pop(sub_session_id, None)
        if not info:
            return
        await self._cleanup_worktree(info)

    async def cleanup_task(self, task_id: str, delete_branch: bool = True) -> None:
        """Remove task worktree and optionally its branch."""
        # Clean up any remaining sub-agent forks
        sub_ids = [
            sid for sid, si in self._sub_worktrees.items()
            if si.parent_branch and task_id[:8] in si.parent_branch
        ]
        for sid in sub_ids:
            await self.cleanup_sub_fork(sid)

        info = self._task_worktrees.pop(task_id, None)
        if not info:
            return
        await self._cleanup_worktree(info, delete_branch=delete_branch)

    async def cleanup_all(self) -> None:
        """Remove all managed worktrees (shutdown cleanup)."""
        for sid in list(self._sub_worktrees.keys()):
            await self.cleanup_sub_fork(sid)
        for tid in list(self._task_worktrees.keys()):
            await self.cleanup_task(tid)

    def list_active_tasks(self) -> list[WorktreeInfo]:
        """List all active task worktrees."""
        return list(self._task_worktrees.values())

    def list_active_forks(self) -> list[WorktreeInfo]:
        """List all active sub-agent forks."""
        return list(self._sub_worktrees.values())

    # ── Internal helpers ─────────────────────────────────────────

    async def _get_default_branch(self, repo_path: str) -> str:
        """Detect the default branch (main or master)."""
        try:
            # Try symbolic-ref first (works if HEAD points to a branch)
            ref = await self._run_git(
                "symbolic-ref", "--short", "HEAD", cwd=repo_path, check=False
            )
            if ref and ref.strip():
                return ref.strip()
        except Exception:
            pass
        # Fallback: check if main exists, otherwise master
        branches = await self._run_git(
            "branch", "--format=%(refname:short)", cwd=repo_path, check=False
        )
        branch_list = [b.strip() for b in (branches or "").splitlines() if b.strip()]
        if "main" in branch_list:
            return "main"
        if "master" in branch_list:
            return "master"
        return branch_list[0] if branch_list else "main"

    async def _commit_worktree(
        self, info: WorktreeInfo, message: Optional[str] = None
    ) -> Optional[str]:
        """Commit all changes in a worktree. Returns hash or None."""
        status = await self._run_git("status", "--porcelain", cwd=info.worktree_path)
        logger.info("_commit_worktree %s: status=%r", info.branch_name, status[:200] if status else "(clean)")
        if not status.strip():
            # Log current HEAD even if nothing to commit
            head = await self._run_git("rev-parse", "--short", "HEAD", cwd=info.worktree_path, check=False)
            logger.info("_commit_worktree %s: nothing to commit, HEAD=%s", info.branch_name, head)
            return None

        await self._run_git("add", "-A", cwd=info.worktree_path)
        msg = message or f"[auto-save] uncommitted changes in {info.branch_name}"
        await self._run_git("commit", "-m", msg, cwd=info.worktree_path)

        commit_hash = await self._run_git("rev-parse", "HEAD", cwd=info.worktree_path)
        logger.info("Committed in %s: %s", info.branch_name, commit_hash[:8])
        return commit_hash

    async def _cleanup_worktree(
        self, info: WorktreeInfo, delete_branch: bool = True
    ) -> None:
        """Remove a worktree directory and optionally its branch."""
        try:
            await self._run_git(
                "worktree", "remove", info.worktree_path, "--force",
                cwd=info.repo_path, check=False,
            )
        except Exception:
            pass

        if os.path.exists(info.worktree_path):
            shutil.rmtree(info.worktree_path, ignore_errors=True)

        if delete_branch:
            await self._run_git(
                "branch", "-D", info.branch_name,
                cwd=info.repo_path, check=False,
            )

        logger.info(
            "Cleaned up worktree %s (branch: %s, deleted: %s)",
            info.worktree_id[:8], info.branch_name, delete_branch,
        )


# Singleton
workspace_service = WorkspaceService()
