"""Complexity levels enum for adaptive planning and routing."""

from __future__ import annotations

from enum import StrEnum


class ComplexityTier(StrEnum):
    """Routing complexity tier classification."""

    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
