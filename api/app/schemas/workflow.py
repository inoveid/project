import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    starting_agent_id: uuid.UUID
    starting_prompt: str = Field(..., min_length=1)
    isolation_mode: str = Field("none", pattern="^(none|worktree)$")
    auto_merge: bool = False


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    starting_agent_id: uuid.UUID | None = None
    starting_prompt: str | None = Field(None, min_length=1)
    isolation_mode: str | None = Field(None, pattern="^(none|worktree)$")
    auto_merge: bool | None = None


class WorkflowRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    team_id: uuid.UUID
    starting_agent_id: uuid.UUID
    starting_prompt: str
    isolation_mode: str
    auto_merge: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowLockStatusRequest(BaseModel):
    workflow_ids: list[uuid.UUID] = Field(..., max_length=100)


class WorkflowLockStatusResponse(BaseModel):
    locked_ids: list[uuid.UUID]
