import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.agent_link import AgentLinkCreate, AgentLinkRead
from app.services.agent_link_service import (
    AgentNotInTeamError,
    DuplicateLinkError,
    LinkNotFoundError,
    TeamNotFoundError,
    create_link,
    delete_link,
    get_links,
)

router = APIRouter()


@router.get("/teams/{team_id}/links", response_model=list[AgentLinkRead])
async def list_links(
    team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_links(db, team_id)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/teams/{team_id}/links", response_model=AgentLinkRead, status_code=201
)
async def create_link_endpoint(
    team_id: uuid.UUID,
    data: AgentLinkCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_link(db, team_id, data)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentNotInTeamError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateLinkError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/links/{link_id}", status_code=204)
async def delete_link_endpoint(
    link_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await delete_link(db, link_id)
    except LinkNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
