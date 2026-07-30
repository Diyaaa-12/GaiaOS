"""Uncertainty Estimation Schema (Phase 5 Milestone 3).

Provides a principled, consistent uncertainty representation replacing ad-hoc
confidence floats with explicit point estimates, confidence bounds, and source tags.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

SourceType = Literal[
    "data_sparsity",
    "model_uncertainty",
    "evidence_conflict",
    "well_supported",
]

# Named Constants
DEFAULT_LEGACY_FALLBACK_MARGIN: float = 0.1
"""Fallback interval margin (+/- 0.1) used when converting legacy scalar confidence

scores into an UncertaintyEstimate. This is a conservative compatibility mechanism only
and is not statistically derived.
"""

DEFAULT_POINT_ESTIMATE_INTERVAL_MARGIN: float = 0.08
"""Default symmetric margin (+/- 0.08) around point estimates when constructing

UncertaintyEstimate intervals via helper functions.
"""


class UncertaintyEstimate(BaseModel):
    """Structured representation of uncertainty for evidence and claims."""

    point_estimate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Point estimate of confidence/probability in range [0.0, 1.0].",
    )
    lower_bound: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Lower bound of uncertainty interval in range [0.0, 1.0].",
    )
    upper_bound: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Upper bound of uncertainty interval in range [0.0, 1.0].",
    )
    source: SourceType = Field(
        ...,
        description="Source tag for uncertainty estimate.",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> UncertaintyEstimate:
        """Validate ordering invariant: lower_bound <= point_estimate <= upper_bound.

        Numeric range validation (ge=0.0, le=1.0) is handled by Pydantic field constraints.

        Raises:
            ValueError: If lower_bound > point_estimate or point_estimate > upper_bound.
        """
        if not (self.lower_bound <= self.point_estimate <= self.upper_bound):
            raise ValueError(
                f"Invalid uncertainty interval: lower_bound ({self.lower_bound}) "
                f"must be <= point_estimate ({self.point_estimate}) "
                f"must be <= upper_bound ({self.upper_bound})."
            )
        return self

    @classmethod
    def from_point_estimate(
        cls,
        point_estimate: float,
        margin: float = DEFAULT_POINT_ESTIMATE_INTERVAL_MARGIN,
        source: SourceType = "well_supported",
    ) -> UncertaintyEstimate:
        """Construct an UncertaintyEstimate interval around a point estimate.

        Consistently generates symmetric uncertainty bounds clamped to [0.0, 1.0].

        Args:
            point_estimate: Central probability or confidence score in [0.0, 1.0].
            margin: Symmetric interval half-width (defaults to
                DEFAULT_POINT_ESTIMATE_INTERVAL_MARGIN).
            source: Source tag identifying origin of uncertainty.

        Returns:
            A valid UncertaintyEstimate instance.
        """
        if not (0.0 <= point_estimate <= 1.0):
            raise ValueError(f"Point estimate {point_estimate} must be between 0.0 and 1.0.")
        pt = float(point_estimate)
        return cls(
            point_estimate=pt,
            lower_bound=max(0.0, pt - margin),
            upper_bound=min(1.0, pt + margin),
            source=source,
        )

    @classmethod
    def from_legacy_confidence(
        cls,
        confidence: float,
        source: SourceType = "model_uncertainty",
    ) -> UncertaintyEstimate:
        """Convert a legacy confidence float into an UncertaintyEstimate.

        Note: The interval constructed with DEFAULT_LEGACY_FALLBACK_MARGIN (+/- 0.1) is a
        conservative compatibility mechanism for legacy scalar confidence scores and is
        not statistically derived.
        """
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence score {confidence} must be between 0.0 and 1.0.")
        conf = float(confidence)
        return cls(
            point_estimate=conf,
            lower_bound=max(0.0, conf - DEFAULT_LEGACY_FALLBACK_MARGIN),
            upper_bound=min(1.0, conf + DEFAULT_LEGACY_FALLBACK_MARGIN),
            source=source,
        )
