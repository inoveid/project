import shutil
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.product import Product
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate


def _products_count_subquery():
    return (
        select(func.count())
        .where(Product.business_id == Business.id)
        .correlate(Business)
        .scalar_subquery()
    )


async def get_businesses(db: AsyncSession) -> list[BusinessRead]:
    subq = _products_count_subquery()
    result = await db.execute(
        select(Business, subq.label("products_count")).order_by(Business.created_at)
    )
    rows = result.all()
    return [
        BusinessRead(
            id=b.id,
            name=b.name,
            description=b.description,
            created_at=b.created_at,
            products_count=count,
        )
        for b, count in rows
    ]


async def _get_business_model(db: AsyncSession, business_id: uuid.UUID) -> Business:
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def _count_products(db: AsyncSession, business_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(Product.business_id == business_id)
    )
    return result.scalar_one()


async def get_business(db: AsyncSession, business_id: uuid.UUID) -> BusinessRead:
    business = await _get_business_model(db, business_id)
    count = await _count_products(db, business.id)
    return BusinessRead(
        id=business.id,
        name=business.name,
        description=business.description,
        created_at=business.created_at,
        products_count=count,
    )


async def create_business(db: AsyncSession, data: BusinessCreate) -> BusinessRead:
    business = Business(name=data.name, description=data.description)
    db.add(business)
    await db.commit()
    await db.refresh(business)
    count = await _count_products(db, business.id)
    return BusinessRead(
        id=business.id,
        name=business.name,
        description=business.description,
        created_at=business.created_at,
        products_count=count,
    )


async def update_business(
    db: AsyncSession, business_id: uuid.UUID, data: BusinessUpdate
) -> BusinessRead:
    business = await _get_business_model(db, business_id)
    if data.name is not None:
        business.name = data.name
    if data.description is not None:
        business.description = data.description
    await db.commit()
    await db.refresh(business)
    count = await _count_products(db, business.id)
    return BusinessRead(
        id=business.id,
        name=business.name,
        description=business.description,
        created_at=business.created_at,
        products_count=count,
    )


async def delete_business(
    db: AsyncSession, business_id: uuid.UUID, force: bool = False
) -> None:
    business = await _get_business_model(db, business_id)
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
