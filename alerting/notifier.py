"""NotificationChannel Protocol definition — Phase 4 Milestone 3.

Mirrors existing AuthProvider and RateLimiter Protocol patterns.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from alerting.rules import AlertFiring, AlertResolution


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol defining the interface for alert notification delivery channels."""

    async def notify(self, payload: AlertFiring | AlertResolution) -> bool:
        """Deliver alert notification payload to target channel.

        Returns True on successful delivery, False on failure.
        Must handle transient failures gracefully and avoid crashing callers.
        """
        ...


__all__ = ["NotificationChannel"]
