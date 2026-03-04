import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.team import Team
from app.schemas.agent import AgentCreate, AgentUpdate


class AgentNotFoundError(Exception):
    pass


class TeamNotFoundError(Exception):
    pass


class AgentDuplicateNameError(Exception):
    pass


async def get_agents(db: AsyncSession, team_id: uuid.UUID) -> list[Agent]:
    await _ensure_team_exists(db, team_id)
    stmt = (
        select(Agent)
        .where(Agent.team_id == team_id)
        .order_by(Agent.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent:
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")
    return agent


async def create_agent(
    db: AsyncSession, team_id: uuid.UUID, data: AgentCreate
) -> Agent:
    await _ensure_team_exists(db, team_id)
    agent = Agent(
        team_id=team_id,
        name=data.name,
        role=data.role,
        description=data.description,
        system_prompt=data.system_prompt,
        allowed_tools=data.allowed_tools,
        config=data.config,
    )
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AgentDuplicateNameError(
            f"Agent with name '{data.name}' already exists in this team"
        )
    await db.refresh(agent)
    return agent


async def update_agent(
    db: AsyncSession, agent_id: uuid.UUID, data: AgentUpdate
) -> Agent:
    agent = await get_agent(db, agent_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AgentDuplicateNameError(
            f"Agent with name '{data.name}' already exists in this team"
        )
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> None:
    agent = await get_agent(db, agent_id)
    await db.delete(agent)
    await db.commit()


async def _ensure_team_exists(db: AsyncSession, team_id: uuid.UUID) -> None:
    stmt = select(Team.id).where(Team.id == team_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise TeamNotFoundError(f"Team {team_id} not found")
