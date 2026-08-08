"""Background RQ job for longitudinal pattern mining (Phase 7 Milestone 2)."""

from __future__ import annotations

import asyncio
import hashlib
import math
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from config.settings import get_settings
from db.models.hazard_event import HazardEvent
from db.repository import PatternFindingRepository
from db.session import get_session_factory
from logging_config import get_logger
from orchestrator.schemas.uncertainty import UncertaintyEstimate

_log = get_logger(__name__)

ALGORITHM_VERSION: str = "1.0"


def calculate_wilson_lower_bound(
    successes: int,
    trials: int,
    z: float = 1.96,
) -> float:
    """Compute the Wilson score interval lower bound for a binomial proportion.

    Args:
        successes: Number of observed co-occurrence events (support_count).
        trials: Total number of source events.
        z: Normal distribution z-score (default 1.96 for ~95% confidence).

    Returns:
        Lower bound of the Wilson confidence interval in range [0.0, 1.0].
    """
    if trials <= 0 or successes <= 0:
        return 0.0

    p_hat = min(1.0, max(0.0, successes / trials))
    denom = 1 + (z**2 / trials)
    center = p_hat + (z**2 / (2 * trials))
    radicand = (p_hat * (1 - p_hat) / trials) + (z**2 / (4 * trials**2))
    spread = z * math.sqrt(max(0.0, radicand))

    lower = (center - spread) / denom
    return max(0.0, min(1.0, float(lower)))


