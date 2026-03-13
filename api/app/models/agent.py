import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("team_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prompts: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    sub_agent_templates: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    max_cycles: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    can_complete_task: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    position_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    team = relationship("Team", back_populates="agents")
    sessions = relationship(
        "Session", back_populates="agent", cascade="all, delete-orphan"
    )
