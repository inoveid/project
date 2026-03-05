from typing import Optional

from pydantic import BaseModel


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
