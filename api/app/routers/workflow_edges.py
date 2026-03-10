import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.workflow_edge import (
    WorkflowEdgeCreate,
    WorkflowEdgeRead,
    WorkflowEdgeUpdate,
)
from app.services.workflow_edge_service import (
    EdgeNotFoundError,
    create_edge,
    delete_edge,
    get_edges,
    update_edge,
)
from app.services.workflow_service import AgentNotInTeamError, WorkflowNotFoundError

router = APIRouter()


@router.get(
    "/workflows/{workflow_id}/edges", response_model=list[WorkflowEdgeRead]
)
async def list_edges(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_edges(db, workflow_id)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/workflows/{workflow_id}/edges",
    response_model=WorkflowEdgeRead,
    status_code=201,
)
async def create_edge_endpoint(
    workflow_id: uuid.UUID,
    data: WorkflowEdgeCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_edge(db, workflow_id, data)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentNotInTeamError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/edges/{edge_id}", response_model=WorkflowEdgeRead)
async def update_edge_endpoint(
    edge_id: uuid.UUID,
    data: WorkflowEdgeUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_edge(db, edge_id, data)
    except EdgeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/edges/{edge_id}", status_code=204)
async def delete_edge_endpoint(
    edge_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await delete_edge(db, edge_id)
    except EdgeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
