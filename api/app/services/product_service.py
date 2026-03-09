import asyncio
import os
import shutil
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    product_id = uuid.uuid4()
    workspace_path = os.path.join(settings.workspace_path, "products", str(product_id))
    os.makedirs(workspace_path, exist_ok=True)

    product = Product(
        id=product_id,
        business_id=data.business_id,
        name=data.name,
        description=data.description,
        git_url=data.git_url,
        workspace_path=workspace_path,
        status="pending",
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_products(db: AsyncSession, business_id: uuid.UUID) -> list[Product]:
    result = await db.execute(
        select(Product).where(Product.business_id == business_id).order_by(Product.created_at)
    )
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def update_product(
    db: AsyncSession, product_id: uuid.UUID, data: ProductUpdate
) -> Product:
    product = await get_product(db, product_id)
    if data.name is not None:
        product.name = data.name
    if data.description is not None:
        product.description = data.description
    if data.git_url is not None:
        product.git_url = data.git_url
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: uuid.UUID) -> None:
    product = await get_product(db, product_id)
    shutil.rmtree(product.workspace_path, ignore_errors=True)
    await db.delete(product)
    await db.commit()


async def clone_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await get_product(db, product_id)

    if not product.git_url:
        raise HTTPException(status_code=400, detail="Product has no git_url")

    if product.status == "cloning":
        raise HTTPException(status_code=409, detail="Product is already being cloned")

    if product.status == "error":
        shutil.rmtree(product.workspace_path, ignore_errors=True)
        os.makedirs(product.workspace_path, exist_ok=True)

    product.status = "cloning"
    product.clone_error = None
    await db.commit()

    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", product.git_url, product.workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.clone_timeout_seconds,
        )
        if proc.returncode != 0:
            product.status = "error"
            product.clone_error = stderr_bytes.decode().strip()
        else:
            product.status = "ready"
            product.clone_error = None
    except asyncio.TimeoutError:
        product.status = "error"
        product.clone_error = "Clone timed out"

    await db.commit()
    await db.refresh(product)
    return product
