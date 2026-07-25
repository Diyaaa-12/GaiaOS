"""Metrics package — event definitions, emission collector, and DB persistence."""

from __future__ import annotations

from metrics.collector import emit, persist_metric
from metrics.events import IngestionCompleted, JobCompleted, JobFailed, JobStarted, MetricEvent

__all__ = [
    "IngestionCompleted",
    "JobCompleted",
    "JobFailed",
    "JobStarted",
    "MetricEvent",
    "emit",
    "persist_metric",
]
