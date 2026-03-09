import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate
from app.services.business_service import (
    create_business,
    delete_business,
    get_business,
    get_businesses,
    update_business,
)

router = APIRouter()


@router.get("/businesses", response_model=list[BusinessRead])
async def list_businesses(db: AsyncSession = Depends(get_db)):
    return await get_businesses(db)


@router.post("/businesses", response_model=BusinessRead, status_code=201)
async def create_business_endpoint(
    data: BusinessCreate, db: AsyncSession = Depends(get_db)
):
    return await create_business(db, data)


@router.get("/businesses/{business_id}", response_model=BusinessRead)
async def get_business_endpoint(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_business(db, business_id)


@router.put("/businesses/{business_id}", response_model=BusinessRead)
async def update_business_endpoint(
    business_id: uuid.UUID,
    data: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_business(db, business_id, data)


@router.delete("/businesses/{business_id}", status_code=204)
async def delete_business_endpoint(
    business_id: uuid.UUID,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    await delete_business(db, business_id, force=force)
