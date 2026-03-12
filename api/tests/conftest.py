import pytest
from unittest.mock import MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from mcp_server.tools.platform import register_platform_tools


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def registered_platform_tools():
    """Возвращает dict {tool_name: func} всех зарегистрированных platform tools."""
    mcp_mock = MagicMock()
    registered = {}

    def tool_decorator(f):
        registered[f.__name__] = f
        return f

    mcp_mock.tool.return_value = tool_decorator
    register_platform_tools(mcp_mock)
    return registered
