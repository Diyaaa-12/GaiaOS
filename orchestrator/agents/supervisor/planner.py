"""Adaptive Planner and Complexity Classifier logic."""

from __future__ import annotations

from logging_config import get_logger
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.schemas.complexity import ComplexityTier

_log = get_logger(__name__)


async def classify_query(query: str) -> ComplexityTier:
    """Analyze query complexity and target domain scopes.

    Routes queries to TRIVIAL, MODERATE, or COMPLEX based on keywords and domains.
    If classification fails, defaults to MODERATE to fail towards safety.
    """
    try:
        result = await classify_query_complexity(query)
        tier = result["tier"]
        _log.info(
            "supervisor.planner.classified",
            query=query,
            tier=tier.value,
            matched_domains=result["matched_domains"],
            classification_metadata=result["classification_metadata"],
        )
        return tier
    except Exception as e:
        _log.error(
            "supervisor.planner.failed_fallback",
            query=query,
            error=str(e),
            fallback_tier=ComplexityTier.MODERATE.value,
        )
        return ComplexityTier.MODERATE
