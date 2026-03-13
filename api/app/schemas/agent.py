import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Sub-agent templates ──────────────────────────────────────────────────────

class SubAgentTemplate(BaseModel):
    """Template for a sub-agent that can be spawned by the parent agent."""
    id: str = Field(..., description="Unique template identifier")
    role: str = Field(..., min_length=1, max_length=100, description="Role name used in spawn_agent(role=...)")
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    system_prompt: str = Field(..., min_length=1, description="System prompt for the sub-agent")
    allowed_tools: list[str] = Field(default_factory=list)
    max_budget_usd: float = Field(default=0.5, ge=0, description="Budget limit per spawn")
    description: str = Field(default="", description="Short description of what this sub-agent does")


# ── Agent schemas ────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    sub_agent_templates: list[SubAgentTemplate] = Field(default_factory=list)
    can_complete_task: bool = False
    is_system: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    allowed_tools: Optional[list[str]] = None
    config: Optional[dict[str, Any]] = None
    sub_agent_templates: Optional[list[SubAgentTemplate]] = None
    max_cycles: Optional[int] = None
    can_complete_task: Optional[bool] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class AgentRead(BaseModel):
    id: uuid.UUID
    team_id: Optional[uuid.UUID]
    name: str
    role: Optional[str]
    description: Optional[str]
    system_prompt: str
    allowed_tools: list[str]
    config: dict[str, Any]
    sub_agent_templates: list[SubAgentTemplate] = Field(default_factory=list)
    max_cycles: int = 3
    can_complete_task: bool = False
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentCanDeleteResponse(BaseModel):
    can_delete: bool
    reason: Optional[str] = None
