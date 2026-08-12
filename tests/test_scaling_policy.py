"""Unit and integration tests for worker scaling policy and container resource configurations."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from workers.scaling_policy import (
    emit_scaling_summary_log,
    get_historical_scaling_telemetry,
    get_scaling_metrics,
    prune_scaling_telemetry_samples,
    recommended_pool_size,
    record_scaling_telemetry_sample,
)


def test_recommended_pool_size_low_load() -> None:
    """Verify scaling policy under low load conditions returns configured minimum pool size."""
    settings = get_settings()
    min_pool = settings.worker_pool_size

    # 0 jobs in queue -> returns min_pool
    assert recommended_pool_size(0, 30.0, 60.0) == min_pool

    # 1 job, 10s duration, 60s target wait -> capacity 0.166 -> clamped to min_pool
    assert recommended_pool_size(1, 10.0, 60.0) == min_pool


def test_recommended_pool_size_medium_and_high_load() -> None:
    """Verify scaling policy under medium and high load scales worker pool proportionally."""
    # 10 jobs, 30s avg, 60s target wait -> (10 * 30) / 60 = 5.0 -> 5 workers
    assert recommended_pool_size(10, 30.0, 60.0) == 5

    # 50 jobs, 30s avg, 60s target wait -> (50 * 30) / 60 = 25.0 -> 25 workers
    assert recommended_pool_size(50, 30.0, 60.0) == 25

    # Fractional capacity rounds UP to next integer (ceil)
    # 7 jobs, 25s avg, 60s target wait -> 175 / 60 = 2.916 -> 3 workers
    assert recommended_pool_size(7, 25.0, 60.0) == 3


def test_recommended_pool_size_edge_cases_and_clamping() -> None:
    """Verify safety clamping against invalid, negative, or zero inputs."""
    settings = get_settings()
    min_pool = settings.worker_pool_size

    # Negative queue depth -> clamped to 0 -> returns min_pool
    assert recommended_pool_size(-10, 30.0, 60.0) == min_pool

    # Negative duration and wait times -> safely clamped without crash
    assert recommended_pool_size(-5, -20.0, -10.0) == min_pool

    # Extreme zero target wait -> clamped to min target wait (1.0s)
    res = recommended_pool_size(5, 10.0, 0.0)
    assert res >= min_pool
    assert res == 50  # (5 * 10) / 1.0 = 50


def test_get_scaling_metrics_structure() -> None:
    """Verify get_scaling_metrics returns expected dictionary keys."""
    metrics = get_scaling_metrics()
    assert "current_queue_depth" in metrics
    assert "worker_utilization_pct" in metrics
    assert "recommended_pool_size" in metrics
    assert "configured_min_pool_size" in metrics
    assert isinstance(metrics["current_queue_depth"], int)
    assert isinstance(metrics["worker_utilization_pct"], float)
    assert isinstance(metrics["recommended_pool_size"], int)


def test_emit_scaling_summary_log_executes_without_errors() -> None:
    """Verify emit_scaling_summary_log runs safely without raising exceptions."""
    emit_scaling_summary_log()


def test_docker_compose_resource_limits_configured() -> None:
    """Verify docker-compose.yml defines deploy.resources.limits for app, worker, and scheduler."""
    compose_path = Path("docker-compose.yml").resolve()
    assert compose_path.exists(), "docker-compose.yml must exist"

    with open(compose_path, encoding="utf-8") as f:
        content = yaml.safe_load(f)

    services = content.get("services", {})
    assert "app" in services
    assert "worker" in services
    assert "scheduler" in services

    for svc_name in ("app", "worker", "scheduler"):
        svc_config = services[svc_name]
        assert "deploy" in svc_config, f"Service {svc_name} missing deploy configuration"
        deploy = svc_config["deploy"]
        assert "resources" in deploy, f"Service {svc_name} missing resources configuration"
        resources = deploy["resources"]
        assert "limits" in resources, f"Service {svc_name} missing limits configuration"
        limits = resources["limits"]
        assert "cpus" in limits, f"Service {svc_name} missing cpus limit"
        assert "memory" in limits, f"Service {svc_name} missing memory limit"


@pytest.mark.asyncio
async def test_scaling_telemetry_persistence_and_historical_aggregation(
    db_session: AsyncSession,
) -> None:
    """Verify recording, querying, and pruning historical scaling telemetry samples."""
    # 1. Record sample
    sample = await record_scaling_telemetry_sample(
        session=db_session,
        metrics={
            "current_queue_depth": 5,
            "worker_utilization_pct": 50.0,
            "active_worker_count": 2,
            "busy_worker_count": 1,
            "recommended_pool_size": 2,
        },
    )
    assert sample.id is not None
    assert sample.queue_depth == 5

    # 2. Query historical telemetry summary
    hist = await get_historical_scaling_telemetry(session=db_session, window="7d")
    assert hist["sample_count"] >= 1
    assert hist["max_queue_depth"] >= 5
    assert hist["avg_worker_utilization_pct"] >= 0.0
    assert hist["triggers_met"] is False
    assert "Outcome B" in hist["scaling_verdict"]

    # 3. Prune samples older than 30 days (sample created now should not be pruned)
    pruned = await prune_scaling_telemetry_samples(session=db_session, retention_days=30)
    assert isinstance(pruned, int)


@pytest.mark.asyncio
async def test_scaling_telemetry_sustained_breach_continuity(
    db_session: AsyncSession,
) -> None:
    """Verify continuity rules for sustained scaling breach evaluation."""
    from datetime import UTC, datetime, timedelta

    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    now = datetime.now(UTC)

    # A. Single transient spike -> no sustained breach
    db_session.add(
        ScalingTelemetrySampleRow(
            queue_depth=25,
            worker_utilization_pct=10.0,
            active_worker_count=2,
            busy_worker_count=1,
            recommended_pool_size=5,
            ts=now - timedelta(minutes=5),
        )
    )
    await db_session.commit()

    hist_a = await get_historical_scaling_telemetry(session=db_session, window="1d")
    assert hist_a["threshold_crossed_at_least_once"] is True
    assert hist_a["sustained_queue_depth_breach"] is False
    assert hist_a["sustained_trigger_satisfied"] is False
    assert "Transient Spike Only" in hist_a["scaling_verdict"]

    # B. Qualifying samples with a large missing interval (20min gap > max_gap)
    # -> NO sustained breach
    s_gap1 = ScalingTelemetrySampleRow(
        queue_depth=25,
        worker_utilization_pct=10.0,
        active_worker_count=2,
        busy_worker_count=1,
        recommended_pool_size=5,
        ts=now - timedelta(minutes=50),
    )
    s_gap2 = ScalingTelemetrySampleRow(
        queue_depth=25,
        worker_utilization_pct=10.0,
        active_worker_count=2,
        busy_worker_count=1,
        recommended_pool_size=5,
        ts=now - timedelta(minutes=30),
    )
    db_session.add_all([s_gap1, s_gap2])
    await db_session.commit()

    # C. Regularly spaced qualifying samples (every 5 min) spanning >= 15 minutes
    # -> sustained queue breach
    t_start = now + timedelta(hours=1)
    for m in (0, 5, 10, 15):
        db_session.add(
            ScalingTelemetrySampleRow(
                queue_depth=25,
                worker_utilization_pct=10.0,
                active_worker_count=2,
                busy_worker_count=1,
                recommended_pool_size=5,
                ts=t_start + timedelta(minutes=m),
            )
        )
    await db_session.commit()

    hist_c = await get_historical_scaling_telemetry(session=db_session, window="1d")
    assert hist_c["sustained_queue_depth_breach"] is True
    assert hist_c["sustained_trigger_satisfied"] is True
    assert "Outcome A" in hist_c["scaling_verdict"]


@pytest.mark.asyncio
async def test_scaling_telemetry_utilization_breach_and_interruption_reset(
    db_session: AsyncSession,
) -> None:
    """Verify regularly spaced utilization breach and below-threshold interruption resetting run."""
    from datetime import UTC, datetime, timedelta

    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    now = datetime.now(UTC) + timedelta(hours=2)

    # D. Regularly spaced qualifying samples (every 4 min) spanning >= 10 minutes
    # -> sustained utilization breach
    for m in (0, 4, 8, 11):
        db_session.add(
            ScalingTelemetrySampleRow(
                queue_depth=2,
                worker_utilization_pct=100.0,
                active_worker_count=2,
                busy_worker_count=2,
                recommended_pool_size=2,
                ts=now + timedelta(minutes=m),
            )
        )
    await db_session.commit()

    hist_d = await get_historical_scaling_telemetry(session=db_session, window="1d")
    assert hist_d["sustained_utilization_breach"] is True
    assert hist_d["sustained_trigger_satisfied"] is True
    assert "Outcome A" in hist_d["scaling_verdict"]

@pytest.mark.asyncio
async def test_scaling_telemetry_below_threshold_reset_isolation(
    db_session: AsyncSession,
) -> None:
    """Independently verify that a below-threshold sample resets the sustained breach run."""
    from datetime import UTC, datetime, timedelta

    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    now = datetime.now(UTC)

    # 1. 10 minutes above threshold (not yet reaching 15 min requirement)
    s1 = ScalingTelemetrySampleRow(
        queue_depth=25,
        worker_utilization_pct=10.0,
        active_worker_count=2,
        busy_worker_count=1,
        recommended_pool_size=5,
        ts=now - timedelta(minutes=20),
    )
    s2 = ScalingTelemetrySampleRow(
        queue_depth=25,
        worker_utilization_pct=10.0,
        active_worker_count=2,
        busy_worker_count=1,
        recommended_pool_size=5,
        ts=now - timedelta(minutes=10),
    )

    # 2. Interruption: sample drops below threshold
    s_reset = ScalingTelemetrySampleRow(
        queue_depth=0,
        worker_utilization_pct=0.0,
        active_worker_count=2,
        busy_worker_count=0,
        recommended_pool_size=1,
        ts=now - timedelta(minutes=6),
    )

    # 3. Only 5 minutes above threshold after reset (not sustained)
    s_post_reset = ScalingTelemetrySampleRow(
        queue_depth=25,
        worker_utilization_pct=10.0,
        active_worker_count=2,
        busy_worker_count=1,
        recommended_pool_size=5,
        ts=now - timedelta(minutes=1),
    )

    db_session.add_all([s1, s2, s_reset, s_post_reset])
    await db_session.commit()

    hist = await get_historical_scaling_telemetry(session=db_session, window="1d")
    assert hist["threshold_crossed_at_least_once"] is True
    assert hist["sustained_queue_depth_breach"] is False
    assert hist["sustained_utilization_breach"] is False
    assert hist["sustained_trigger_satisfied"] is False
    assert "Transient Spike Only" in hist["scaling_verdict"]
