import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BusinessCreate(BaseModel):
    name: str
    description: Optional[str] = None


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BusinessRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    products_count: int

    model_config = ConfigDict(from_attributes=True)
