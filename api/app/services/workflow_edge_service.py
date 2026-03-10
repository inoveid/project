import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.models.workflow_edge import WorkflowEdge
from app.schemas.workflow_edge import WorkflowEdgeCreate, WorkflowEdgeUpdate


class WorkflowNotFoundError(Exception):
    pass


class EdgeNotFoundError(Exception):
    pass


async def get_edges(
    db: AsyncSession, workflow_id: uuid.UUID
) -> list[WorkflowEdge]:
    await _ensure_workflow_exists(db, workflow_id)
    stmt = (
        select(WorkflowEdge)
        .where(WorkflowEdge.workflow_id == workflow_id)
        .order_by(WorkflowEdge.order, WorkflowEdge.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_edge(
    db: AsyncSession, workflow_id: uuid.UUID, data: WorkflowEdgeCreate
) -> WorkflowEdge:
    await _ensure_workflow_exists(db, workflow_id)

    edge = WorkflowEdge(
        workflow_id=workflow_id,
        from_agent_id=data.from_agent_id,
        to_agent_id=data.to_agent_id,
        condition=data.condition,
        prompt_template=data.prompt_template,
        prompt_id=data.prompt_id,
        order=data.order,
        requires_approval=data.requires_approval,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


async def update_edge(
    db: AsyncSession, edge_id: uuid.UUID, data: WorkflowEdgeUpdate
) -> WorkflowEdge:
    edge = await _get_edge(db, edge_id)
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(edge, field, value)

    await db.commit()
    await db.refresh(edge)
    return edge


async def delete_edge(db: AsyncSession, edge_id: uuid.UUID) -> None:
    edge = await _get_edge(db, edge_id)
    await db.delete(edge)
    await db.commit()


async def _get_edge(db: AsyncSession, edge_id: uuid.UUID) -> WorkflowEdge:
    stmt = select(WorkflowEdge).where(WorkflowEdge.id == edge_id)
    result = await db.execute(stmt)
    edge = result.scalar_one_or_none()
    if edge is None:
        raise EdgeNotFoundError(f"Edge {edge_id} not found")
    return edge


async def _ensure_workflow_exists(
    db: AsyncSession, workflow_id: uuid.UUID
) -> None:
    stmt = select(Workflow.id).where(Workflow.id == workflow_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")
