import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.team import Team
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


class TeamNotFoundError(Exception):
    pass


class WorkflowNotFoundError(Exception):
    pass


class DuplicateWorkflowError(Exception):
    pass


class AgentNotInTeamError(Exception):
    pass


async def get_workflows(db: AsyncSession, team_id: uuid.UUID) -> list[Workflow]:
    await _ensure_team_exists(db, team_id)
    stmt = (
        select(Workflow)
        .where(Workflow.team_id == team_id)
        .order_by(Workflow.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow:
    stmt = select(Workflow).where(Workflow.id == workflow_id)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")
    return workflow


async def create_workflow(
    db: AsyncSession, team_id: uuid.UUID, data: WorkflowCreate
) -> Workflow:
    await _ensure_team_exists(db, team_id)
    await _ensure_agent_in_team(db, data.starting_agent_id, team_id)

    workflow = Workflow(
        team_id=team_id,
        name=data.name,
        description=data.description,
        starting_agent_id=data.starting_agent_id,
        starting_prompt=data.starting_prompt,
    )
    db.add(workflow)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateWorkflowError(
            f"Workflow with name '{data.name}' already exists in this team"
        )
    await db.refresh(workflow)
    return workflow


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, data: WorkflowUpdate
) -> Workflow:
    workflow = await get_workflow(db, workflow_id)
    update_data = data.model_dump(exclude_unset=True)

    if "starting_agent_id" in update_data:
        await _ensure_agent_in_team(
            db, update_data["starting_agent_id"], workflow.team_id
        )

    for field, value in update_data.items():
        setattr(workflow, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DuplicateWorkflowError(
            f"Workflow with name '{data.name}' already exists in this team"
        )
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> None:
    workflow = await get_workflow(db, workflow_id)
    await db.delete(workflow)
    await db.commit()


async def validate_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> bool:
    workflow = await get_workflow(db, workflow_id)
    return bool(workflow.starting_agent_id and workflow.starting_prompt)


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
