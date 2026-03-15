"""Tests for workspace_service — git worktree operations, diff, merge.

Uses real git repos in /tmp — no mocking of git.
"""
import asyncio
import os
import shutil
import tempfile
import pytest

from app.services.workspace_service import WorkspaceService, WorkspaceError, _ensure_gitignore


@pytest.fixture
def ws():
    """Fresh WorkspaceService instance per test."""
    return WorkspaceService()


@pytest.fixture
def git_repo(tmp_path):
    """Create a real git repo with initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    loop = asyncio.get_event_loop()

    async def _init():
        proc = await asyncio.create_subprocess_exec(
            "git", "init", "-b", "main", cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        for cmd in [
            ["git", "config", "user.email", "test@test.com"],
            ["git", "config", "user.name", "Test"],
        ]:
            p = await asyncio.create_subprocess_exec(*cmd, cwd=repo,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await p.communicate()

        # Initial commit
        with open(os.path.join(repo, "README.md"), "w") as f:
            f.write("# Test\n")
        p = await asyncio.create_subprocess_exec("git", "add", ".", cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p.communicate()
        p = await asyncio.create_subprocess_exec("git", "commit", "-m", "init", cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p.communicate()

    loop.run_until_complete(_init())
    yield repo
    shutil.rmtree(repo, ignore_errors=True)


class TestEnsureGitignore:
    def test_creates_gitignore(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        created = _ensure_gitignore(repo)
        assert created
        gi = os.path.join(repo, ".gitignore")
        assert os.path.isfile(gi)
        content = open(gi).read()
        assert ".env" in content
        assert "__pycache__" in content

    def test_does_not_overwrite(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        gi = os.path.join(repo, ".gitignore")
        with open(gi, "w") as f:
            f.write("custom\n")
        created = _ensure_gitignore(repo)
        assert not created
        assert open(gi).read() == "custom\n"


class TestEnsureRepoInitialized:
    async def test_inits_empty_dir(self, ws, tmp_path):
        repo = str(tmp_path / "empty")
        os.makedirs(repo)
        await ws.ensure_repo_initialized(repo)

        assert os.path.isdir(os.path.join(repo, ".git"))
        # Has at least one commit — use _run_git which handles errors
        head = await ws._run_git("rev-parse", "HEAD", cwd=repo, check=False)
        assert len(head) == 40  # SHA hash

    async def test_handles_orphan_head(self, ws, tmp_path):
        """Repo with .git but no commits (orphan HEAD)."""
        repo = str(tmp_path / "orphan")
        os.makedirs(repo)
        proc = await asyncio.create_subprocess_exec(
            "git", "init", "-b", "main", cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        # No commits — orphan HEAD
        await ws.ensure_repo_initialized(repo)

        head = await ws._run_git("rev-parse", "HEAD", cwd=repo, check=False)
        assert len(head) == 40

    async def test_idempotent(self, ws, git_repo):
        """Calling twice on valid repo doesn't break anything."""
        await ws.ensure_repo_initialized(git_repo)
        await ws.ensure_repo_initialized(git_repo)
        proc = await asyncio.create_subprocess_exec(
            "git", "log", "--oneline", cwd=git_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        # Should still have commits (not duplicated init)
        assert len(stdout.decode().strip().splitlines()) >= 1


class TestTaskWorktree:
    async def test_create_and_diff(self, ws, git_repo, tmp_path, monkeypatch):
        """Full cycle: create worktree → make changes → get diff."""
        # Override worktree base to tmp
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        task_id = "test-task-1234-5678-abcd-ef0123456789"
        info = await ws.create_task_worktree(git_repo, task_id)

        assert os.path.isdir(info.worktree_path)
        assert info.branch_name == "task/test-tas"
        assert info.repo_path == git_repo

        # Make a change in the worktree
        test_file = os.path.join(info.worktree_path, "new_feature.py")
        with open(test_file, "w") as f:
            f.write("def hello():\n    return 'world'\n")

        # Get diff — should see the new file
        diff = await ws.get_task_diff(task_id)
        assert len(diff) > 0
        assert "new_feature.py" in diff
        assert "+def hello():" in diff

        # Cleanup
        await ws.cleanup_task(task_id)
        assert not os.path.isdir(info.worktree_path)

    async def test_create_idempotent(self, ws, git_repo, tmp_path, monkeypatch):
        """Creating worktree twice returns same info."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        task_id = "idempotent-task-1234-5678"
        info1 = await ws.create_task_worktree(git_repo, task_id)
        info2 = await ws.create_task_worktree(git_repo, task_id)
        assert info1.worktree_path == info2.worktree_path

        await ws.cleanup_task(task_id)

    async def test_diff_empty_when_no_changes(self, ws, git_repo, tmp_path, monkeypatch):
        """Diff is empty when worktree has no changes vs base."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        task_id = "no-changes-task-1234-5678"
        await ws.create_task_worktree(git_repo, task_id)
        diff = await ws.get_task_diff(task_id)
        assert diff.strip() == ""

        await ws.cleanup_task(task_id)

    async def test_diff_with_committed_changes(self, ws, git_repo, tmp_path, monkeypatch):
        """Diff works even when agent already committed (no uncommitted files)."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        task_id = "committed-task-1234-5678"
        info = await ws.create_task_worktree(git_repo, task_id)

        # Write file and commit in worktree (simulating Claude CLI behavior)
        test_file = os.path.join(info.worktree_path, "agent_work.py")
        with open(test_file, "w") as f:
            f.write("# agent did this\nresult = 42\n")
        proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A", cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", "agent work", cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Now get diff — should still see the changes
        diff = await ws.get_task_diff(task_id)
        assert "agent_work.py" in diff
        assert "+result = 42" in diff

        await ws.cleanup_task(task_id)

    async def test_merge_task_branch(self, ws, git_repo, tmp_path, monkeypatch):
        """Merge task branch back to main."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        task_id = "merge-task-1234-5678"
        info = await ws.create_task_worktree(git_repo, task_id)

        # Make change
        with open(os.path.join(info.worktree_path, "merged.txt"), "w") as f:
            f.write("merged content\n")

        # Merge
        result = await ws.merge_task_branch(task_id)
        assert result is True

        # Verify file exists in main
        assert os.path.isfile(os.path.join(git_repo, "merged.txt"))

        await ws.cleanup_task(task_id)

    async def test_no_worktree_raises(self, ws):
        """get_task_diff with unknown task_id raises."""
        with pytest.raises(WorkspaceError, match="No task worktree"):
            await ws.get_task_diff("nonexistent-id")



    async def test_diff_with_detached_head_repo(self, ws, tmp_path, monkeypatch):
        """Diff works even when main repo has detached HEAD."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        # Create repo with only "main" branch
        repo = str(tmp_path / "detached_repo")
        os.makedirs(repo)
        await ws.ensure_repo_initialized(repo)

        task_id = "detached-head-task-1234"
        info = await ws.create_task_worktree(repo, task_id)

        # Detach HEAD in main repo (simulates what happens after worktree checkout)
        proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD", cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        head_sha = stdout.decode().strip()
        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", head_sha, cwd=repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Make change in worktree
        with open(os.path.join(info.worktree_path, "detached_test.py"), "w") as f:
            f.write("x = 1\n")

        diff = await ws.get_task_diff(task_id)
        assert "detached_test.py" in diff
        assert "+x = 1" in diff

        await ws.cleanup_task(task_id)

class TestSubAgentFork:
    async def test_fork_and_merge(self, ws, git_repo, tmp_path, monkeypatch):
        """Sub-agent fork: create, modify, merge back."""
        wt_base = str(tmp_path / "worktrees")
        monkeypatch.setattr("app.services.workspace_service.WORKTREE_BASE", wt_base)

        # Use UUID-like task_id to avoid branch name conflicts (task/xxxxxxxx vs task/xxxxxxxx/sub-...)
        task_id = "a1b2c3d4e5f6a7b8-fork-test"
        await ws.create_task_worktree(git_repo, task_id)

        sub_id = "z9y8x7w6v5u4-sub"
        fork_info = await ws.create_sub_agent_fork(task_id, sub_id)
        assert os.path.isdir(fork_info.worktree_path)

        # Sub-agent makes a change
        with open(os.path.join(fork_info.worktree_path, "sub_work.py"), "w") as f:
            f.write("sub = True\n")

        success, conflict = await ws.merge_sub_agent_fork(sub_id)
        assert success
        assert conflict is None or conflict == ""

        await ws.cleanup_sub_fork(sub_id)
        await ws.cleanup_task(task_id)
