"""Pytest configuration for mcp-workspace tests."""

import sys
import os

import pytest

# Add the mcp-workspace root to sys.path so we can import tools.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class MockMCP:
    """Minimal MCP stub that captures registered tool functions."""

    def __init__(self):
        self._tools: dict = {}

    def tool(self, annotations=None):
        def decorator(fn):
            self._tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.fixture
def mock_mcp():
    return MockMCP()
