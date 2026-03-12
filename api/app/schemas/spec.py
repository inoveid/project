import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

SpecStatus = Literal["draft", "active"]


class SpecCreate(BaseModel):
    feature: str
    title: str
    content: str = ""
    status: SpecStatus = "draft"


class SpecUpdate(BaseModel):
    feature: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[SpecStatus] = None
    author: str = "user"
    summary: Optional[str] = None


class SpecRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    feature: str
    title: str
    content: str
    version: int
    status: SpecStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpecVersionRead(BaseModel):
    id: uuid.UUID
    spec_id: uuid.UUID
    version: int
    content: str
    author: str
    summary: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
