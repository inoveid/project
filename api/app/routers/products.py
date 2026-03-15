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


@router.get("/products/{product_id}/files")
async def list_product_files(
    product_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    from app.services.product_service import get_product_files
    return await get_product_files(db, product_id)


@router.get("/products/{product_id}/files/tree")
async def list_product_files_tree(
    product_id: uuid.UUID,
    path: str = "",
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import get_product_files_recursive
    return await get_product_files_recursive(db, product_id, path)


@router.get("/products/{product_id}/file")
async def read_file(
    product_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import read_product_file
    try:
        return await read_product_file(db, product_id, path)
    except FileNotFoundError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/products/{product_id}/file")
async def write_file(
    product_id: uuid.UUID,
    path: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import write_product_file
    try:
        content = body.get("content", "")
        return await write_product_file(db, product_id, path, content)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products/{product_id}/git/info")
async def git_info(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import get_product_git_info
    return await get_product_git_info(db, product_id)


@router.post("/products/{product_id}/git/checkout")
async def git_checkout(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import checkout_product_branch
    branch = body.get("branch", "")
    if not branch:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Branch name required")
    try:
        return await checkout_product_branch(db, product_id, branch)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products/{product_id}/git/diff")
async def git_diff(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import get_product_git_diff
    return await get_product_git_diff(db, product_id)


@router.get("/products/{product_id}/git/commits/{commit_hash}")
async def git_commit_detail(
    product_id: uuid.UUID,
    commit_hash: str,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import get_product_commit_detail
    try:
        return await get_product_commit_detail(db, product_id, commit_hash)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products/{product_id}/git/sync-status")
async def git_sync_status(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import get_sync_status
    return await get_sync_status(db, product_id)


@router.post("/products/{product_id}/git/push")
async def git_push(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import git_push as do_push
    try:
        return await do_push(db, product_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_id}/git/pull")
async def git_pull(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import git_pull as do_pull
    try:
        return await do_pull(db, product_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_id}/git/remote")
async def git_add_remote(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    from app.services.product_service import add_remote
    url = body.get("url", "")
    if not url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Remote URL required")
    try:
        return await add_remote(db, product_id, url)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
