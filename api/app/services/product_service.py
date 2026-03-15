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

def _git_auth_env() -> dict:
    """Return env with git credential helper using GITHUB_TOKEN."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {}
    env = os.environ.copy()
    env["GIT_ASKPASS"] = "/bin/echo"
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Use credential helper that returns the token
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "credential.helper"
    env["GIT_CONFIG_VALUE_0"] = f"!f() {{ echo username=x-access-token; echo password={token}; }}; f"
    return env




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
        from app.services.workspace_service import workspace_service
        await workspace_service.ensure_repo_initialized(workspace_path)

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
    from app.services.workspace_service import workspace_service as ws
    await ws.ensure_repo_initialized(base)

    async def run_git(args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    branch = await run_git(["branch", "--show-current"])

    # Fix detached HEAD (e.g. after shallow clone)
    if not branch:
        symbolic = await run_git(["branch", "-r", "--points-at", "HEAD", "--format=%(refname:short)"])
        target = "main"
        for ref in symbolic.splitlines():
            ref = ref.strip()
            if ref and not ref.endswith("/HEAD") and "/" in ref:
                target = ref.split("/", 1)[1]
                break
        fix_proc = await asyncio.create_subprocess_exec(
            "git", "checkout", "-B", target, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await fix_proc.communicate()
        # Set up tracking for the branch
        track_proc = await asyncio.create_subprocess_exec(
            "git", "branch", "--set-upstream-to", f"origin/{target}", target, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await track_proc.communicate()
        branch = target

    # Local branches
    local_raw = await run_git(["branch", "--format=%(refname:short)"])
    local_branches = [b.strip() for b in local_raw.splitlines() if b.strip()]

    # Remote branches (exclude those that already have a local counterpart)
    remote_raw = await run_git(["branch", "-r", "--format=%(refname:short)"])
    remote_branches = []
    for b in remote_raw.splitlines():
        b = b.strip()
        if not b or b.endswith("/HEAD") or "/" not in b:
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




def _parse_diff(raw_diff: str) -> list[dict]:
    """Parse unified diff into structured file list.
    
    Returns list of:
    {
        "path": "src/main.py",
        "old_path": "src/old_main.py" | None,  # for renames
        "status": "modified" | "added" | "deleted" | "renamed" | "binary",
        "additions": 5,
        "deletions": 2,
        "hunks": [
            {
                "header": "@@ -10,7 +10,8 @@ def foo():",
                "old_start": 10, "old_lines": 7,
                "new_start": 10, "new_lines": 8,
                "lines": [
                    {"type": "context", "content": " unchanged line", "old_no": 10, "new_no": 10},
                    {"type": "delete",  "content": "-removed line",   "old_no": 11, "new_no": None},
                    {"type": "add",     "content": "+added line",     "old_no": None, "new_no": 11},
                ]
            }
        ]
    }
    """
    import re
    files: list[dict] = []
    current_file: dict | None = None
    current_hunk: dict | None = None
    old_no = 0
    new_no = 0

    for line in raw_diff.splitlines():
        # New file diff header
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            m = re.match(r"diff --git a/(.*?) b/(.*)", line)
            old_path = m.group(1) if m else ""
            new_path = m.group(2) if m else ""
            current_file = {
                "path": new_path,
                "old_path": old_path if old_path != new_path else None,
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "hunks": [],
            }
            current_hunk = None
            continue

        if not current_file:
            continue

        # Binary file
        if line.startswith("Binary files") or line.startswith("GIT binary patch"):
            current_file["status"] = "binary"
            continue

        # New/deleted file markers
        if line.startswith("new file mode"):
            current_file["status"] = "added"
            continue
        if line.startswith("deleted file mode"):
            current_file["status"] = "deleted"
            continue
        if line.startswith("rename from"):
            current_file["status"] = "renamed"
            continue

        # Skip index/--- /+++ lines
        if line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
            continue

        # Hunk header
        hunk_match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line)
        if hunk_match:
            old_start = int(hunk_match.group(1))
            old_lines = int(hunk_match.group(2) or "1")
            new_start = int(hunk_match.group(3))
            new_lines = int(hunk_match.group(4) or "1")
            old_no = old_start
            new_no = new_start
            current_hunk = {
                "header": line,
                "old_start": old_start,
                "old_lines": old_lines,
                "new_start": new_start,
                "new_lines": new_lines,
                "lines": [],
            }
            current_file["hunks"].append(current_hunk)
            continue

        if not current_hunk:
            continue

        # Diff lines
        if line.startswith("+"):
            current_hunk["lines"].append({
                "type": "add", "content": line, "old_no": None, "new_no": new_no,
            })
            new_no += 1
            current_file["additions"] += 1
        elif line.startswith("-"):
            current_hunk["lines"].append({
                "type": "delete", "content": line, "old_no": old_no, "new_no": None,
            })
            old_no += 1
            current_file["deletions"] += 1
        else:
            current_hunk["lines"].append({
                "type": "context", "content": line, "old_no": old_no, "new_no": new_no,
            })
            old_no += 1
            new_no += 1

    if current_file:
        files.append(current_file)

    return files


async def get_sync_status(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Fetch from remote and return ahead/behind counts."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        return {"has_remote": False}

    async def run_git(args: list[str]) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return proc.returncode, stdout.decode().strip()

    # Check if remote exists
    rc, remote_out = await run_git(["remote"])
    if rc != 0 or not remote_out.strip():
        return {"has_remote": False}

    remote_name = remote_out.splitlines()[0].strip()
    _, remote_url = await run_git(["remote", "get-url", remote_name])

    # Unshallow if needed (shallow clones can't count ahead/behind)
    shallow_path = os.path.join(base, ".git", "shallow")
    if os.path.isfile(shallow_path):
        unshal_env = _git_auth_env()
        unshal = await asyncio.create_subprocess_exec(
            "git", "fetch", "--unshallow", remote_name, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            **({"env": unshal_env} if unshal_env else {}),
        )
        try:
            await asyncio.wait_for(unshal.communicate(), timeout=60)
        except asyncio.TimeoutError:
            pass

    # Fetch latest
    auth_env = _git_auth_env()
    fetch_proc = await asyncio.create_subprocess_exec(
        "git", "fetch", "--quiet", remote_name, cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        **({"env": auth_env} if auth_env else {}),
    )
    fetch_err = ""
    try:
        _, fetch_stderr = await asyncio.wait_for(fetch_proc.communicate(), timeout=30)
        if fetch_proc.returncode != 0:
            fetch_err = fetch_stderr.decode().strip()
            logger.warning("git fetch failed for product %s: %s", product_id, fetch_err)
    except asyncio.TimeoutError:
        fetch_err = "timeout"

    # Get current branch
    _, branch = await run_git(["branch", "--show-current"])
    if not branch:
        branch = "main"

    # Check if upstream is set
    rc_upstream, upstream = await run_git(["rev-parse", "--abbrev-ref", f"{branch}@{{u}}"])
    if rc_upstream != 0:
        # No upstream tracking — try to count via remote ref directly
        rc_remote_ref, _ = await run_git(["rev-parse", "--verify", f"{remote_name}/{branch}"])
        if rc_remote_ref == 0:
            # Remote branch exists but no tracking — count manually
            _, rev_list = await run_git(["rev-list", "--left-right", "--count", f"{branch}...{remote_name}/{branch}"])
            parts = rev_list.split()
            ahead = int(parts[0]) if len(parts) >= 1 else 0
            behind = int(parts[1]) if len(parts) >= 2 else 0
            return {
                "has_remote": True,
                "remote": remote_name,
                "remote_url": remote_url,
                "branch": branch,
                "upstream": None,
                "ahead": ahead,
                "behind": behind,
                "remote_branch_exists": True,
                "fetch_error": fetch_err or None,
            }
        return {
            "has_remote": True,
            "remote": remote_name,
            "remote_url": remote_url,
            "branch": branch,
            "upstream": None,
            "ahead": 0,
            "behind": 0,
            "remote_branch_exists": False,
            "fetch_error": fetch_err or None,
        }

    # Count ahead/behind
    _, rev_list = await run_git(["rev-list", "--left-right", "--count", f"{branch}...{upstream}"])
    parts = rev_list.split()
    ahead = int(parts[0]) if len(parts) >= 1 else 0
    behind = int(parts[1]) if len(parts) >= 2 else 0

    return {
        "has_remote": True,
        "remote": remote_name,
        "remote_url": remote_url,
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "remote_branch_exists": True,
        "fetch_error": fetch_err or None,
    }


async def git_push(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Push current branch to remote."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    auth_env = _git_auth_env()
    proc = await asyncio.create_subprocess_exec(
        "git", "push", "-u", "origin", "HEAD", cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        **({"env": auth_env} if auth_env else {}),
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise ValueError(f"Push failed: {err}")

    return {"ok": True, "message": stdout.decode().strip() + "\n" + stderr.decode().strip()}


async def git_pull(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Pull from remote for current branch."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    auth_env = _git_auth_env()
    proc = await asyncio.create_subprocess_exec(
        "git", "pull", "--ff-only", cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        **({"env": auth_env} if auth_env else {}),
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise ValueError(f"Pull failed: {err}")

    return {"ok": True, "message": stdout.decode().strip()}


async def add_remote(db: AsyncSession, product_id: uuid.UUID, url: str) -> dict:
    """Add or update remote origin."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    proc = await asyncio.create_subprocess_exec(
        "git", "remote", "add", "origin", url, cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        if "already exists" in err:
            proc2 = await asyncio.create_subprocess_exec(
                "git", "remote", "set-url", "origin", url, cwd=base,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc2.communicate()
        else:
            raise ValueError(f"Failed to add remote: {err}")

    return {"ok": True, "remote": "origin", "url": url}




async def create_branch(db: AsyncSession, product_id: uuid.UUID, branch_name: str, from_branch: str | None = None) -> dict:
    """Create a new branch and optionally switch to it."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    proc = await asyncio.create_subprocess_exec(
        "git", "checkout", "-b", branch_name,
        *([] if not from_branch else [from_branch]),
        cwd=base,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()

    if proc.returncode != 0:
        err = stderr_bytes.decode().strip()
        raise ValueError(f"Failed to create branch: {err}")

    return {"branch": branch_name}

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
    
    raw_diff = diff_stdout.decode() if proc2.returncode == 0 else ""
    parsed_files = _parse_diff(raw_diff)
    total_additions = sum(f["additions"] for f in parsed_files)
    total_deletions = sum(f["deletions"] for f in parsed_files)

    return {
        "hash": lines[0],
        "message": lines[1],
        "author": lines[2],
        "email": lines[3],
        "date": lines[4],
        "stats": "\n".join(lines[5:]).strip(),
        "diff": raw_diff,
        "files": parsed_files,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
    }


async def get_changed_files(db: AsyncSession, product_id: uuid.UUID) -> dict:
    """Get list of changed files with their diffs."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        return {"files": []}

    async def run_git(args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    # Get status — use -u to show individual files inside untracked dirs
    status_raw = await run_git(["status", "--porcelain", "-u"])
    if not status_raw:
        return {"files": []}

    files = []
    for line in status_raw.splitlines():
        if not line.strip():
            continue
        status_code = line[:2]
        file_path = line[3:].strip()
        # Determine status
        if status_code.startswith("?"):
            status = "untracked"
        elif status_code[0] == "A" or status_code[1] == "A":
            status = "added"
        elif status_code[0] == "D" or status_code[1] == "D":
            status = "deleted"
        elif status_code[0] == "M" or status_code[1] == "M":
            status = "modified"
        elif status_code[0] == "R":
            status = "renamed"
        else:
            status = "modified"
        files.append({"path": file_path, "status": status})

    # Get combined diff (staged + unstaged) for tracked files
    diff_raw = await run_git(["diff", "HEAD"])
    parsed = _parse_diff(diff_raw) if diff_raw else []

    # For untracked files — generate a synthetic diff (all lines as additions)
    for f in files:
        if f["status"] == "untracked":
            full_path = os.path.join(base, f["path"])
            try:
                file_content = open(full_path, "r", errors="replace").read()
                lines = file_content.splitlines()
                diff_lines = []
                for i, ln in enumerate(lines[:200]):
                    diff_lines.append({
                        "type": "add", "content": "+" + ln,
                        "old_no": None, "new_no": i + 1,
                    })
                parsed.append({
                    "path": f["path"],
                    "old_path": None,
                    "status": "added",
                    "additions": len(diff_lines),
                    "deletions": 0,
                    "hunks": [{
                        "header": f"@@ -0,0 +1,{len(diff_lines)} @@",
                        "old_start": 0, "old_lines": 0,
                        "new_start": 1, "new_lines": len(diff_lines),
                        "lines": diff_lines,
                    }],
                })
            except Exception:
                pass

    return {"files": files, "diff_files": parsed}


async def discard_file(db: AsyncSession, product_id: uuid.UUID, file_path: str) -> dict:
    """Discard changes for a specific file (git checkout / git clean)."""
    product = await get_product(db, product_id)
    base = product.workspace_path
    if not base or not _is_git_repo(base):
        raise ValueError("No git repository")

    # Security: prevent path traversal
    target = os.path.normpath(os.path.join(base, file_path))
    if not target.startswith(os.path.normpath(base)):
        raise ValueError("Invalid path")

    async def run_git(args: list[str]) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=base,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    # Check if file is untracked
    _, status_out, _ = await run_git(["status", "--porcelain", "--", file_path])
    if status_out.startswith("??"):
        # Untracked — remove it
        if os.path.isfile(target):
            os.remove(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)
    else:
        # Tracked — restore from HEAD
        await run_git(["checkout", "HEAD", "--", file_path])
        # Also unstage if staged
        await run_git(["reset", "HEAD", "--", file_path])

    return {"ok": True, "path": file_path}
