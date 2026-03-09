import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.product_service import (
    clone_product,
    create_product,
    delete_product,
    get_product,
    get_products,
    update_product,
)

router = APIRouter()


@router.get("/businesses/{business_id}/products", response_model=list[ProductRead])
async def list_products(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_products(db, business_id)


@router.post("/businesses/{business_id}/products", response_model=ProductRead, status_code=201)
async def create_product_endpoint(
    business_id: uuid.UUID,
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    merged = data.model_copy(update={"business_id": business_id})
    return await create_product(db, merged)


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product_endpoint(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await get_product(db, product_id)


@router.put("/products/{product_id}", response_model=ProductRead)
async def update_product_endpoint(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_product(db, product_id, data)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product_endpoint(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    await delete_product(db, product_id)


@router.post("/products/{product_id}/clone", response_model=ProductRead)
async def clone_product_endpoint(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    return await clone_product(db, product_id)
