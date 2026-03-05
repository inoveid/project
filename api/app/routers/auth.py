from fastapi import APIRouter, HTTPException

from app.schemas.auth import AuthCodeSubmit, AuthLoginResponse, AuthStatusRead
from app.services.auth_service import (
    AuthCheckError,
    AuthLoginError,
    auth_logout,
    exchange_code,
    get_auth_status,
    start_oauth_login,
)

router = APIRouter()


@router.get("/status", response_model=AuthStatusRead)
async def auth_status_endpoint():
    try:
        return await get_auth_status()
    except AuthCheckError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/login", response_model=AuthLoginResponse)
async def auth_login_endpoint():
    try:
        url = await start_oauth_login()
    except AuthLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return AuthLoginResponse(
        auth_url=url,
        message="Open the URL in a browser to complete authentication",
    )


@router.post("/callback")
async def auth_callback_endpoint(body: AuthCodeSubmit):
    try:
        await exchange_code(body.code)
    except AuthLoginError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Authenticated"}


@router.post("/logout", status_code=204)
async def auth_logout_endpoint():
    try:
        await auth_logout()
    except AuthCheckError as e:
        raise HTTPException(status_code=503, detail=str(e))
