#!/bin/bash
set -e

# Initialize a git repo in /workspace root so Claude CLI doesn't fall back to /repo.
if [ ! -d "/workspace/.git" ]; then
    git init /workspace -q 2>/dev/null || true
    git -C /workspace config user.email "agent@console.local" 2>/dev/null || true
    git -C /workspace config user.name "Agent Console" 2>/dev/null || true
fi

# Mark /workspace as safe (needed in Docker with volume mounts).
git config --global --add safe.directory /workspace 2>/dev/null || true
# Mark all subdirectories as safe too
git config --global --add safe.directory '*' 2>/dev/null || true

exec "$@"
