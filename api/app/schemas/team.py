import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    project_scoped: bool = False


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    project_scoped: Optional[bool] = None


class TeamRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    project_scoped: bool
    created_at: datetime
    updated_at: datetime
    agents_count: int = 0

    model_config = {"from_attributes": True}
