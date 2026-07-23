"""Minimal metrics write-path collector."""

from __future__ import annotations

from logging_config import get_logger
from metrics.events import MetricEvent

_log = get_logger(__name__)


def emit(event: MetricEvent) -> None:
    """Emit a metric event to structured access logs.

    This is the minimal write path for Phase 3 Milestone 3.
    Full aggregation metrics backend is implemented in Milestone 9.
    """
    event_type = event.__class__.__name__
    _log.info("metrics.event", event_type=event_type, **event.as_dict())
