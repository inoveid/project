from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthCodeSubmit,
    AuthLoginResponse,
    AuthStatusRead,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.services.auth_service import (
    AuthCheckError,
    AuthLoginError,
    auth_logout,
    exchange_code,
    get_auth_status,
    start_oauth_login,
)
from app.services.auth_user_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    invite_user,
    register_user,
)

router = APIRouter()


# ── User auth (login/password + JWT) ──────────────────────────────────────


@router.get("/registration-open")
async def registration_open_endpoint(db: AsyncSession = Depends(get_db)):
    """Check if registration is open (no users yet)."""
    count_result = await db.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar() or 0
    return {"open": user_count == 0}


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register_endpoint(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data.email, data.password, data.name)
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserRead(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserRead(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserRead)
async def me_endpoint(user=Depends(get_current_user)):
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/invite", response_model=TokenResponse, status_code=201)
async def invite_endpoint(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only: create a new user."""
    user = await invite_user(db, data.email, data.password, data.name, current_user)
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserRead(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            created_at=user.created_at,
        ),
    )


# ── Claude OAuth (для агентов) ────────────────────────────────────────────


@router.get("/claude/status", response_model=AuthStatusRead)
async def claude_auth_status_endpoint():
    try:
        return await get_auth_status()
    except AuthCheckError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/claude/login", response_model=AuthLoginResponse)
async def claude_auth_login_endpoint():
    try:
        url = await start_oauth_login()
    except AuthLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return AuthLoginResponse(
        auth_url=url,
        message="Open the URL in a browser to complete authentication",
    )


@router.post("/claude/callback")
async def claude_auth_callback_endpoint(body: AuthCodeSubmit):
    try:
        await exchange_code(body.code)
    except AuthLoginError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Authenticated"}


@router.post("/claude/logout", status_code=204)
async def claude_auth_logout_endpoint():
    try:
        await auth_logout()
    except AuthCheckError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Legacy aliases ──


@router.get("/status", response_model=AuthStatusRead)
async def auth_status_endpoint():
    try:
        return await get_auth_status()
    except AuthCheckError as e:
        raise HTTPException(status_code=503, detail=str(e))
