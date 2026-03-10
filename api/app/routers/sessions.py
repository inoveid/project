import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.session import SessionCreate, SessionListItem, SessionRead
from app.services.runtime import runtime
from app.services.session_service import (
    AgentNotFoundError,
    SessionNotFoundError,
    create_session,
    get_session,
    get_sessions,
    stop_session,
)

router = APIRouter()


@router.post("", response_model=SessionRead, status_code=201)
async def create_session_endpoint(
    data: SessionCreate, db: AsyncSession = Depends(get_db)
):
    try:
        return await create_session(db, data)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    task_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await get_sessions(db, task_id=task_id)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session_endpoint(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_session(db, session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{session_id}", status_code=204)
async def delete_session_endpoint(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await runtime.stop_session(session_id)
        await stop_session(db, session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
