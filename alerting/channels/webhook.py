"""Webhook notification channel implementation — Phase 4 Milestone 3."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from alerting.notifier import NotificationChannel
from alerting.rules import AlertFiring, AlertResolution
from logging_config import get_logger

_log = get_logger(__name__)


class WebhookNotificationChannel(NotificationChannel):
    """Channel-agnostic webhook notifier.

    Delivers alert firing and resolution notifications to configured Webhook URLs
    (compatible with Slack, Discord, PagerDuty, and custom HTTP endpoints).

    Resilience guarantees:
    - Retries failed HTTP POST requests up to max_retries with exponential backoff.
    - Swallows delivery exceptions so worker evaluation jobs are never crashed.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def notify(self, payload: AlertFiring | AlertResolution) -> bool:
        """Deliver alert notification payload via HTTP POST.

        Returns True on successful delivery, False on failure.
        Never raises an exception.
        """
        if not self.webhook_url:
            _log.info(
                "alerting.webhook.skipped_no_url",
                rule_name=payload.rule_name,
            )
            return True

        if isinstance(payload, AlertFiring):
            event_type = "alert.firing"
            body: dict[str, Any] = {
                "event": event_type,
                "rule_name": payload.rule_name,
                "metric": payload.metric,
                "severity": payload.severity,
                "current_value": payload.current_value,
                "threshold": payload.threshold,
                "comparison": payload.comparison,
                "timestamp": payload.fired_at.isoformat(),
            }
        else:
            event_type = "alert.resolution"
            body = {
                "event": event_type,
                "rule_name": payload.rule_name,
                "metric": payload.metric,
                "severity": payload.severity,
                "timestamp": payload.resolved_at.isoformat(),
            }

        async with httpx.AsyncClient(timeout=5.0) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    res = await client.post(self.webhook_url, json=body)
                    if res.status_code < 400:
                        _log.info(
                            "alerting.webhook.sent",
                            alert_event=event_type,
                            rule_name=payload.rule_name,
                            status_code=res.status_code,
                        )
                        return True
                    elif 400 <= res.status_code < 500:
                        # Permanent client error (401, 403, 404, etc.) — do not retry
                        _log.warning(
                            "alerting.webhook.permanent_4xx_error",
                            rule_name=payload.rule_name,
                            status_code=res.status_code,
                        )
                        return False
                    else:
                        # Transient server error (500, 502, 503, 504) — retry
                        _log.warning(
                            "alerting.webhook.transient_5xx_error",
                            rule_name=payload.rule_name,
                            status_code=res.status_code,
                            attempt=attempt,
                        )
                except Exception as exc:
                    _log.warning(
                        "alerting.webhook.request_error",
                        rule_name=payload.rule_name,
                        attempt=attempt,
                        error=str(exc),
                    )

                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        _log.error(
            "alerting.webhook.delivery_failed",
            rule_name=payload.rule_name,
            max_retries=self.max_retries,
        )
        return False


__all__ = ["WebhookNotificationChannel"]
