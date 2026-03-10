import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.workflow import WorkflowCreate, WorkflowRead, WorkflowUpdate
from app.services.workflow_service import (
    AgentNotInTeamError,
    DuplicateWorkflowError,
    TeamNotFoundError,
    WorkflowNotFoundError,
    create_workflow,
    delete_workflow,
    get_workflow,
    get_workflows,
    update_workflow,
)

router = APIRouter()


@router.get("/teams/{team_id}/workflows", response_model=list[WorkflowRead])
async def list_workflows(
    team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_workflows(db, team_id)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/teams/{team_id}/workflows", response_model=WorkflowRead, status_code=201
)
async def create_workflow_endpoint(
    team_id: uuid.UUID,
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_workflow(db, team_id, data)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentNotInTeamError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateWorkflowError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
async def get_workflow_endpoint(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_workflow(db, workflow_id)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/workflows/{workflow_id}", response_model=WorkflowRead)
async def update_workflow_endpoint(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_workflow(db, workflow_id, data)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentNotInTeamError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateWorkflowError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow_endpoint(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await delete_workflow(db, workflow_id)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
