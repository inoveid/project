from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("AC_API_BASE_URL", "http://localhost:8000")


async def _api(method: str, path: str, **kwargs: Any) -> Any:
    """Базовый HTTP клиент для вызова API платформы."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        response = await getattr(client, method)(path, **kwargs)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()


def register_platform_tools(mcp: "FastMCP") -> None:

    @mcp.tool()
    async def list_businesses() -> list[dict]:
        """Получить список всех бизнесов."""
        return await _api("get", "/api/businesses")

    @mcp.tool()
    async def create_business(name: str, description: str = "") -> dict:
        """Создать новый бизнес.

        Args:
            name: Название бизнеса
            description: Описание (необязательно)
        """
        return await _api("post", "/api/businesses",
                          json={"name": name, "description": description or None})

    @mcp.tool()
    async def list_products(business_id: str) -> list[dict]:
        """Получить список продуктов бизнеса.

        Args:
            business_id: UUID бизнеса
        """
        return await _api("get", f"/api/businesses/{business_id}/products")

    @mcp.tool()
    async def create_product(business_id: str, name: str,
                             git_url: str = "", description: str = "") -> dict:
        """Создать новый продукт в бизнесе.

        Args:
            business_id: UUID бизнеса
            name: Название продукта
            git_url: URL git-репозитория (необязательно)
            description: Описание (необязательно)
        """
        return await _api("post", f"/api/businesses/{business_id}/products", json={
            "business_id": business_id,
            "name": name,
            "git_url": git_url or None,
            "description": description or None,
        })

    @mcp.tool()
    async def list_teams() -> list[dict]:
        """Получить список всех команд агентов."""
        return await _api("get", "/api/teams")

    @mcp.tool()
    async def create_team(name: str, description: str = "") -> dict:
        """Создать новую команду агентов.

        Args:
            name: Название команды
            description: Описание (необязательно)
        """
        return await _api("post", "/api/teams",
                          json={"name": name, "description": description or None})

    @mcp.tool()
    async def list_agents(team_id: str = "") -> list[dict]:
        """Получить список агентов. Если team_id указан — только агенты команды.

        Args:
            team_id: UUID команды (необязательно)
        """
        if team_id:
            return await _api("get", f"/api/teams/{team_id}/agents")
        return await _api("get", "/api/agents")

    @mcp.tool()
    async def create_agent(name: str, team_id: str, system_prompt: str,
                           description: str = "") -> dict:
        """Создать нового агента в команде.

        Args:
            name: Имя агента
            team_id: UUID команды
            system_prompt: Системный промпт агента
            description: Описание (необязательно)
        """
        return await _api("post", "/api/agents", json={
            "name": name,
            "team_id": team_id,
            "system_prompt": system_prompt,
            "description": description or None,
        })
