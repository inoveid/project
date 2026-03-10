import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate, TaskUpdate
from app.services.task_service import (
    create_task,
    delete_task,
    get_task,
    get_tasks,
    update_task,
    update_task_status,
)

router = APIRouter()


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    product_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await get_tasks(db, product_id)


@router.post("/tasks", response_model=TaskRead, status_code=201)
async def create_task_endpoint(
    data: TaskCreate, db: AsyncSession = Depends(get_db)
):
    return await create_task(db, data)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task_endpoint(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_task(db, task_id)


@router.put("/tasks/{task_id}", response_model=TaskRead)
async def update_task_endpoint(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_task(db, task_id, data)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task_endpoint(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    await delete_task(db, task_id)


@router.patch("/tasks/{task_id}/status", response_model=TaskRead)
async def update_task_status_endpoint(
    task_id: uuid.UUID,
    data: TaskStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_task_status(db, task_id, data.status)
