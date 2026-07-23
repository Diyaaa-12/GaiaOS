"""Metrics package — event definitions and minimal emission collector."""

from __future__ import annotations

from metrics.collector import emit
from metrics.events import JobCompleted, JobFailed, JobStarted, MetricEvent

__all__ = [
    "JobCompleted",
    "JobFailed",
    "JobStarted",
    "MetricEvent",
    "emit",
]
