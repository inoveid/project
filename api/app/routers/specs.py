import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.spec import SpecCreate, SpecRead, SpecUpdate, SpecVersionRead
from app.services.spec_service import (
    create_spec,
    delete_spec,
    get_spec,
    get_spec_versions,
    get_specs,
    rollback_spec,
    update_spec,
)

router = APIRouter()


@router.get("/products/{product_id}/specs", response_model=list[SpecRead])
async def list_specs(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_specs(db, product_id)


@router.post("/products/{product_id}/specs", response_model=SpecRead, status_code=201)
async def create_spec_endpoint(
    product_id: uuid.UUID,
    data: SpecCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_spec(db, product_id, data)


@router.get("/specs/{spec_id}", response_model=SpecRead)
async def get_spec_endpoint(
    spec_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_spec(db, spec_id)


@router.patch("/specs/{spec_id}", response_model=SpecRead)
async def update_spec_endpoint(
    spec_id: uuid.UUID,
    data: SpecUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_spec(db, spec_id, data)


@router.delete("/specs/{spec_id}", status_code=204)
async def delete_spec_endpoint(
    spec_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    await delete_spec(db, spec_id)


@router.get("/specs/{spec_id}/versions", response_model=list[SpecVersionRead])
async def list_spec_versions(
    spec_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_spec_versions(db, spec_id)


@router.post("/specs/{spec_id}/versions/{version}/rollback", response_model=SpecRead)
async def rollback_spec_endpoint(
    spec_id: uuid.UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
):
    return await rollback_spec(db, spec_id, version)
