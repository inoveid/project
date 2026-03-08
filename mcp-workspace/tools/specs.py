"""Specification and ADR tools for MCP server.

Reads specs from {workspace}/process/specs/ and ADRs from
{workspace}/process/specs/adr/.
"""

import os


def _specs_dir(workspace_root: str) -> str:
    return os.path.join(workspace_root, "process", "specs")


def _adr_dir(workspace_root: str) -> str:
    return os.path.join(workspace_root, "process", "specs", "adr")


def register_spec_tools(mcp, workspace_root: str) -> None:
    """Register spec and ADR tools on the MCP server."""

    @mcp.tool()
    def list_specs() -> str:
        """List all specification files and architecture decision records (ADRs).

        Returns two sections:
        - Specs: architecture, scaffolding, and other design documents
        - ADRs: architecture decision records (ADR-NNN-title.md)
        """
        specs_path = _specs_dir(workspace_root)
        if not os.path.isdir(specs_path):
            return f"Specs directory not found: {specs_path}"

        spec_files = sorted(
            f for f in os.listdir(specs_path)
            if f.endswith(".md") and os.path.isfile(os.path.join(specs_path, f))
        )

        adr_path = _adr_dir(workspace_root)
        adr_files = []
        if os.path.isdir(adr_path):
            adr_files = sorted(
                f for f in os.listdir(adr_path)
                if f.endswith(".md")
            )

        lines = ["## Specifications\n"]
        if spec_files:
            for f in spec_files:
                lines.append(f"- {f}")
        else:
            lines.append("No spec files found.")

        lines.append("\n## Architecture Decision Records (ADR)\n")
        if adr_files:
            for f in adr_files:
                lines.append(f"- {f}")
        else:
            lines.append("No ADR files found.")

        return "\n".join(lines)

    @mcp.tool()
    def get_spec(filename: str) -> str:
        """Read a specification or ADR file.

        For specs: pass the filename directly (e.g. "architecture.md").
        For ADRs: pass "adr/ADR-001-initial-stack.md".

        Args:
            filename: Relative path within the specs directory.
                      Examples: "architecture.md", "adr/ADR-001-initial-stack.md"
        """
        specs_path = _specs_dir(workspace_root)
        filepath = os.path.normpath(os.path.join(specs_path, filename))

        # Prevent path traversal
        if not filepath.startswith(specs_path):
            return "Error: path traversal not allowed."

        if not os.path.isfile(filepath):
            return f"File not found: {filename}"

        with open(filepath) as f:
            return f.read()
