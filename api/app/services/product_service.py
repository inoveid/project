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


async def _do_clone(product_id: uuid.UUID) -> None:
    """Фоновая задача: выполняет git clone и обновляет статус в своей сессии."""
    from app.database import async_session

    async with async_session() as db:
        product = await get_product(db, product_id)
        if not product.git_url:
            product.status = "error"
            product.clone_error = "git_url is missing"
            await db.commit()
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", product.git_url, product.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
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
                proc.kill()
                await proc.communicate()
                product.status = "error"
                product.clone_error = "Clone timed out"
        except Exception as e:
            product.status = "error"
            product.clone_error = str(e)
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
    await db.refresh(product)

    asyncio.create_task(_do_clone(product.id))
    return product


async def get_product_files(
    db: AsyncSession, product_id: uuid.UUID, max_items: int = 50
) -> list[dict]:
    """Return top-level entries of the product workspace."""
    product = await get_product(db, product_id)
    workspace = product.workspace_path

    if not os.path.isdir(workspace):
        return []

    entries: list[dict] = []
    try:
        for name in sorted(os.listdir(workspace)):
            if name.startswith("."):
                continue
            full = os.path.join(workspace, name)
            is_dir = os.path.isdir(full)
            size = 0 if is_dir else os.path.getsize(full)
            entries.append({"name": name, "type": "dir" if is_dir else "file", "size": size})
            if len(entries) >= max_items:
                break
    except OSError:
        pass

    return entries
