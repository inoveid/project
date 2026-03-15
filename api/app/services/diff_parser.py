"""Parse unified diff into per-file structured data."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FileDiff:
    path: str
    status: str  # M, A, D
    additions: int = 0
    deletions: int = 0
    patch: str = ""


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    """Parse unified diff output into per-file FileDiff objects."""
    if not diff_text or not diff_text.strip():
        return []

    files: list[FileDiff] = []
    current: FileDiff | None = None
    patch_lines: list[str] = []

    for line in diff_text.splitlines(keepends=True):
        # New file header
        if line.startswith("diff --git"):
            # Save previous
            if current:
                current.patch = "".join(patch_lines)
                files.append(current)

            # Extract path from "diff --git a/path b/path"
            m = re.match(r"diff --git a/(.*) b/(.*)", line.strip())
            path = m.group(2) if m else "unknown"
            current = FileDiff(path=path, status="M")
            patch_lines = [line]
            continue

        if current is None:
            continue

        patch_lines.append(line)

        # Detect status
        if line.startswith("new file"):
            current.status = "A"
        elif line.startswith("deleted file"):
            current.status = "D"
        elif line.startswith("rename from"):
            current.status = "R"

        # Count additions/deletions (only in hunk lines)
        if line.startswith("+") and not line.startswith("+++"):
            current.additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.deletions += 1

    # Save last file
    if current:
        current.patch = "".join(patch_lines)
        files.append(current)

    return files


def diff_files_to_dict(files: list[FileDiff]) -> list[dict]:
    """Convert FileDiff list to JSON-serializable dicts."""
    return [
        {
            "path": f.path,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "patch": f.patch,
        }
        for f in files
    ]
