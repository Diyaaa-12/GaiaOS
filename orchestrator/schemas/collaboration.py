"""Schemas for multi-agent collaboration protocol (Phase 5 Milestone 4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.schemas.uncertainty import UncertaintyEstimate


class CollaborationMessage(BaseModel):
    """Structured message broadcast by domain agents during fan-out collaboration.

    Immutable once constructed to prevent race conditions during concurrent broadcast.
    """

    model_config = ConfigDict(frozen=True)

    from_agent: str = Field(
        ...,
        description="Domain agent name broadcasting the finding.",
    )
    finding_summary: str = Field(
        ...,
        description="Structured summary of the early finding.",
    )
    uncertainty: UncertaintyEstimate = Field(
        ...,
        description="Structured uncertainty estimate associated with the finding.",
    )
    suggested_refinement: dict[str, Any] | None = Field(
        default=None,
        description="Structured refinement parameters (e.g., {'region_hint': '...'}).",
    )
    round: int = Field(
        default=0,
        ge=0,
        description="Collaboration round index when message was broadcast.",
    )
