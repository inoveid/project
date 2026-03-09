import shutil
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.product import Product
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate


async def _count_products(db: AsyncSession, business_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(Product.business_id == business_id)
    )
    return result.scalar_one()


async def _business_read(db: AsyncSession, business: Business) -> BusinessRead:
    count = await _count_products(db, business.id)
    data: dict[str, Any] = {
        "id": business.id,
        "name": business.name,
        "description": business.description,
        "created_at": business.created_at,
        "products_count": count,
    }
    return BusinessRead.model_validate(data)


async def create_business(db: AsyncSession, data: BusinessCreate) -> BusinessRead:
    business = Business(name=data.name, description=data.description)
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return await _business_read(db, business)


async def get_businesses(db: AsyncSession) -> list[BusinessRead]:
    result = await db.execute(select(Business).order_by(Business.created_at))
    businesses = result.scalars().all()
    return [await _business_read(db, b) for b in businesses]


async def get_business(db: AsyncSession, business_id: uuid.UUID) -> Business:
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def update_business(
    db: AsyncSession, business_id: uuid.UUID, data: BusinessUpdate
) -> BusinessRead:
    business = await get_business(db, business_id)
    if data.name is not None:
        business.name = data.name
    if data.description is not None:
        business.description = data.description
    await db.commit()
    await db.refresh(business)
    return await _business_read(db, business)


async def delete_business(
    db: AsyncSession, business_id: uuid.UUID, force: bool = False
) -> None:
    business = await get_business(db, business_id)
    products_count = await _count_products(db, business_id)

    if not force and products_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"products_count": products_count},
        )

    if force and products_count > 0:
        result = await db.execute(
            select(Product).where(Product.business_id == business_id)
        )
        products = result.scalars().all()
        for product in products:
            shutil.rmtree(product.workspace_path, ignore_errors=True)
            await db.delete(product)

    await db.delete(business)
    await db.commit()
