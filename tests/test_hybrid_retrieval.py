"""Unit tests for Literature RAG hybrid retrieval and RankFusion scoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from db.models.literature_chunk import LiteratureChunk
from db.repository import LiteratureRepository


class TestRankFusion:
    """Verifies reciprocal rank fusion and score normalization mathematics."""

    @pytest.mark.asyncio
    async def test_rrf_and_normalization_logic(self) -> None:
        # Mock literature chunks
        chunk_a = LiteratureChunk(
            id="00000000-0000-0000-0000-00000000000a",
            document_id="doc_1",
            chunk_text="Text block A",
            source_url="http://url1.com",
            extra_metadata={"title": "Paper Title A", "chunk_id": 1},
        )
        chunk_b = LiteratureChunk(
            id="00000000-0000-0000-0000-00000000000b",
            document_id="doc_2",
            chunk_text="Text block B",
            source_url="http://url2.com",
            extra_metadata={"title": "Paper Title B", "chunk_id": 2},
        )
        chunk_c = LiteratureChunk(
            id="00000000-0000-0000-0000-00000000000c",
            document_id="doc_3",
            chunk_text="Text block C",
            source_url="http://url3.com",
            extra_metadata={"title": "Paper Title C", "chunk_id": 3},
        )

        # 1. Vector returns [A, B] (Rank 1 = A, Rank 2 = B)
        # 2. FTS returns [B, C] (Rank 1 = B, Rank 2 = C)
        # RRF score for A: 1/(60+1) + 0 = 1/61 ~ 0.01639
        # RRF score for B: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ~ 0.03252
        # RRF score for C: 0 + 1/(60+2) = 1/62 ~ 0.01612
        # Highest potential score (rank 1 in both): 2 / 61 ~ 0.03278
        #
        # Normalized B: ~0.03252 / 0.03278 ~ 0.99
        # Normalized A: ~0.01639 / 0.03278 ~ 0.50
        # Normalized C: ~0.01612 / 0.03278 ~ 0.49

        # Mock database session execution
        session = MagicMock()

        # We need mock result scalars
        mock_vec_scalars = MagicMock()
        mock_vec_scalars.all.return_value = [chunk_a, chunk_b]
        mock_vec_result = MagicMock()
        mock_vec_result.scalars.return_value = mock_vec_scalars

        mock_fts_scalars = MagicMock()
        mock_fts_scalars.all.return_value = [chunk_b, chunk_c]
        mock_fts_result = MagicMock()
        mock_fts_result.scalars.return_value = mock_fts_scalars

        # Async execution mock
        session.execute = AsyncMock()
        session.execute.side_effect = [mock_vec_result, mock_fts_result]

        # Execute hybrid search
        results = await LiteratureRepository.hybrid_search(
            session=session,
            query="test query",
            query_embedding=[0.1] * 1536,
            k=3,
        )

        # Assert correct ordering (B should be first, then A, then C)
        assert len(results) == 3
        assert results[0].document_id == "doc_2"
        assert results[1].document_id == "doc_1"
        assert results[2].document_id == "doc_3"

        # Assert score normalization (Confidence in 0-1 range)
        assert 0.98 <= results[0].confidence <= 1.0
        assert 0.49 <= results[1].confidence <= 0.51
        assert 0.48 <= results[2].confidence <= 0.50

        # Assert rich citation metadata was preserved
        assert results[0].chunk_id == 2
        assert results[0].title == "Paper Title B"
        assert results[0].source_url == "http://url2.com"

    @pytest.mark.asyncio
    async def test_hybrid_search_empty_corpus(self) -> None:
        """Verify that an empty corpus returns an empty list without raising exceptions."""
        session = MagicMock()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        session.execute = AsyncMock()
        session.execute.side_effect = [mock_result, mock_result]

        results = await LiteratureRepository.hybrid_search(
            session=session,
            query="unmatched query",
            query_embedding=[0.0] * 1536,
            k=5,
        )
        assert results == []