def generate_pattern_hash(
    source_event_type: str,
    target_event_type: str,
    region_label: str | None,
    time_window_days: int,
    algorithm_version: str = ALGORITHM_VERSION,
) -> str:
    """Generate a stable, deterministic SHA-256 hash identifying a pattern candidate."""
    raw_key = (
        f"{algorithm_version}:{source_event_type.strip().lower()}:"
        f"{target_event_type.strip().lower()}:"
        f"{(region_label or '').strip().lower()}:{time_window_days}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def execute_pattern_mining(
    source_tag: str = "longitudinal_patterns",
) -> dict[str, Any]:
    """Asynchronous core execution for longitudinal pattern mining."""
    start_time = time.perf_counter()
    settings = get_settings()

    lookback_days = settings.pattern_lookback_days
    min_support = settings.pattern_min_support
    min_confidence = settings.pattern_min_confidence

    cutoff_date = datetime.now(UTC) - timedelta(days=lookback_days)

    async with get_session_factory()() as session:
        # Fetch events within lookback window
        stmt = select(HazardEvent).where(HazardEvent.event_date >= cutoff_date)
        res = await session.execute(stmt)
        events = list(res.scalars().all())

        events_scanned = len(events)
        candidate_pairs_count = 0
        accepted_findings_count = 0
        rejected_findings_count = 0

        if events_scanned < 2:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log.info(
                "pattern_mining.completed",
                events_scanned=events_scanned,
                candidate_pairs=0,
                accepted_findings=0,
                rejected_findings=0,
                duration_ms=round(duration_ms, 2),
            )
            return {
                "events_scanned": events_scanned,
                "candidate_pairs": 0,
                "accepted_findings": 0,
                "rejected_findings": 0,
                "duration_ms": round(duration_ms, 2),
            }

        # Group events by (event_type, region_label)
        type_region_groups: dict[tuple[str, str | None], list[HazardEvent]] = {}
        for ev in events:
            key = (ev.event_type.strip().lower(), ev.region_label)
            type_region_groups.setdefault(key, []).append(ev)

        event_types = sorted({ev.event_type.strip().lower() for ev in events})
        regions = sorted({ev.region_label for ev in events})
        time_windows = [7, 14, 30]
        mined_at = datetime.now(UTC)

        for source_type in event_types:
            for target_type in event_types:
                if source_type == target_type:
                    continue

                for region in regions:
                    for window_days in time_windows:
                        candidate_pairs_count += 1

                        # Get source and target events matching region
                        src_events = [
                            e
                            for e in events
                            if e.event_type.strip().lower() == source_type
                            and e.region_label == region
                        ]
                        tgt_events = [
                            e
                            for e in events
                            if e.event_type.strip().lower() == target_type
                            and e.region_label == region
                        ]

                        total_source_events = len(src_events)
                        total_target_events = len(tgt_events)

                        if total_source_events == 0 or total_target_events == 0:
                            rejected_findings_count += 1
                            continue

                        # Find co-occurring target events following source events within window
                        co_occurrences: list[tuple[HazardEvent, HazardEvent]] = []
                        supporting_event_ids_set: set[str] = set()

                        for s_ev in src_events:
                            for t_ev in tgt_events:
                                time_diff = (t_ev.event_date - s_ev.event_date).total_seconds()
                                if 0 < time_diff <= window_days * 86400:
                                    co_occurrences.append((s_ev, t_ev))
                                    supporting_event_ids_set.add(str(s_ev.id))
                                    supporting_event_ids_set.add(str(t_ev.id))

                        support_count = len(co_occurrences)
                        if support_count < min_support:
                            rejected_findings_count += 1
                            continue

                        observed_rate = support_count / total_source_events
                        baseline_rate = total_target_events / max(1, events_scanned)

                        if baseline_rate <= 0.0:
                            rejected_findings_count += 1
                            continue

                        lift = observed_rate / baseline_rate
                        if lift <= 1.0:
                            # Must exhibit positive correlation / lift > 1.0
                            rejected_findings_count += 1
                            continue

                        # Calculate Wilson confidence lower bound
                        confidence = calculate_wilson_lower_bound(
                            successes=support_count,
                            trials=total_source_events,
                        )

                        if confidence < min_confidence:
                            rejected_findings_count += 1
                            continue

                        # Build UncertaintyEstimate per Phase 5 M3
                        source_tag_type = (
                            "well_supported" if confidence >= 0.85 else "model_uncertainty"
                        )
                        uncertainty_obj = UncertaintyEstimate.from_point_estimate(
                            point_estimate=confidence,
                            source=source_tag_type,
                        )

                        pattern_hash = generate_pattern_hash(
                            source_event_type=source_type,
                            target_event_type=target_type,
                            region_label=region,
                            time_window_days=window_days,
                            algorithm_version=ALGORITHM_VERSION,
                        )

                        reg_desc = f" in {region}" if region else " globally"
                        description = (
                            f"Longitudinal pattern: {source_type.title()} is followed by "
                            f"{target_type.title()}{reg_desc} within {window_days} days "
                            f"(Observed: {observed_rate:.1%}, Baseline: {baseline_rate:.1%}, "
                            f"Lift: {lift:.2f}x, Confidence: {confidence:.2f})."
                        )

                        await PatternFindingRepository.save_pattern_version(
                            session=session,
                            pattern_hash=pattern_hash,
                            source_event_type=source_type,
                            target_event_type=target_type,
                            region_label=region,
                            time_window_days=window_days,
                            support_count=support_count,
                            total_source_events=total_source_events,
                            total_target_events=total_target_events,
                            observed_rate=round(observed_rate, 4),
                            baseline_rate=round(baseline_rate, 4),
                            lift=round(lift, 4),
                            statistical_confidence=round(confidence, 4),
                            uncertainty=uncertainty_obj.model_dump(),
                            supporting_event_ids=sorted(supporting_event_ids_set),
                            description=description,
                            mined_at=mined_at,
                            algorithm_version=ALGORITHM_VERSION,
                        )
                        accepted_findings_count += 1

        if session.dirty or session.new or session.deleted:
            await session.commit()

        duration_ms = (time.perf_counter() - start_time) * 1000

        # TODO: Optimize O(N^2) pairwise event comparisons with a time-sorted sliding
        # window / index-based search for larger Phase 6 datasets (N > 10,000 events).
        _log.info(
            "pattern_mining.completed",
            events_scanned=events_scanned,
            candidate_pairs=candidate_pairs_count,
            accepted_findings=accepted_findings_count,
            rejected_findings=rejected_findings_count,
            duration_ms=round(duration_ms, 2),
        )

        return {
            "events_scanned": events_scanned,
            "candidate_pairs": candidate_pairs_count,
            "accepted_findings": accepted_findings_count,
            "rejected_findings": rejected_findings_count,
            "duration_ms": round(duration_ms, 2),
        }


def run_pattern_mining_job(source: str = "longitudinal_patterns") -> dict[str, Any]:
    """Synchronous RQ worker entrypoint wrapper."""
    _log.info("pattern_mining.job_started", source=source)
    try:
        return asyncio.run(execute_pattern_mining(source_tag=source))
    except Exception as exc:
        _log.error("pattern_mining.job_failed", error=str(exc))
        raise exc
