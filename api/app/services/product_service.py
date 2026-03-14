import asyncio
import logging
import os
import shutil
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


logger = logging.getLogger(__name__)


def _is_git_repo(path: str) -> bool:
    """Check if path is a git repo (works for both regular repos and worktrees)."""
    git_path = os.path.join(path, ".git")
    return os.path.isdir(git_path) or os.path.isfile(git_path)


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

    # Auto-init git with initial commit so branches exist from the start
    if not data.git_url:
        import asyncio as _aio
        for cmd in [
            ['git', 'init', '-b', 'main'],
            ['git', 'config', 'user.email', 'agent@console.local'],
            ['git', 'config', 'user.name', 'Agent Console'],
            ['git', 'commit', '--allow-empty', '-m', 'Initial commit'],
        ]:
            p = await _aio.create_subprocess_exec(
                *cmd, cwd=workspace_path,
                stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE,
            )
            await p.communicate()

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
    if not base or not _is_git_repo(base):
        return {"initialized": False}

    # Auto-fix repos without initial commit (no branches)
    async def _ensure_initial_commit():
        proc = await asyncio.create_subprocess_exec(
            'git', 'branch', '--show-current', cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        if not out.decode().strip():
            # No branch = no commits yet, create initial commit
            for cmd in [
                ['git', 'config', 'user.email', 'agent@console.local'],
                ['git', 'config', 'user.name', 'Agent Console'],
                ['git', 'commit', '--allow-empty', '-m', 'Initial commit'],
            ]:
                p = await asyncio.create_subprocess_exec(
                    *cmd, cwd=base,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await p.communicate()

    await _ensure_initial_commit()

    async def run_git(args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    branch = await run_git(["branch", "--show-current"])
    # Local branches
    local_raw = await run_git(["branch", "--format=%(refname:short)"])
    local_branches = [b.strip() for b in local_raw.splitlines() if b.strip()]

    # Remote branches (exclude those that already have a local counterpart)
    remote_raw = await run_git(["branch", "-r", "--format=%(refname:short)"])
    remote_branches = []
    for b in remote_raw.splitlines():
        b = b.strip()
        if not b or b.endswith("/HEAD"):
            continue
        # Strip origin/ prefix for display
        short = b.split("/", 1)[1] if "/" in b else b
        if short not in local_branches:
            remote_branches.append(b)

    branches = local_branches + remote_branches

    # Filter out branches locked by worktrees (can't be checked out)
    worktree_raw = await run_git(["worktree", "list", "--porcelain"])
    locked_branches = set()
    for line in worktree_raw.splitlines():
        if line.startswith("branch refs/heads/"):
            locked_branches.add(line.replace("branch refs/heads/", "").strip())

    # Current branch is in a worktree too, but we still show it
    current = branch or "main"
    branches = [b for b in branches if b == current or b not in locked_branches]

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
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    async def run_git(args: list[str]) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    # Stash uncommitted changes if any
    rc, status, _ = await run_git(["status", "--porcelain"])
    has_changes = bool(status.strip())
    if has_changes:
        await run_git(["stash", "push", "-m", f"auto-stash before checkout {branch}"])

    # Try checkout
    if "/" in branch and branch.startswith("origin/"):
        local_name = branch.split("/", 1)[1]
        rc, _, checkout_err = await run_git(["checkout", "-b", local_name, branch])
        if rc != 0 and "already exists" in checkout_err:
            rc, _, checkout_err = await run_git(["checkout", local_name])
        branch = local_name
    else:
        rc, _, checkout_err = await run_git(["checkout", branch])

    # Restore stashed changes (regardless of checkout result)
    if has_changes:
        await run_git(["stash", "pop"])

    if rc != 0:
        logger.error("Git checkout failed for product %s: %s", product_id, checkout_err)
        raise ValueError(f"Checkout failed: {checkout_err}")

    return {"branch": branch}


async def get_product_git_diff(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Get git diff for product workspace."""
    import asyncio
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
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
    if not base or not _is_git_repo(base):
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
