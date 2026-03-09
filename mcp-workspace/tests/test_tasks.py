"""Unit tests for mcp-workspace task tools."""

from unittest.mock import MagicMock, patch

import pytest

from tools.tasks import register_task_tools


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace structure with two TASK files."""
    tasks_dir = tmp_path / "process" / "tasks"
    tasks_dir.mkdir(parents=True)

    (tasks_dir / "TASK-001.md").write_text(
        '---\nid: TASK-001\ntitle: "First task"\nstatus: backlog\nassigned_to: developer\npriority: 1\n---\n\n# TASK-001\nBody here.'
    )
    (tasks_dir / "TASK-002.md").write_text(
        '---\nid: TASK-002\ntitle: "Second task"\nstatus: in-progress\nassigned_to: reviewer\npriority: 2\n---\n\n# TASK-002\nAnother body.'
    )

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    script = tools_dir / "task-status.sh"
    script.write_text("#!/bin/bash\necho 'Status updated'\n")
    script.chmod(0o755)

    return tmp_path


@pytest.fixture
def tools(workspace, mock_mcp):
    """Register task tools and return the tool dict."""
    register_task_tools(mock_mcp, str(workspace))
    return mock_mcp._tools


def test_list_tasks_returns_all(tools):
    """list_tasks returns all TASK-*.md files."""
    result = tools["list_tasks"]()
    assert "TASK-001" in result
    assert "TASK-002" in result
    assert "First task" in result
    assert "Second task" in result


def test_get_task_valid_id(tools):
    """get_task returns file content for a valid TASK-NNN id."""
    result = tools["get_task"]("TASK-001")
    assert "TASK-001" in result
    assert "First task" in result
    assert "Body here." in result


def test_get_task_invalid_id(tools):
    """get_task returns error message for invalid id format."""
    result = tools["get_task"]("INVALID")
    assert "Invalid task_id" in result


def test_get_task_nonexistent(tools):
    """get_task returns error for a well-formed but missing task."""
    result = tools["get_task"]("TASK-999")
    assert "not found" in result.lower()


def test_update_task_status_valid(tools):
    """update_task_status calls task-status.sh with [script, task_id, status]."""
    with patch("tools.tasks.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Status updated\n", stderr="")
        result = tools["update_task_status"]("TASK-001", "in-progress")

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[1] == "TASK-001"
    assert cmd[2] == "in-progress"
    assert "Status updated" in result
