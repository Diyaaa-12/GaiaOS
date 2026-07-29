"""Typed I/O contracts for domain agents."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError

from orchestrator.schemas.uncertainty import UncertaintyEstimate


class Evidence(BaseModel):
    """A supporting evidence item extracted by a domain agent."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique immutable ID for this evidence item.",
    )
    source: str = Field(description="Name or URL of the data source.")
    claim: str = Field(description="The factual claim or observation extracted.")
    uncertainty: UncertaintyEstimate = Field(
        default_factory=lambda: UncertaintyEstimate(
            point_estimate=0.5, lower_bound=0.4, upper_bound=0.6, source="model_uncertainty"
        ),
        description="Assigned structured uncertainty estimate for this evidence item.",
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when this evidence was queried/scraped.",
    )
    document_id: str | None = Field(
        default=None,
        description="Identifier of the specific literature document.",
    )
    chunk_id: str | int | None = Field(
        default=None,
        description="Identifier of the specific text chunk within the document.",
    )
    title: str | None = Field(
        default=None,
        description="Title of the source document.",
    )
    source_url: str | None = Field(
        default=None,
        description="Original source URL of the document.",
    )
    extra_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra domain-specific metadata.",
    )
    uncertainty_bounds: tuple[float, float] | None = Field(
        default=None,
        description="Explicit uncertainty bounds (low, high) for simulation results.",
    )
    assumptions: list[str] | None = Field(
        default=None,
        description="Explicit list of assumptions for the simulation/prediction model.",
    )

    def __init__(self, confidence: float | None = None, **data: Any) -> None:
        if confidence is not None and "uncertainty" not in data:
            if not (0.0 <= confidence <= 1.0):
                raise ValidationError.from_exception_data(
                    "Evidence",
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


class SimulationResult(BaseModel):
    """The structured result of a simulation model prediction."""

    prediction: str = Field(description="The forecasted result text.")
    uncertainty_bounds: tuple[float, float] = Field(
        description="Explicit uncertainty bounds (low, high) for the simulation."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made by the model.",
    )
    model_used: str = Field(description="The name of the simulation model utilized.")
    uncertainty: UncertaintyEstimate | None = Field(
        default=None,
        description="Explicit structured uncertainty estimate representation.",
    )


class AgentInput(BaseModel):
    """Input payload expected by a domain agent's run function."""

    investigation_id: uuid.UUID = Field(description="Unique ID of the parent investigation.")
    query: str = Field(description="User search query or instructions.")
    region_hint: str | None = Field(
        default=None,
        description="Optional location query boundary (e.g. 'Paris').",
    )


class AgentOutput(BaseModel):
    """Standardized output structure returned by all domain agents."""

    agent_name: str = Field(description="Name of the agent generating this output.")
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="List of retrieved evidence blocks.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Non-blocking tool-call or querying errors encountered.",
    )
