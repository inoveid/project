import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.agent_service import (
    AgentDuplicateNameError,
    AgentNotFoundError,
    TeamNotFoundError,
    can_delete_agent,
    create_agent,
    delete_agent,
    get_agent,
    get_agents,
    get_all_agents,
    update_agent,
)
from app.services.system_agent_service import seed_system_agent

router = APIRouter()


@router.get("/agents", response_model=list[AgentRead])
async def list_all_agents(db: AsyncSession = Depends(get_db)):
    return await get_all_agents(db)


@router.get("/agents/system", response_model=AgentRead)
async def get_system_agent(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.is_system == True))
    agent = result.scalar_one_or_none()
    if not agent:
        agent = await seed_system_agent(db)
    return agent


@router.get("/teams/{team_id}/agents", response_model=list[AgentRead])
async def list_agents(
    team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_agents(db, team_id)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/teams/{team_id}/agents", response_model=AgentRead, status_code=201
)
async def create_agent_endpoint(
    team_id: uuid.UUID,
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_agent(db, team_id, data)
    except TeamNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentDuplicateNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/agents/{agent_id}/can-delete")
async def check_agent_deletable(
    agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        can_delete, reason = await can_delete_agent(db, agent_id)
        return {"can_delete": can_delete, "reason": reason}
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_agent_endpoint(
    agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        return await get_agent(db, agent_id)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def update_agent_endpoint(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_agent(db, agent_id, data)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentDuplicateNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent_endpoint(
    agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    try:
        await delete_agent(db, agent_id)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
