import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class LinkType(str, Enum):
    handoff = "handoff"
    review = "review"
    migration_brief = "migration_brief"


class AgentLinkCreate(BaseModel):
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    link_type: LinkType


class AgentLinkRead(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    from_agent_id: uuid.UUID
    to_agent_id: uuid.UUID
    link_type: LinkType
    created_at: datetime

    model_config = {"from_attributes": True}
