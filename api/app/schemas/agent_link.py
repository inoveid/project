import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class LinkType(str, Enum):
    handoff = "handoff"
    review = "review"
    migration_brief = "migration_brief"


class AgentLinkCreate(BaseModel):
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    link_type: LinkType

    @model_validator(mode="after")
    def check_no_self_link(self) -> "AgentLinkCreate":
        if self.from_agent_id == self.to_agent_id:
            raise ValueError("from_agent_id and to_agent_id must be different")
        return self


class AgentLinkRead(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    link_type: LinkType
    created_at: datetime

    model_config = {"from_attributes": True}
