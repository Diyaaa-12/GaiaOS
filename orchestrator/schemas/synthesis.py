"""Schemas for synthesis and critic output objects."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.schemas.agent_io import Evidence


class SynthesizedClaim(BaseModel):
    """A synthesized claim backed by mapped evidence citations."""

    text: str = Field(description="The text of the claim.")
    supporting_evidence: list[Evidence] = Field(
        default_factory=list,
        description="List of supporting evidence objects cited for this claim.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Calculated confidence score for this claim.",
    )
    uncertainty_bounds: tuple[float, float] | None = Field(
        default=None,
        description="Explicit uncertainty bounds (low, high) for simulation claims.",
    )
    assumptions: list[str] | None = Field(
        default=None,
        description="Explicit list of assumptions for simulation claims.",
    )


class SynthesisOutput(BaseModel):
    """The synthesized answer block containing claims and identified gaps."""

    claims: list[SynthesizedClaim] = Field(
        default_factory=list,
        description="List of synthesized claims.",
    )
    evidence_gaps: list[str] = Field(
        default_factory=list,
        description="List of domains that had errors or returned no evidence.",
    )


class CriticFlag(BaseModel):
    """A verification flag annotated by the Critic agent."""

    claim_text: str = Field(description="The text of the claim being flagged.")
    flagged_reason: str = Field(description="Reason why the claim is flagged.")
    severity: Literal["low", "medium", "high"] = Field(
        description="The severity of the flag (low, medium, high).",
    )
