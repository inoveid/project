"""Tests for memory_service: _embed, save_episodic, save_semantic, search_memories."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_service import (
    MemorySearchResult,
    _embed,
    save_episodic,
    save_semantic,
    search_memories,
)


FAKE_EMBEDDING = [0.1] * 512
FAKE_TEAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_embed_uses_document_type_by_default():
    """_embed() defaults to input_type='document' for storing memories."""
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_result

    with patch("app.services.memory_service.voyageai") as mock_voyage:
        mock_voyage.Client.return_value = mock_client
        result = await _embed("test document")

    mock_client.embed.assert_called_once()
    call_kwargs = mock_client.embed.call_args
    assert call_kwargs[1]["input_type"] == "document"
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_uses_query_type_when_specified():
    """_embed() uses input_type='query' when explicitly passed."""
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.embeddings = [[0.4, 0.5, 0.6]]
    mock_client.embed.return_value = mock_result

    with patch("app.services.memory_service.voyageai") as mock_voyage:
        mock_voyage.Client.return_value = mock_client
        result = await _embed("search query", input_type="query")

    mock_client.embed.assert_called_once()
    call_kwargs = mock_client.embed.call_args
    assert call_kwargs[1]["input_type"] == "query"
    assert result == [0.4, 0.5, 0.6]


def _make_mock_db() -> MagicMock:
    """Create a mock DB session with async commit/refresh."""
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


@pytest.mark.asyncio
async def test_save_episodic_creates_record():
    """save_episodic creates EpisodicMemory, calls db.add/commit/refresh."""
    mock_db = _make_mock_db()

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING) as mock_embed:
        result = await save_episodic(
            db=mock_db,
            team_id=FAKE_TEAM_ID,
            summary="Fixed the auth bug",
            outcome="Tests pass, no regressions",
            task_id="TASK-001",
            tags=["bugfix", "auth"],
        )

    mock_embed.assert_awaited_once_with("Fixed the auth bug\n\nTests pass, no regressions")
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()
    assert result.summary == "Fixed the auth bug"
    assert result.outcome == "Tests pass, no regressions"
    assert result.tags == ["bugfix", "auth"]
    assert result.embedding == FAKE_EMBEDDING


@pytest.mark.asyncio
async def test_save_semantic_creates_record():
    """save_semantic creates SemanticMemory, calls db.add/commit/refresh."""
    mock_db = _make_mock_db()

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING) as mock_embed:
        result = await save_semantic(
            db=mock_db,
            team_id=FAKE_TEAM_ID,
            kind="adr",
            title="Use FastAPI for backend",
            content="Chosen for async support and auto-generated docs.",
            tags=["architecture", "backend"],
        )

    mock_embed.assert_awaited_once_with("Use FastAPI for backend\n\nChosen for async support and auto-generated docs.")
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()
    assert result.kind == "adr"
    assert result.title == "Use FastAPI for backend"
    assert result.tags == ["architecture", "backend"]
    assert result.embedding == FAKE_EMBEDDING


@pytest.mark.asyncio
async def test_search_memories_merges_results():
    """search_memories merges episodic + semantic results and sorts by similarity."""
    mock_db = _make_mock_db()
    episodic = [
        MemorySearchResult(id="e1", kind="episodic", title="T1", content="C1", tags=[], similarity=0.7),
    ]
    semantic = [
        MemorySearchResult(id="s1", kind="adr", title="T2", content="C2", tags=[], similarity=0.9),
        MemorySearchResult(id="s2", kind="convention", title="T3", content="C3", tags=[], similarity=0.5),
    ]

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING), \
         patch("app.services.memory_service._search_episodic", return_value=episodic), \
         patch("app.services.memory_service._search_semantic", return_value=semantic):
        results = await search_memories(db=mock_db, team_id=FAKE_TEAM_ID, query="test query")

    assert len(results) == 3
    assert results[0].similarity == 0.9
    assert results[1].similarity == 0.7
    assert results[2].similarity == 0.5


@pytest.mark.asyncio
async def test_search_memories_uses_query_input_type():
    """search_memories calls _embed with input_type='query'."""
    mock_db = _make_mock_db()

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING) as mock_embed, \
         patch("app.services.memory_service._search_episodic", return_value=[]), \
         patch("app.services.memory_service._search_semantic", return_value=[]):
        await search_memories(db=mock_db, team_id=FAKE_TEAM_ID, query="my query")

    mock_embed.assert_awaited_once_with("my query", input_type="query")


@pytest.mark.asyncio
async def test_search_memories_empty_results():
    """search_memories returns empty list when no memories exist."""
    mock_db = _make_mock_db()

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING), \
         patch("app.services.memory_service._search_episodic", return_value=[]), \
         patch("app.services.memory_service._search_semantic", return_value=[]):
        results = await search_memories(db=mock_db, team_id=FAKE_TEAM_ID, query="anything")

    assert results == []


@pytest.mark.asyncio
async def test_search_memories_respects_limit():
    """search_memories returns at most top_k results."""
    mock_db = _make_mock_db()
    many_results = [
        MemorySearchResult(id=f"e{i}", kind="episodic", title=f"T{i}", content="C", tags=[], similarity=float(i) / 10)
        for i in range(10)
    ]

    with patch("app.services.memory_service._embed", return_value=FAKE_EMBEDDING), \
         patch("app.services.memory_service._search_episodic", return_value=many_results), \
         patch("app.services.memory_service._search_semantic", return_value=[]):
        results = await search_memories(db=mock_db, team_id=FAKE_TEAM_ID, query="q", top_k=3)

    assert len(results) == 3
    # Should be top 3 by similarity (highest first)
    assert results[0].similarity >= results[1].similarity >= results[2].similarity
