import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ProductStatus = Literal["pending", "cloning", "ready", "error"]


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    git_url: Optional[str] = None
    business_id: Optional[uuid.UUID] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    git_url: Optional[str] = None


class ProductRead(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    description: Optional[str]
    git_url: Optional[str]
    workspace_path: str
    status: ProductStatus
    clone_error: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
