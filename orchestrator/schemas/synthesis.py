"""Schemas for synthesis and critic output objects."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError

from orchestrator.schemas.agent_io import Evidence
from orchestrator.schemas.uncertainty import UncertaintyEstimate


class RawCitedEvidence(BaseModel):
    """Raw citation payload parsed from LLM completion response."""

    evidence_id: uuid.UUID | None = Field(
        default=None,
        description="Optional evidence_id cited by LLM.",
    )
    source: str = Field(description="Name or URL of the data source.")
    claim: str = Field(description="The factual claim or observation extracted.")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Assigned confidence level for this citation.",
    )


class SynthesizedClaim(BaseModel):
    """A synthesized claim backed by mapped evidence citations."""

    text: str = Field(description="The text of the claim.")
    supporting_evidence: list[Evidence] = Field(
        default_factory=list,
        description="List of supporting evidence objects cited for this claim.",
    )
    uncertainty: UncertaintyEstimate = Field(
        default_factory=lambda: UncertaintyEstimate(
            point_estimate=0.5, lower_bound=0.4, upper_bound=0.6, source="model_uncertainty"
        ),
        description="Structured uncertainty estimate calculated for this claim.",
    )
    uncertainty_bounds: tuple[float, float] | None = Field(
        default=None,
        description="Explicit uncertainty bounds (low, high) for simulation claims.",
    )
    assumptions: list[str] | None = Field(
        default=None,
        description="Explicit list of assumptions for simulation claims.",
    )

    def __init__(self, confidence: float | None = None, **data: Any) -> None:
        if confidence is not None and "uncertainty" not in data:
            if not (0.0 <= confidence <= 1.0):
                raise ValidationError.from_exception_data(
                    "SynthesizedClaim",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error", "Confidence must be between 0.0 and 1.0"
                            ),
                            loc=("confidence",),
                            input=confidence,
                        )
                    ],
                )
            data["uncertainty"] = UncertaintyEstimate.from_legacy_confidence(confidence)
        super().__init__(**data)

    @property
    def confidence(self) -> float:
        """Backward-compatible read-only property returning uncertainty point estimate."""
        return self.uncertainty.point_estimate


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
    flagged_domains: list[str] | None = Field(
        default=None,
        description="Optional structured list of domain identifiers associated with this flag.",
    )
