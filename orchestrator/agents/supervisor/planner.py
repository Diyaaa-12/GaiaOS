"""Adaptive Planner and Complexity Classifier logic."""

from __future__ import annotations

from orchestrator.schemas.complexity import ComplexityTier


async def classify_query(query: str) -> ComplexityTier:
    """Analyze query complexity and target domain scopes.

    In Milestone 2, this functions as a stub planner routing queries
    to the TRIVIAL tier (as only the Air Quality agent is implemented).
    """
    # Simply classify as TRIVIAL for Milestone 2 graph validation.
    return ComplexityTier.TRIVIAL
