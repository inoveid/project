import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class AuthStatusRead(BaseModel):
    logged_in: bool
    email: Optional[str] = None
    org_name: Optional[str] = None
    subscription_type: Optional[str] = None
    auth_method: Optional[str] = None


class AuthLoginResponse(BaseModel):
    auth_url: str
    message: str


class AuthCodeSubmit(BaseModel):
    code: str


# ── User auth ──

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
