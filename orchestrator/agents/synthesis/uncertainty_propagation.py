"""Uncertainty Propagation Engine (Phase 5 Milestone 3).

Combines UncertaintyEstimates from multiple evidence sources into a single,
honest UncertaintyEstimate for synthesized claims.

Invariants:
1. Field constraints enforce numeric range [0.0, 1.0].
2. lower_bound <= point_estimate <= upper_bound.
3. Combination rule NEVER narrows interval on conflicting evidence.
4. Deterministic computation without randomness or LLM-prompt judgment.
"""

from __future__ import annotations

from itertools import combinations

from orchestrator.schemas.uncertainty import SourceType, UncertaintyEstimate

# Named Constants
CONFLICT_SPREAD_THRESHOLD: float = 0.15
"""Point estimate spread threshold (max_pt - min_pt >= 0.15) above which evidence is

flagged as conflicting. This threshold is intentionally conservative and deterministic
to ensure disagreement between domain agents is explicitly surfaced rather than averaged out.
"""

MIN_CONFLICT_PADDING: float = 0.05
"""Minimum interval padding added under evidence conflict to widen the combined

uncertainty interval beyond union bounds, ensuring conflict is highlighted.
"""


def propagate_uncertainty(estimates: list[UncertaintyEstimate]) -> UncertaintyEstimate:
    """Propagate and combine uncertainty estimates across multiple evidence items.

    Conflict Detection Rules:
    An evidence_conflict tag is produced if ANY of the following conservative criteria hold:
    1. Spread threshold: The difference between maximum and minimum point estimates
       is >= CONFLICT_SPREAD_THRESHOLD (0.15).
    2. Disjoint intervals: Any pair of evidence items has non-overlapping bounds
       (e1.upper_bound < e2.lower_bound or e2.upper_bound < e1.lower_bound).
    3. Propagated conflict: Any input evidence item already carries source == "evidence_conflict".

    This combination rule is intentionally conservative and deterministic.

    Args:
        estimates: List of UncertaintyEstimate objects to combine.

    Returns:
        A combined UncertaintyEstimate reflecting aggregated confidence and source tag.
    """
    if not estimates:
        return UncertaintyEstimate(
            point_estimate=0.5,
            lower_bound=0.0,
            upper_bound=1.0,
            source="model_uncertainty",
        )

    if len(estimates) == 1:
        single = estimates[0]
        return UncertaintyEstimate(
            point_estimate=single.point_estimate,
            lower_bound=single.lower_bound,
            upper_bound=single.upper_bound,
            source=single.source,
        )

    # 1. Extract component point estimates and interval bounds
    min_pt = min(e.point_estimate for e in estimates)
    max_pt = max(e.point_estimate for e in estimates)
    union_lower = min(e.lower_bound for e in estimates)
    union_upper = max(e.upper_bound for e in estimates)
    spread = max_pt - min_pt

    # 2. Detect evidence conflict pairwise using itertools.combinations
    has_disjoint_intervals = any(
        e1.upper_bound < e2.lower_bound or e2.upper_bound < e1.lower_bound
        for e1, e2 in combinations(estimates, 2)
    )
    is_conflict = (
        spread >= CONFLICT_SPREAD_THRESHOLD
        or has_disjoint_intervals
        or any(e.source == "evidence_conflict" for e in estimates)
    )

    # 3. Determine combined source tag
    combined_source: SourceType
    if is_conflict:
        combined_source = "evidence_conflict"
    elif any(e.source == "data_sparsity" for e in estimates):
        combined_source = "data_sparsity"
    elif any(e.source == "model_uncertainty" for e in estimates):
        combined_source = "model_uncertainty"
    else:
        combined_source = "well_supported"

    # 4. Calculate combined point estimate and bounds
    avg_pt = sum(e.point_estimate for e in estimates) / len(estimates)
    combined_pt = avg_pt

    if is_conflict:
        # Conflict penalty widens interval beyond union bounds
        penalty = max(MIN_CONFLICT_PADDING, spread / 2.0)
        combined_lower = min(union_lower, min_pt) - penalty
        combined_upper = max(union_upper, max_pt) + penalty
    else:
        combined_lower = union_lower
        combined_upper = union_upper

    # 5. Enforce "never narrows" invariant and boundary constraints
    combined_lower = min(combined_lower, union_lower)
    combined_upper = max(combined_upper, union_upper)

    combined_lower = max(0.0, min(1.0, combined_lower))
    combined_upper = max(0.0, min(1.0, combined_upper))
    combined_pt = max(combined_lower, min(combined_upper, combined_pt))

    return UncertaintyEstimate(
        point_estimate=combined_pt,
        lower_bound=combined_lower,
        upper_bound=combined_upper,
        source=combined_source,
    )
