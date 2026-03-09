"""Unit tests for mcp-workspace spec tools (including path traversal protection)."""

import pytest

from tools.specs import register_spec_tools


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace with specs and adr directories."""
    specs_dir = tmp_path / "process" / "specs"
    specs_dir.mkdir(parents=True)

    (specs_dir / "architecture.md").write_text("# Architecture\nContent here.")
    (specs_dir / "scaffolding.md").write_text("# Scaffolding\nAnother doc.")

    adr_dir = specs_dir / "adr"
    adr_dir.mkdir()
    (adr_dir / "ADR-001-initial-stack.md").write_text("# ADR-001\nDecision: FastAPI.")

    # Sibling directory for traversal test
    evil_dir = tmp_path / "process" / "specs_evil"
    evil_dir.mkdir()
    (evil_dir / "secret.md").write_text("SECRET DATA")

    return tmp_path


@pytest.fixture
def tools(workspace, mock_mcp):
    """Register spec tools and return the tool dict."""
    register_spec_tools(mock_mcp, str(workspace))
    return mock_mcp._tools


def test_list_specs_returns_all(tools):
    """list_specs lists both spec files and ADR files."""
    result = tools["list_specs"]()
    assert "architecture.md" in result
    assert "scaffolding.md" in result
    assert "ADR-001-initial-stack.md" in result


def test_get_spec_valid(tools):
    """get_spec returns file content for a valid spec filename."""
    result = tools["get_spec"]("architecture.md")
    assert "# Architecture" in result
    assert "Content here." in result


def test_get_spec_adr_subdirectory(tools):
    """get_spec allows reading files inside adr/ subdirectory."""
    result = tools["get_spec"]("adr/ADR-001-initial-stack.md")
    assert "# ADR-001" in result
    assert "Decision: FastAPI." in result


def test_get_spec_path_traversal_blocked(tools):
    """get_spec blocks ../../etc/passwd style traversal."""
    result = tools["get_spec"]("../../etc/passwd")
    assert "path traversal not allowed" in result.lower()


def test_get_spec_sibling_dir_blocked(tools):
    """get_spec blocks traversal to sibling directory specs_evil/."""
    result = tools["get_spec"]("../specs_evil/secret.md")
    assert "path traversal not allowed" in result.lower()
    assert "SECRET DATA" not in result


def test_get_spec_nonexistent(tools):
    """get_spec returns error for a file that does not exist."""
    result = tools["get_spec"]("nonexistent.md")
    assert "not found" in result.lower()
