from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select

from app.config import settings
from app.database import async_session
from app.models.oauth_token import OAuthToken
from app.schemas.auth import AuthStatusRead

logger = logging.getLogger(__name__)

_code_verifier: Optional[str] = None
_oauth_state: Optional[str] = None


class AuthCheckError(Exception):
    pass


class AuthLoginError(Exception):
    pass


def _generate_pkce() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) for OAuth PKCE S256."""
    verifier_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


async def start_oauth_login() -> str:
    """Generate OAuth URL with PKCE. Stores code_verifier at module level."""
    global _code_verifier, _oauth_state

    code_verifier, code_challenge = _generate_pkce()
    _code_verifier = code_verifier

    state = secrets.token_urlsafe(32)
    _oauth_state = state

    params = {
        "code": "true",
        "client_id": settings.oauth_client_id,
        "response_type": "code",
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": settings.oauth_scopes,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = f"{settings.oauth_authorize_url}?{urlencode(params)}"
    return url


async def exchange_code(code: str) -> None:
    """Exchange authorization code for tokens. Save to DB."""
    global _code_verifier, _oauth_state

    if _code_verifier is None:
        raise AuthLoginError("No active login session. Call /login first.")

    verifier = _code_verifier
    state = _oauth_state
    _code_verifier = None
    _oauth_state = None

    code = code.strip()
    if "#" in code:
        code = code.split("#")[0]

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri,
        "client_id": settings.oauth_client_id,
        "code_verifier": verifier,
        "state": state,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.oauth_token_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    if resp.status_code != 200:
        logger.error("OAuth token exchange failed: %s %s", resp.status_code, resp.text)
        raise AuthLoginError(f"Token exchange failed: {resp.status_code} {resp.text}")

    body = resp.json()
    access_token = body["access_token"]
    refresh_token = body.get("refresh_token")
    expires_in = body.get("expires_in")

    expires_at = None
    if expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    async with async_session() as db:
        await db.execute(delete(OAuthToken))
        token = OAuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        db.add(token)
        await db.commit()


async def get_auth_status() -> AuthStatusRead:
    """Read token from DB, check expires_at."""
    async with async_session() as db:
        result = await db.execute(select(OAuthToken).limit(1))
        token = result.scalar_one_or_none()

    if not token:
        return AuthStatusRead(logged_in=False)

    expired = False
    if token.expires_at:
        expired = datetime.now(timezone.utc) >= token.expires_at

    return AuthStatusRead(
        logged_in=not expired,
        email=token.email,
        subscription_type=token.subscription_type,
    )


async def get_current_access_token() -> Optional[str]:
    """Return valid access_token. Refresh if expired. Return None if unavailable."""
    async with async_session() as db:
        result = await db.execute(select(OAuthToken).limit(1))
        token = result.scalar_one_or_none()

    if not token:
        return None

    if token.expires_at and datetime.now(timezone.utc) >= token.expires_at:
        if not token.refresh_token:
            return None
        try:
            new_data = await _refresh_access_token(token.refresh_token)
        except AuthLoginError:
            return None

        new_expires_at = None
        if new_data.get("expires_in"):
            new_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=int(new_data["expires_in"])
            )

        async with async_session() as db:
            await db.execute(delete(OAuthToken))
            refreshed = OAuthToken(
                access_token=new_data["access_token"],
                refresh_token=new_data.get("refresh_token", token.refresh_token),
                expires_at=new_expires_at,
                email=token.email,
                subscription_type=token.subscription_type,
            )
            db.add(refreshed)
            await db.commit()
        return new_data["access_token"]

    return token.access_token


async def _refresh_access_token(refresh_token: str) -> dict:
    """POST token_url with grant_type=refresh_token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.oauth_client_id,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.oauth_token_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    if resp.status_code != 200:
        logger.error("OAuth refresh failed: %s %s", resp.status_code, resp.text)
        raise AuthLoginError(f"Token refresh failed: {resp.status_code}")

    return resp.json()


async def auth_logout() -> None:
    """Delete all tokens from DB."""
    async with async_session() as db:
        await db.execute(delete(OAuthToken))
        await db.commit()
