"""Retrieval precision metric: precision = |retrieved ∩ relevant| / |retrieved|.

See docs/phase5/eval_metrics.md for usage guide and curation process.
"""

from __future__ import annotations


def calculate_retrieval_precision(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
) -> float:
    """Return retrieval precision for one benchmark question.

    Args:
        retrieved_chunk_ids: ``Evidence.chunk_id`` strings from the agent
            response. Uses stable DB chunk identifiers, not per-run UUIDs.
        relevant_chunk_ids: Chunk IDs judged relevant for this question
            (from ``eval.metrics.relevance_judgments.RELEVANCE_JUDGMENTS``).

    Returns:
        Precision in ``[0.0, 1.0]``. Returns ``0.0`` for empty
        ``retrieved_chunk_ids`` or when no retrieved chunk is relevant.
    """
    if not retrieved_chunk_ids:
        return 0.0

    relevant_count = sum(1 for cid in retrieved_chunk_ids if cid in relevant_chunk_ids)
    return relevant_count / len(retrieved_chunk_ids)
