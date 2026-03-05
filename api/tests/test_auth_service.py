from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import auth_service
from app.services.auth_service import (
    AuthLoginError,
    _generate_pkce,
    exchange_code,
    get_auth_status,
    get_current_access_token,
    start_oauth_login,
)


class TestGeneratePkce:
    def test_returns_verifier_and_challenge(self):
        verifier, challenge = _generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0

    def test_no_padding(self):
        verifier, challenge = _generate_pkce()
        assert "=" not in verifier
        assert "=" not in challenge

    def test_challenge_is_sha256_of_verifier(self):
        import base64
        import hashlib

        verifier, challenge = _generate_pkce()
        expected_digest = hashlib.sha256(verifier.encode()).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode()
        assert challenge == expected_challenge

    def test_unique_each_call(self):
        v1, _ = _generate_pkce()
        v2, _ = _generate_pkce()
        assert v1 != v2


class TestStartOAuthLogin:
    @pytest.mark.asyncio
    async def test_returns_url_with_params(self):
        url = await start_oauth_login()
        assert "https://claude.ai/oauth/authorize?" in url
        assert "response_type=code" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "client_id=" in url
        assert "redirect_uri=" in url
        assert "scope=" in url

    @pytest.mark.asyncio
    async def test_stores_code_verifier(self):
        auth_service._code_verifier = None
        await start_oauth_login()
        assert auth_service._code_verifier is not None


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_raises_without_login(self):
        auth_service._code_verifier = None
        with pytest.raises(AuthLoginError, match="No active login session"):
            await exchange_code("some-code")

    @pytest.mark.asyncio
    async def test_clears_verifier_after_exchange(self):
        auth_service._code_verifier = "test-verifier"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_client),
            patch("app.services.auth_service.async_session", return_value=mock_session),
        ):
            await exchange_code("auth-code")

        assert auth_service._code_verifier is None

    @pytest.mark.asyncio
    async def test_raises_on_token_error(self):
        auth_service._code_verifier = "test-verifier"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.auth_service.httpx.AsyncClient", return_value=mock_client),
            pytest.raises(AuthLoginError, match="Token exchange failed"),
        ):
            await exchange_code("bad-code")


class TestGetAuthStatus:
    @pytest.mark.asyncio
    async def test_not_logged_in_when_no_token(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            status = await get_auth_status()

        assert status.logged_in is False

    @pytest.mark.asyncio
    async def test_logged_in_with_valid_token(self):
        mock_token = MagicMock()
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_token.email = "user@example.com"
        mock_token.subscription_type = "pro"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            status = await get_auth_status()

        assert status.logged_in is True
        assert status.email == "user@example.com"

    @pytest.mark.asyncio
    async def test_not_logged_in_when_expired(self):
        mock_token = MagicMock()
        mock_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_token.email = "user@example.com"
        mock_token.subscription_type = "pro"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            status = await get_auth_status()

        assert status.logged_in is False


class TestGetCurrentAccessToken:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            token = await get_current_access_token()

        assert token is None

    @pytest.mark.asyncio
    async def test_returns_token_when_valid(self):
        mock_token = MagicMock()
        mock_token.access_token = "valid_token"
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            token = await get_current_access_token()

        assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_returns_none_when_expired_no_refresh(self):
        mock_token = MagicMock()
        mock_token.access_token = "expired_token"
        mock_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_token.refresh_token = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_token

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.auth_service.async_session", return_value=mock_session):
            token = await get_current_access_token()

        assert token is None
