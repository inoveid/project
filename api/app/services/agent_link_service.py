"""Backward-compatibility stub. Will be removed in TASK-049 when
graph_service.py and ws.py switch to workflow-based routing."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


async def get_agent_handoff_targets(
    db: AsyncSession, agent_id: uuid.UUID
) -> list[Agent]:
    """Stub: agent_links table was replaced by workflows.
    Returns empty list until TASK-049 migrates graph_service to workflows."""
    return []
