"""Tests for memory_service: _embed input_type parameter (BUG-2 fix)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_embed_uses_document_type_by_default():
    """_embed() defaults to input_type='document' for storing memories."""
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_result

    with patch("app.services.memory_service.voyageai") as mock_voyage:
        mock_voyage.Client.return_value = mock_client
        from app.services.memory_service import _embed

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
        from app.services.memory_service import _embed

        result = await _embed("search query", input_type="query")

    mock_client.embed.assert_called_once()
    call_kwargs = mock_client.embed.call_args
    assert call_kwargs[1]["input_type"] == "query"
    assert result == [0.4, 0.5, 0.6]
