import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class WorkflowEdgeCreate(BaseModel):
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    condition: str | None = None
    prompt_template: str | None = None
    prompt_id: str | None = None
    order: int = 0
    requires_approval: bool = True

    @model_validator(mode="after")
    def check_no_self_edge(self) -> "WorkflowEdgeCreate":
        if self.from_agent_id == self.to_agent_id:
            raise ValueError("from_agent_id and to_agent_id must be different")
        return self


class WorkflowEdgeUpdate(BaseModel):
    condition: str | None = None
    prompt_template: str | None = None
    prompt_id: str | None = None
    order: int | None = None
    requires_approval: bool | None = None


class WorkflowEdgeRead(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    condition: str | None
    prompt_template: str | None
    prompt_id: str | None
    order: int
    requires_approval: bool
    created_at: datetime

    model_config = {"from_attributes": True}
