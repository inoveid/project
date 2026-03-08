"""Task management tools for MCP server.

Reads task files from {workspace}/process/tasks/TASK-NNN.md,
parses YAML frontmatter, and exposes list/get/update operations.
"""

import os
import re
import subprocess




def _tasks_dir(workspace_root: str) -> str:
    return os.path.join(workspace_root, "process", "tasks")


def _tools_dir(workspace_root: str) -> str:
    return os.path.join(workspace_root, "tools")


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter fields from task markdown."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


def _read_task_file(filepath: str) -> tuple[dict[str, str], str]:
    """Read task file, return (frontmatter_dict, full_content)."""
    with open(filepath) as f:
        content = f.read()
    return _parse_frontmatter(content), content


def register_task_tools(mcp, workspace_root: str) -> None:
    """Register all task-related tools on the MCP server."""

    @mcp.tool()
    def list_tasks(status: str | None = None) -> str:
        """List all tasks in the workspace.

        Returns task ID, title, status, priority, and assignee for each task.
        Optionally filter by status.

        Args:
            status: Filter by status (pending, in-progress, done, qa-pass, qa-fail).
                    Leave empty to list all tasks.
        """
        tasks_path = _tasks_dir(workspace_root)
        if not os.path.isdir(tasks_path):
            return f"Tasks directory not found: {tasks_path}"

        files = sorted(f for f in os.listdir(tasks_path) if f.startswith("TASK-") and f.endswith(".md"))
        if not files:
            return "No tasks found."

        rows: list[str] = []
        for filename in files:
            meta, _ = _read_task_file(os.path.join(tasks_path, filename))
            task_status = meta.get("status", "unknown")
            if status and task_status != status:
                continue
            rows.append(
                f"| {meta.get('id', '?')} "
                f"| {meta.get('title', '?')} "
                f"| {task_status} "
                f"| {meta.get('priority', '-')} "
                f"| {meta.get('assigned_to', '-')} |"
            )

        if not rows:
            return f"No tasks with status '{status}'."

        header = "| ID | Title | Status | Priority | Assignee |\n|---|---|---|---|---|"
        filter_note = f" (filtered: status={status})" if status else ""
        return f"## Tasks{filter_note}\n\n{header}\n" + "\n".join(rows) + f"\n\nTotal: {len(rows)}"

    @mcp.tool()
    def get_task(task_id: str) -> str:
        """Get the full content of a specific task.

        Returns the complete task markdown including description,
        acceptance criteria, dependencies, and files to read.

        Args:
            task_id: Task identifier, e.g. "TASK-001".
        """
        if not re.match(r"^TASK-\d{3}$", task_id):
            return f"Invalid task_id format: {task_id}. Expected TASK-NNN (e.g. TASK-001)."

        filepath = os.path.join(_tasks_dir(workspace_root), f"{task_id}.md")
        if not os.path.isfile(filepath):
            return f"Task not found: {task_id}"

        with open(filepath) as f:
            return f.read()

    @mcp.tool(annotations={"destructiveHint": True, "idempotentHint": False})
    def update_task_status(task_id: str, new_status: str) -> str:
        """Change the status of a task.

        This triggers validation and git operations:
        - "in-progress": creates git branch task/TASK-NNN
        - "done": runs build + tests + lint + quality checks, then commits
        - "qa-pass": merges task branch into main
        - "qa-fail": marks for rework

        Valid transitions:
          pending → in-progress
          in-progress → done
          done → qa-pass | qa-fail
          qa-fail → in-progress

        Args:
            task_id: Task identifier, e.g. "TASK-001".
            new_status: Target status (in-progress, done, qa-pass, qa-fail).
        """
        if not re.match(r"^TASK-\d{3}$", task_id):
            return f"Invalid task_id format: {task_id}. Expected TASK-NNN."

        valid_statuses = {"in-progress", "done", "qa-pass", "qa-fail"}
        if new_status not in valid_statuses:
            return f"Invalid status: {new_status}. Valid: {', '.join(sorted(valid_statuses))}"

        script = os.path.join(_tools_dir(workspace_root), "task-status.sh")
        if not os.path.isfile(script):
            return f"task-status.sh not found at {script}"

        result = subprocess.run(
            [script, task_id, new_status],
            capture_output=True,
            text=True,
            cwd=workspace_root,
            timeout=300,
        )

        output = result.stdout
        if result.returncode != 0:
            output += f"\nERROR (exit {result.returncode}):\n{result.stderr}"

        return output
