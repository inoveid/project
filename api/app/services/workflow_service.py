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


async def get_active_tasks(
    db: AsyncSession, workflow_id: uuid.UUID
) -> list["Task"]:
    """Return tasks with status in_progress or awaiting_user for a workflow."""
    from app.models.task import Task  # lazy: avoid circular import

    await get_workflow(db, workflow_id)  # raises WorkflowNotFoundError if missing

    stmt = (
        select(Task)
        .where(
            Task.workflow_id == workflow_id,
            Task.status.in_(["in_progress", "awaiting_user"]),
        )
        .order_by(Task.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_locked_workflow_ids(
    db: AsyncSession, workflow_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Return the subset of workflow_ids that have active tasks (locked)."""
    from app.models.task import Task  # lazy: avoid circular import

    if not workflow_ids:
        return set()

    stmt = (
        select(Task.workflow_id)
        .where(
            Task.workflow_id.in_(workflow_ids),
            Task.status.in_(["in_progress", "awaiting_user"]),
        )
        .distinct()
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def validate_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> bool:
    """Check that starting_agent exists and workflow has at least one edge."""
    from app.models.workflow_edge import WorkflowEdge  # lazy: avoid circular import

    workflow = await get_workflow(db, workflow_id)

    agent_stmt = select(Agent.id).where(Agent.id == workflow.starting_agent_id)
    agent_result = await db.execute(agent_stmt)
    if agent_result.scalar_one_or_none() is None:
        return False

    edges_stmt = select(WorkflowEdge.id).where(
        WorkflowEdge.workflow_id == workflow_id
    ).limit(1)
    edges_result = await db.execute(edges_stmt)
    if edges_result.scalar_one_or_none() is None:
        return False

    return True


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
