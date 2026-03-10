import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    product_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
    workflow_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    product_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None
    workflow_id: Optional[uuid.UUID] = None


class TaskStatusUpdate(BaseModel):
    status: str


class TaskRead(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    product_id: Optional[uuid.UUID]
    team_id: Optional[uuid.UUID]
    workflow_id: Optional[uuid.UUID]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
