import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.agent_link import AgentLink
from app.models.team import Team
from app.schemas.agent_link import AgentLinkCreate


class TeamNotFoundError(Exception):
    pass


class AgentNotInTeamError(Exception):
    pass


class DuplicateLinkError(Exception):
    pass


class LinkNotFoundError(Exception):
    pass


async def get_links(db: AsyncSession, team_id: uuid.UUID) -> list[AgentLink]:
    await _ensure_team_exists(db, team_id)
    stmt = (
        select(AgentLink)
        .where(AgentLink.team_id == team_id)
        .order_by(AgentLink.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_link(
    db: AsyncSession, team_id: uuid.UUID, data: AgentLinkCreate
) -> AgentLink:
    await _ensure_team_exists(db, team_id)
    await _ensure_agent_in_team(db, data.from_agent_id, team_id)
    await _ensure_agent_in_team(db, data.to_agent_id, team_id)

    link = AgentLink(
        team_id=team_id,
        from_agent_id=data.from_agent_id,
        to_agent_id=data.to_agent_id,
        link_type=data.link_type.value,
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateLinkError("This link already exists")
    await db.refresh(link)
    return link


async def delete_link(db: AsyncSession, link_id: uuid.UUID) -> None:
    stmt = select(AgentLink).where(AgentLink.id == link_id)
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise LinkNotFoundError(f"Link {link_id} not found")
    await db.delete(link)
    await db.commit()


async def get_agent_handoff_targets(
    db: AsyncSession, agent_id: uuid.UUID
) -> list[Agent]:
    """Return all agents this agent can hand off to (link_type='handoff')."""
    stmt = (
        select(Agent)
        .join(AgentLink, AgentLink.to_agent_id == Agent.id)
        .where(
            AgentLink.from_agent_id == agent_id,
            AgentLink.link_type == "handoff",
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _ensure_team_exists(db: AsyncSession, team_id: uuid.UUID) -> None:
    stmt = select(Team.id).where(Team.id == team_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise TeamNotFoundError(f"Team {team_id} not found")


async def _ensure_agent_in_team(
    db: AsyncSession, agent_id: uuid.UUID, team_id: uuid.UUID
) -> None:
    stmt = select(Agent.id).where(Agent.id == agent_id, Agent.team_id == team_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise AgentNotInTeamError(
            f"Agent {agent_id} does not belong to team {team_id}"
        )
