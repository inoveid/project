import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    agent_id: uuid.UUID


class MessageRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    tool_uses: Optional[list[dict]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionRead(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    claude_session_id: Optional[str] = None
    created_at: datetime
    stopped_at: Optional[datetime] = None
    messages: list[MessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str = ""
    status: str
    created_at: datetime
    stopped_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
