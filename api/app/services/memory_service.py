"""
Memory service: сохранение и поиск воспоминаний агентов.

Два типа памяти:
- EpisodicMemory — история задач (что делали, что получилось)
- SemanticMemory — архитектурные решения, конвенции, паттерны

RAG-as-Tool: агент вызывает search_memories() когда нужно — не каждый запрос.
"""
import asyncio
import uuid
from dataclasses import dataclass

import voyageai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import EpisodicMemory, SemanticMemory

EMBEDDING_MODEL = "voyage-3-lite"
EMBEDDING_DIM = 512  # voyage-3-lite output dimension
DEFAULT_TOP_K = 5


@dataclass
class MemorySearchResult:
    id: str
    kind: str          # "episodic" | "adr" | "convention" | "pattern"
    title: str
    content: str
    tags: list[str]
    similarity: float  # 0..1, 1 = идентично


async def _embed(text_input: str) -> list[float]:
    """Получить embedding через Voyage AI voyage-3-lite."""
    client = voyageai.Client(api_key=settings.voyage_api_key)
    # voyageai SDK синхронный — запускаем в thread pool чтобы не блокировать event loop
    result = await asyncio.to_thread(
        client.embed, [text_input], model=EMBEDDING_MODEL, input_type="document"
    )
    return result.embeddings[0]


# ── Episodic memory ──────────────────────────────────────────────────────────

async def save_episodic(
    db: AsyncSession,
    team_id: uuid.UUID,
    summary: str,
    outcome: str,
    task_id: str | None = None,
    tags: list[str] | None = None,
) -> EpisodicMemory:
    """Сохранить воспоминание о выполненной задаче."""
    # Embed: summary + outcome вместе дают лучший контекст для поиска
    embed_text = f"{summary}\n\n{outcome}"
    embedding = await _embed(embed_text)

    memory = EpisodicMemory(
        team_id=team_id,
        task_id=task_id,
        summary=summary,
        outcome=outcome,
        tags=tags or [],
        embedding=embedding,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


# ── Semantic memory ──────────────────────────────────────────────────────────

async def save_semantic(
    db: AsyncSession,
    team_id: uuid.UUID,
    kind: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
) -> SemanticMemory:
    """Сохранить архитектурное решение / конвенцию / паттерн."""
    embed_text = f"{title}\n\n{content}"
    embedding = await _embed(embed_text)

    memory = SemanticMemory(
        team_id=team_id,
        kind=kind,
        title=title,
        content=content,
        tags=tags or [],
        embedding=embedding,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


# ── Search (RAG-as-Tool) ─────────────────────────────────────────────────────

async def search_memories(
    db: AsyncSession,
    team_id: uuid.UUID,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    memory_types: list[str] | None = None,
) -> list[MemorySearchResult]:
    """
    Семантический поиск по всей памяти команды.

    memory_types — фильтр: ["episodic", "adr", "convention", "pattern"].
    Если None — ищем везде.

    Возвращает результаты отсортированные по убыванию сходства.
    """
    query_embedding = await _embed(query)
    results: list[MemorySearchResult] = []

    if memory_types is None or "episodic" in memory_types:
        episodic_results = await _search_episodic(db, team_id, query_embedding, top_k)
        results.extend(episodic_results)

    semantic_kinds = [t for t in (memory_types or ["adr", "convention", "pattern"])
                      if t in ("adr", "convention", "pattern")]
    if semantic_kinds:
        semantic_results = await _search_semantic(db, team_id, query_embedding, top_k, semantic_kinds)
        results.extend(semantic_results)

    # Объединяем и берём top_k по убыванию similarity
    results.sort(key=lambda r: r.similarity, reverse=True)
    return results[:top_k]


async def _search_episodic(
    db: AsyncSession,
    team_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
) -> list[MemorySearchResult]:
    # pgvector: <=> — cosine distance (0 = идентично, 2 = противоположно)
    # similarity = 1 - cosine_distance
    stmt = (
        select(
            EpisodicMemory,
            (1 - EpisodicMemory.embedding.cosine_distance(query_embedding)).label("similarity"),
        )
        .where(EpisodicMemory.team_id == team_id)
        .order_by(text("similarity DESC"))
        .limit(top_k)
    )
    rows = await db.execute(stmt)

    return [
        MemorySearchResult(
            id=str(row.EpisodicMemory.id),
            kind="episodic",
            title=row.EpisodicMemory.summary,
            content=row.EpisodicMemory.outcome,
            tags=row.EpisodicMemory.tags,
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def _search_semantic(
    db: AsyncSession,
    team_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
    kinds: list[str],
) -> list[MemorySearchResult]:
    stmt = (
        select(
            SemanticMemory,
            (1 - SemanticMemory.embedding.cosine_distance(query_embedding)).label("similarity"),
        )
        .where(SemanticMemory.team_id == team_id)
        .where(SemanticMemory.kind.in_(kinds))
        .order_by(text("similarity DESC"))
        .limit(top_k)
    )
    rows = await db.execute(stmt)

    return [
        MemorySearchResult(
            id=str(row.SemanticMemory.id),
            kind=row.SemanticMemory.kind,
            title=row.SemanticMemory.title,
            content=row.SemanticMemory.content,
            tags=row.SemanticMemory.tags,
            similarity=float(row.similarity),
        )
        for row in rows
    ]
