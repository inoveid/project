"""Tests for specs.py path traversal protection (BUG-5 fix).

Reproduces the path validation logic from mcp-workspace/tools/specs.py
without importing it (separate package).
"""

import os
import tempfile


def _check_path_traversal(specs_path: str, filename: str) -> str | None:
    """Reproduce the path traversal check from specs.py get_spec()."""
    filepath = os.path.normpath(os.path.join(specs_path, filename))

    # This is the fixed check (with os.sep)
    if not filepath.startswith(specs_path + os.sep) and filepath != specs_path:
        return "Error: path traversal not allowed."

    if not os.path.isfile(filepath):
        return f"File not found: {filename}"

    with open(filepath) as f:
        return f.read()


def test_allows_legitimate_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        specs_dir = os.path.join(tmpdir, "process", "specs")
        os.makedirs(specs_dir)
        with open(os.path.join(specs_dir, "architecture.md"), "w") as f:
            f.write("Legitimate content")

        result = _check_path_traversal(specs_dir, "architecture.md")
        assert result == "Legitimate content"


def test_blocks_parent_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        specs_dir = os.path.join(tmpdir, "process", "specs")
        os.makedirs(specs_dir)

        result = _check_path_traversal(specs_dir, "../../etc/passwd")
        assert "path traversal not allowed" in result.lower()


def test_blocks_sibling_directory_traversal():
    """Sibling dir 'specs_evil' starts with 'specs' — must be blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        specs_dir = os.path.join(tmpdir, "process", "specs")
        os.makedirs(specs_dir)

        sibling_dir = os.path.join(tmpdir, "process", "specs_evil")
        os.makedirs(sibling_dir)
        with open(os.path.join(sibling_dir, "secret.md"), "w") as f:
            f.write("SECRET DATA")

        result = _check_path_traversal(specs_dir, "../specs_evil/secret.md")
        assert "path traversal not allowed" in result.lower()


def test_allows_subdirectory():
    """Files in subdirectories like adr/ should be allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        specs_dir = os.path.join(tmpdir, "process", "specs")
        adr_dir = os.path.join(specs_dir, "adr")
        os.makedirs(adr_dir)
        with open(os.path.join(adr_dir, "ADR-001.md"), "w") as f:
            f.write("ADR content")

        result = _check_path_traversal(specs_dir, "adr/ADR-001.md")
        assert result == "ADR content"
