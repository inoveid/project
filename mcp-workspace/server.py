"""MCP server for agent workspace tools.

Exposes workspace operations (tasks, specs, project context)
as standardized MCP tools and resources.

Usage:
    WORKSPACE_ROOT=/path/to/workspace python server.py
"""

import os

from mcp.server.fastmcp import FastMCP

from tools.tasks import register_task_tools
from tools.specs import register_spec_tools

# Default: 3 levels up from mcp-workspace/server.py → agent-console/
_this_dir = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.environ.get(
    "WORKSPACE_ROOT",
    os.path.dirname(os.path.dirname(_this_dir)),
)

mcp = FastMCP(
    "workspace-tools",
    instructions=(
        "Workspace tools for AI agents. "
        "Use task tools to list, read, and update tasks. "
        "Use spec tools to read architecture specs and ADRs. "
        "Use resources to access project context."
    ),
)

# Register tool groups
register_task_tools(mcp, WORKSPACE_ROOT)
register_spec_tools(mcp, WORKSPACE_ROOT)


# --- Resources ---

@mcp.resource("workspace://project/context")
def get_project_context() -> str:
    """Project overview: structure, commands, conventions."""
    claude_md = os.path.join(WORKSPACE_ROOT, "project", "CLAUDE.md")
    if os.path.isfile(claude_md):
        with open(claude_md) as f:
            return f.read()
    return "No project CLAUDE.md found."


@mcp.resource("workspace://protocol")
def get_protocol() -> str:
    """Team protocol: handoff formats, task lifecycle, conventions."""
    protocol_md = os.path.join(WORKSPACE_ROOT, "PROTOCOL.md")
    if os.path.isfile(protocol_md):
        with open(protocol_md) as f:
            return f.read()
    return "No PROTOCOL.md found."


if __name__ == "__main__":
    mcp.run()
