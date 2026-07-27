"""Unit and integration tests for worker scaling policy and container resource configurations."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from config.settings import get_settings
from workers.scaling_policy import (
    emit_scaling_summary_log,
    get_scaling_metrics,
    recommended_pool_size,
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
