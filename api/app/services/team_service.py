import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.team import Team
from app.schemas.team import TeamCreate, TeamUpdate


class TeamNotFoundError(Exception):
    pass


class TeamDuplicateNameError(Exception):
    pass


async def get_teams(db: AsyncSession) -> list[dict]:
    stmt = (
        select(Team, func.count(Agent.id).label("agents_count"))
        .outerjoin(Agent, Agent.team_id == Team.id)
        .group_by(Team.id)
        .order_by(Team.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {**_team_to_dict(team), "agents_count": count}
        for team, count in rows
    ]


async def get_team(db: AsyncSession, team_id: uuid.UUID) -> dict:
    stmt = (
        select(Team, func.count(Agent.id).label("agents_count"))
        .outerjoin(Agent, Agent.team_id == Team.id)
        .where(Team.id == team_id)
        .group_by(Team.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise TeamNotFoundError(f"Team {team_id} not found")
    team, count = row
    return {**_team_to_dict(team), "agents_count": count}


async def create_team(db: AsyncSession, data: TeamCreate) -> dict:
    team = Team(
        name=data.name,
        description=data.description,
        project_scoped=data.project_scoped,
    )
    db.add(team)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise TeamDuplicateNameError(f"Team with name '{data.name}' already exists")
    await db.refresh(team)
    return {**_team_to_dict(team), "agents_count": 0}


async def update_team(
    db: AsyncSession, team_id: uuid.UUID, data: TeamUpdate
) -> dict:
    stmt = select(Team).where(Team.id == team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    if team is None:
        raise TeamNotFoundError(f"Team {team_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise TeamDuplicateNameError(f"Team with name '{data.name}' already exists")
    await db.refresh(team)
    return await get_team(db, team_id)


async def delete_team(db: AsyncSession, team_id: uuid.UUID) -> None:
    stmt = select(Team).where(Team.id == team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    if team is None:
        raise TeamNotFoundError(f"Team {team_id} not found")
    await db.delete(team)
    await db.commit()


def _team_to_dict(team: Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "project_scoped": team.project_scoped,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
    }
