#!/bin/bash
set -e

# Initialize a git repo in /workspace root so Claude CLI doesn't fall back to /repo.
# Real projects live as subdirectories: /workspace/{project-name}/ (each has its own .git).
if [ ! -d "/workspace/.git" ]; then
    git init /workspace -q
    git -C /workspace config user.email "agent@console.local"
    git -C /workspace config user.name "Agent Console"
fi

# Mark /workspace as safe (needed when running as root in Docker).
git config --global --add safe.directory /workspace

exec "$@"
