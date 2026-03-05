from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.auth import AuthStatusRead
from app.services.auth_service import AuthCheckError, AuthLoginError

ROUTER = "app.routers.auth"


@pytest.mark.asyncio
async def test_auth_status_logged_in(client):
    status = AuthStatusRead(
        logged_in=True,
        email="user@example.com",
        org_name="TestOrg",
        subscription_type="pro",
        auth_method="oauth",
    )
    with patch(f"{ROUTER}.get_auth_status", new_callable=AsyncMock, return_value=status):
        resp = await client.get("/api/auth/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["logged_in"] is True
    assert data["email"] == "user@example.com"
    assert data["org_name"] == "TestOrg"
    assert data["subscription_type"] == "pro"
    assert data["auth_method"] == "oauth"


@pytest.mark.asyncio
async def test_auth_status_not_logged_in(client):
    status = AuthStatusRead(logged_in=False)
    with patch(f"{ROUTER}.get_auth_status", new_callable=AsyncMock, return_value=status):
        resp = await client.get("/api/auth/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["logged_in"] is False
    assert data["email"] is None


@pytest.mark.asyncio
async def test_auth_status_cli_error(client):
    with patch(
        f"{ROUTER}.get_auth_status",
        new_callable=AsyncMock,
        side_effect=AuthCheckError("command not found"),
    ):
        resp = await client.get("/api/auth/status")

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_auth_login_returns_url(client):
    with patch(
        f"{ROUTER}.start_auth_login",
        new_callable=AsyncMock,
        return_value="https://auth.example.com/oauth?code=abc123",
    ):
        resp = await client.post("/api/auth/login")

    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_url"] == "https://auth.example.com/oauth?code=abc123"
    assert "message" in data


@pytest.mark.asyncio
async def test_auth_login_no_url(client):
    with patch(
        f"{ROUTER}.start_auth_login",
        new_callable=AsyncMock,
        side_effect=AuthLoginError("OAuth URL not found"),
    ):
        resp = await client.post("/api/auth/login")

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_auth_logout(client):
    with patch(f"{ROUTER}.auth_logout", new_callable=AsyncMock):
        resp = await client.post("/api/auth/logout")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_auth_logout_error(client):
    with patch(
        f"{ROUTER}.auth_logout",
        new_callable=AsyncMock,
        side_effect=AuthCheckError("logout failed"),
    ):
        resp = await client.post("/api/auth/logout")

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_auth_callback_submits_code(client):
    with patch(f"{ROUTER}.submit_auth_code", new_callable=AsyncMock):
        resp = await client.post("/api/auth/callback", json={"code": "abc123"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Code submitted"


@pytest.mark.asyncio
async def test_auth_callback_no_process(client):
    with patch(
        f"{ROUTER}.submit_auth_code",
        new_callable=AsyncMock,
        side_effect=AuthLoginError("No active login process"),
    ):
        resp = await client.post("/api/auth/callback", json={"code": "abc123"})

    assert resp.status_code == 400
