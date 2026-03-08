import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import memory_service

router = APIRouter()

MemoryKind = Literal["adr", "convention", "pattern"]


# ── Request / Response schemas ────────────────────────────────────────────────

class SaveEpisodicRequest(BaseModel):
    team_id: uuid.UUID
    task_id: str | None = None
    summary: str
    outcome: str
    tags: list[str] = []


class SaveSemanticRequest(BaseModel):
    team_id: uuid.UUID
    kind: MemoryKind
    title: str
    content: str
    tags: list[str] = []


class SearchRequest(BaseModel):
    team_id: uuid.UUID
    query: str
    top_k: int = 5
    memory_types: list[str] | None = None


class SearchResultItem(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    tags: list[str]
    similarity: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/memory/episodic", status_code=201)
async def save_episodic(body: SaveEpisodicRequest, db: AsyncSession = Depends(get_db)):
    """Сохранить воспоминание о выполненной задаче."""
    memory = await memory_service.save_episodic(
        db,
        team_id=body.team_id,
        summary=body.summary,
        outcome=body.outcome,
        task_id=body.task_id,
        tags=body.tags,
    )
    return {"id": str(memory.id), "created_at": memory.created_at}


@router.post("/memory/semantic", status_code=201)
async def save_semantic(body: SaveSemanticRequest, db: AsyncSession = Depends(get_db)):
    """Сохранить архитектурное решение / конвенцию / паттерн."""
    memory = await memory_service.save_semantic(
        db,
        team_id=body.team_id,
        kind=body.kind,
        title=body.title,
        content=body.content,
        tags=body.tags,
    )
    return {"id": str(memory.id), "created_at": memory.created_at}


@router.post("/memory/search", response_model=list[SearchResultItem])
async def search_memories(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    """
    RAG-as-Tool: семантический поиск по памяти команды.

    Агент вызывает этот endpoint когда нужно найти релевантный контекст.
    Возвращает топ-N результатов по убыванию similarity (0..1).
    """
    results = await memory_service.search_memories(
        db,
        team_id=body.team_id,
        query=body.query,
        top_k=body.top_k,
        memory_types=body.memory_types,
    )
    return [
        SearchResultItem(
            id=r.id,
            kind=r.kind,
            title=r.title,
            content=r.content,
            tags=r.tags,
            similarity=r.similarity,
        )
        for r in results
    ]
