import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    starting_agent_id: uuid.UUID
    starting_prompt: str = Field(..., min_length=1)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    starting_agent_id: uuid.UUID | None = None
    starting_prompt: str | None = Field(None, min_length=1)


class WorkflowRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    team_id: uuid.UUID
    starting_agent_id: uuid.UUID
    starting_prompt: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowLockStatusRequest(BaseModel):
    workflow_ids: list[uuid.UUID] = Field(..., max_length=100)


class WorkflowLockStatusResponse(BaseModel):
    locked_ids: list[uuid.UUID]
