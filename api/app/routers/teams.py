import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.services.team_service import (
    TeamDuplicateNameError,
    TeamNotFoundError,
    create_team,
    delete_team,
    get_team,
    get_teams,
    update_team,
)

router = APIRouter()


@router.get("", response_model=list[TeamRead])
async def list_teams(db: AsyncSession = Depends(get_db)):
    return await get_teams(db)


@router.post("", response_model=TeamRead, status_code=201)
async def create_team_endpoint(
    data: TeamCreate, db: AsyncSession = Depends(get_db)
):
    try:
        return await create_team(db, data)
    except TeamDuplicateNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{team_id}", response_model=TeamRead)
async def get_team_endpoint(
    team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_team(db, team_id)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team_endpoint(
    team_id: uuid.UUID, data: TeamUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        return await update_team(db, team_id, data)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TeamDuplicateNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{team_id}", status_code=204)
async def delete_team_endpoint(
    team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await delete_team(db, team_id)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
