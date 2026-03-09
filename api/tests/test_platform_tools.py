"""Тесты для MCP platform tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import mcp.tools.platform as platform_module


def _make_response(data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def patch_base_url(monkeypatch):
    monkeypatch.setattr(platform_module.settings, "api_base_url", "http://testserver")


class TestPlatformToolsRegistration:
    def test_register_platform_tools_attaches_tools(self):
        """register_platform_tools регистрирует инструменты на mcp без ошибок."""
        mcp_mock = MagicMock()
        tool_decorator = MagicMock(side_effect=lambda f: f)
        mcp_mock.tool.return_value = tool_decorator

        from mcp.tools.platform import register_platform_tools
        register_platform_tools(mcp_mock)

        assert mcp_mock.tool.call_count == 8


class TestApiHelper:
    @pytest.mark.asyncio
    async def test_api_get_returns_json(self):
        response = _make_response([{"id": "1"}])
        with patch("mcp.tools.platform.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            from mcp.tools.platform import _api
            result = await _api("get", "/api/businesses")

        assert result == [{"id": "1"}]
        response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_204_returns_empty_dict(self):
        response = _make_response(None, status_code=204)
        with patch("mcp.tools.platform.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            from mcp.tools.platform import _api
            result = await _api("delete", "/api/something")

        assert result == {}


class TestPlatformToolsFunctions:
    """Тесты вызовов каждого инструмента через замоканный _api."""

    @pytest.mark.asyncio
    async def test_list_businesses(self, registered_platform_tools):
        businesses = [{"id": "b1", "name": "Acme"}]
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=businesses)):
            result = await registered_platform_tools["list_businesses"]()
        assert result == businesses

    @pytest.mark.asyncio
    async def test_create_business(self, registered_platform_tools):
        business = {"id": "b1", "name": "Acme", "description": None}
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=business)):
            result = await registered_platform_tools["create_business"]("Acme")
        assert result["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_create_business_with_description(self, registered_platform_tools):
        business = {"id": "b1", "name": "Acme", "description": "Corp"}
        api_mock = AsyncMock(return_value=business)
        with patch("mcp.tools.platform._api", new=api_mock):
            await registered_platform_tools["create_business"]("Acme", "Corp")
            api_mock.assert_called_once_with(
                "post", "/api/businesses",
                json={"name": "Acme", "description": "Corp"}
            )

    @pytest.mark.asyncio
    async def test_list_products(self, registered_platform_tools):
        products = [{"id": "p1"}]
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=products)):
            result = await registered_platform_tools["list_products"]("b1")
        assert result == products

    @pytest.mark.asyncio
    async def test_create_product(self, registered_platform_tools):
        product = {"id": "p1", "name": "Widget"}
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=product)):
            result = await registered_platform_tools["create_product"]("b1", "Widget")
        assert result["name"] == "Widget"

    @pytest.mark.asyncio
    async def test_list_teams(self, registered_platform_tools):
        teams = [{"id": "t1", "name": "Dev"}]
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=teams)):
            result = await registered_platform_tools["list_teams"]()
        assert result == teams

    @pytest.mark.asyncio
    async def test_create_team(self, registered_platform_tools):
        team = {"id": "t1", "name": "Dev"}
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=team)):
            result = await registered_platform_tools["create_team"]("Dev")
        assert result["name"] == "Dev"

    @pytest.mark.asyncio
    async def test_list_agents_all(self, registered_platform_tools):
        agents = [{"id": "a1"}]
        api_mock = AsyncMock(return_value=agents)
        with patch("mcp.tools.platform._api", new=api_mock):
            result = await registered_platform_tools["list_agents"]()
        api_mock.assert_called_once_with("get", "/api/agents")
        assert result == agents

    @pytest.mark.asyncio
    async def test_list_agents_by_team(self, registered_platform_tools):
        agents = [{"id": "a1"}]
        api_mock = AsyncMock(return_value=agents)
        with patch("mcp.tools.platform._api", new=api_mock):
            result = await registered_platform_tools["list_agents"]("t1")
        api_mock.assert_called_once_with("get", "/api/teams/t1/agents")
        assert result == agents

    @pytest.mark.asyncio
    async def test_create_agent(self, registered_platform_tools):
        agent = {"id": "a1", "name": "Bot"}
        with patch("mcp.tools.platform._api", new=AsyncMock(return_value=agent)):
            result = await registered_platform_tools["create_agent"]("Bot", "t1", "You are Bot.")
        assert result["name"] == "Bot"
