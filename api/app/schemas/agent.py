import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    allowed_tools: Optional[list[str]] = None
    config: Optional[dict[str, Any]] = None


class AgentRead(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    role: str
    description: Optional[str]
    system_prompt: str
    allowed_tools: list[str]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
