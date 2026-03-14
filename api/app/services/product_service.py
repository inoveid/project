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


async def get_product_files_recursive(db: AsyncSession, product_id: uuid.UUID, path: str = "") -> list[dict]:
    """Get files in a subdirectory of the product workspace."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not os.path.isdir(base):
        return []

    target = os.path.normpath(os.path.join(base, path)) if path else base
    # Security: prevent path traversal
    if not target.startswith(os.path.normpath(base)):
        return []
    if not os.path.isdir(target):
        return []

    items = []
    try:
        for entry in sorted(os.scandir(target), key=lambda e: (not e.is_dir(), e.name)):
            if entry.name.startswith("."):
                continue
            rel_path = os.path.relpath(entry.path, base)
            items.append({
                "name": entry.name,
                "path": rel_path,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
    except OSError:
        pass
    return items


async def read_product_file(db: AsyncSession, product_id: uuid.UUID, path: str) -> dict:
    """Read a file from product workspace."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base:
        raise ValueError("Product has no workspace")

    target = os.path.normpath(os.path.join(base, path))
    if not target.startswith(os.path.normpath(base)):
        raise ValueError("Invalid path")
    if not os.path.isfile(target):
        raise FileNotFoundError(f"File not found: {path}")

    content = open(target, "r", errors="replace").read()
    return {"path": path, "content": content, "size": len(content)}


async def write_product_file(db: AsyncSession, product_id: uuid.UUID, path: str, content: str) -> dict:
    """Write a file in product workspace."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base:
        raise ValueError("Product has no workspace")

    target = os.path.normpath(os.path.join(base, path))
    if not target.startswith(os.path.normpath(base)):
        raise ValueError("Invalid path")

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as f:
        f.write(content)

    return {"path": path, "size": len(content)}


async def get_product_git_info(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Get git info for product workspace."""
    import asyncio
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not os.path.isdir(os.path.join(base, ".git")):
        return {"initialized": False}

    async def run_git(args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    branch = await run_git(["branch", "--show-current"])
    branches_raw = await run_git(["branch", "-a", "--format=%(refname:short)"])
    branches = [b.strip() for b in branches_raw.splitlines() if b.strip()]

    log_raw = await run_git(["log", "--oneline", "-20", "--format=%H|%s|%an|%ar"])
    commits = []
    for line in log_raw.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0][:8], "message": parts[1], "author": parts[2], "date": parts[3]})

    status_raw = await run_git(["status", "--porcelain"])
    changed_files = len([l for l in status_raw.splitlines() if l.strip()])

    return {
        "initialized": True,
        "branch": branch or "main",
        "branches": branches,
        "commits": commits,
        "changed_files": changed_files,
    }


async def checkout_product_branch(db: AsyncSession, product_id: uuid.UUID, branch: str) -> dict:
    """Checkout a branch in product workspace."""
    import asyncio
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not os.path.isdir(os.path.join(base, ".git")):
        raise ValueError("No git repository")
    
    proc = await asyncio.create_subprocess_exec(
        "git", "checkout", branch, cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ValueError(f"Checkout failed: {stderr.decode().strip()}")
    
    return {"branch": branch}


async def get_product_git_diff(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Get git diff for product workspace."""
    import asyncio
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not os.path.isdir(os.path.join(base, ".git")):
        return {"diff": ""}
    
    proc = await asyncio.create_subprocess_exec(
        "git", "diff", cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return {"diff": stdout.decode()}


async def get_product_commit_detail(db: AsyncSession, product_id: uuid.UUID, commit_hash: str) -> dict:
    """Get details of a specific commit."""
    import asyncio
    import re
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not os.path.isdir(os.path.join(base, ".git")):
        raise ValueError("No git repository")
    
    # Validate hash format to prevent injection
    if not re.match(r'^[a-f0-9]{4,40}$', commit_hash):
        raise ValueError("Invalid commit hash")
    
    proc = await asyncio.create_subprocess_exec(
        "git", "show", "--stat", "--format=%H%n%s%n%an%n%ae%n%aI", commit_hash,
        cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ValueError(f"Commit not found: {stderr.decode().strip()}")
    
    lines = stdout.decode().splitlines()
    if len(lines) < 5:
        raise ValueError("Invalid commit data")
    
    # Get diff for this commit
    proc2 = await asyncio.create_subprocess_exec(
        "git", "diff", f"{commit_hash}~1", commit_hash, cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    diff_stdout, _ = await proc2.communicate()
    
    return {
        "hash": lines[0],
        "message": lines[1],
        "author": lines[2],
        "email": lines[3],
        "date": lines[4],
        "stats": "\n".join(lines[5:]).strip(),
        "diff": diff_stdout.decode() if proc2.returncode == 0 else "",
    }
