"""Integration tests for WebhookNotificationChannel resilience and retries (Milestone 3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx

from alerting.channels.webhook import WebhookNotificationChannel
from alerting.rules import AlertFiring, AlertResolution


class TestWebhookNotifier:
    """Tests for WebhookNotificationChannel delivery resilience."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_successful_firing_notification(self) -> None:
        """Notifier delivers AlertFiring payload over HTTP POST."""
        webhook_url = "https://hooks.example.com/alerts"
        respx.post(webhook_url).respond(200, json={"status": "received"})

        channel = WebhookNotificationChannel(webhook_url=webhook_url)
        firing = AlertFiring(
            rule_name="high_p95_latency",
            metric="investigation.p95_latency_ms",
            current_value=12500.0,
            threshold=10000.0,
            comparison="gt",
            severity="warning",
            fired_at=datetime.now(UTC),
        )

        success = await channel.notify(firing)
        assert success is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_resolution_notification(self) -> None:
        """Notifier delivers AlertResolution payload over HTTP POST."""
        webhook_url = "https://hooks.example.com/alerts"
        respx.post(webhook_url).respond(200, json={"status": "received"})

        channel = WebhookNotificationChannel(webhook_url=webhook_url)
        resolution = AlertResolution(
            rule_name="high_p95_latency",
            metric="investigation.p95_latency_ms",
            severity="warning",
            resolved_at=datetime.now(UTC),
        )

        success = await channel.notify(resolution)
        assert success is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_retry_and_non_blocking_failure(self) -> None:
        """HTTP errors trigger retries and return False without raising exceptions."""
        webhook_url = "https://hooks.example.com/alerts"
        route = respx.post(webhook_url).respond(500, json={"error": "internal_error"})

        channel = WebhookNotificationChannel(
            webhook_url=webhook_url,
            max_retries=2,
            backoff_factor=0.01,
        )
        firing = AlertFiring(
            rule_name="high_p95_latency",
            metric="investigation.p95_latency_ms",
            current_value=12500.0,
            threshold=10000.0,
            comparison="gt",
            severity="warning",
            fired_at=datetime.now(UTC),
        )

        # Swallows delivery exception and returns False
        success = await channel.notify(firing)
        assert success is False
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_webhook_permanent_4xx_failure_fast_fails(self) -> None:
        """HTTP 4xx client errors fail fast without retrying."""
        webhook_url = "https://hooks.example.com/alerts"
        route = respx.post(webhook_url).respond(401, json={"error": "unauthorized"})

        channel = WebhookNotificationChannel(
            webhook_url=webhook_url,
            max_retries=3,
            backoff_factor=0.01,
        )
        firing = AlertFiring(
            rule_name="high_p95_latency",
            metric="investigation.p95_latency_ms",
            current_value=12500.0,
            threshold=10000.0,
            comparison="gt",
            severity="warning",
            fired_at=datetime.now(UTC),
        )

        success = await channel.notify(firing)
        assert success is False
        assert route.call_count == 1
