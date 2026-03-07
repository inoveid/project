import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.config import settings

router = APIRouter()

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")


class WorkspaceRead(BaseModel):
    name: str
    path: str


class WorkspaceCreate(BaseModel):
    name: str
    clone_url: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _SAFE_NAME.match(v):
            raise ValueError("name must contain only letters, digits, hyphens, underscores")
        return v


def _projects_root() -> Path:
    return Path(settings.workspace_path) / "projects"


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def list_workspaces() -> list[WorkspaceRead]:
    root = _projects_root()
    if not root.exists():
        return []
    return [
        WorkspaceRead(name=d.name, path=str(d))
        for d in sorted(root.iterdir())
        if d.is_dir() and not d.name.startswith(".") and (d / ".git").exists()
    ]


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
async def create_workspace(data: WorkspaceCreate) -> WorkspaceRead:
    root = _projects_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / data.name
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Workspace '{data.name}' already exists")

    if data.clone_url:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", data.clone_url, str(target),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            raise HTTPException(status_code=422, detail=stderr.decode().strip())
    else:
        target.mkdir(parents=True)
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(target), "init", "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            target.rmdir()
            raise HTTPException(status_code=500, detail=stderr.decode().strip())

    return WorkspaceRead(name=data.name, path=str(target))
