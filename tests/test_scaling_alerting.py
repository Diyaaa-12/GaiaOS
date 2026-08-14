"""Tests for Phase 8 Milestone 1 — Automated Scaling-Trigger Alerting."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alerting.evaluator import _is_threshold_violated, evaluate_rules
from alerting.rules import DEFAULT_ALERT_RULES, AlertRuleSchema
from config.settings import get_settings
from db.models.scaling_telemetry import ScalingTelemetrySampleRow
from db.repository import AlertRepository
from workers.jobs.alert_evaluation_job import _async_run_alert_evaluation
from workers.scaling_policy import (
    evaluate_sustained_queue_depth_breach,
    evaluate_sustained_utilization_breach,
)


class TestScalingAlertRulesSchema:
    """Unit tests for scaling alert rules and comparison operators."""

    def test_default_scaling_rules_schema_validation(self) -> None:
        """All default scaling rules validate against AlertRuleSchema."""
        for rule_dict in DEFAULT_ALERT_RULES:
            schema = AlertRuleSchema.model_validate(rule_dict)
            assert schema.name
            assert schema.threshold >= 0.0

    def test_gte_comparison_operator(self) -> None:
        """Verify greater-than-or-equal (gte) comparison operator logic."""
        assert _is_threshold_violated(100.0, 100.0, "gte")
        assert _is_threshold_violated(105.0, 100.0, "gte")
        assert not _is_threshold_violated(99.9, 100.0, "gte")

    def test_gt_and_lt_comparison_operators(self) -> None:
        """Verify gt and lt comparison operators remain correct."""
        assert _is_threshold_violated(21.0, 20.0, "gt")
        assert not _is_threshold_violated(20.0, 20.0, "gt")
        assert _is_threshold_violated(50.0, 60.0, "lt")


class TestSustainedBreachHelpers:
    """Unit tests for shared pure sustained breach evaluation helper functions."""

    def test_evaluate_sustained_queue_depth_breach(self) -> None:
        """Sustained queue depth breach returns True only when duration >= sustained_seconds."""
        now = datetime.now(UTC)
        # Sample sequence spanning 1000 seconds with depth > 20
        samples = [
            ScalingTelemetrySampleRow(
                queue_depth=25,
                worker_utilization_pct=50.0,
                ts=now,
            ),
            ScalingTelemetrySampleRow(
                queue_depth=25,
                worker_utilization_pct=50.0,
                ts=now + timedelta(minutes=15),
            ),
        ]
        # Over 900s gap
        assert evaluate_sustained_queue_depth_breach(
            samples, threshold=20, sustained_seconds=900.0, max_gap_seconds=1800.0
        )

        # Below threshold sequence
        samples_low = [
            ScalingTelemetrySampleRow(queue_depth=5, worker_utilization_pct=10.0, ts=now)
        ]
        assert not evaluate_sustained_queue_depth_breach(samples_low, threshold=20)

    def test_evaluate_sustained_utilization_breach(self) -> None:
        """Sustained utilization breach returns True when worker_utilization_pct >= 100%."""
        now = datetime.now(UTC)
        samples = [
            ScalingTelemetrySampleRow(queue_depth=0, worker_utilization_pct=100.0, ts=now),
            ScalingTelemetrySampleRow(
                queue_depth=0,
                worker_utilization_pct=100.0,
                ts=now + timedelta(minutes=12),
            ),
        ]
        assert evaluate_sustained_utilization_breach(
            samples, threshold=100.0, sustained_seconds=600.0, max_gap_seconds=1800.0
        )


class TestScalingAlertEvaluatorIntegration:
    """Integration tests for scaling alert rules and incident lifecycle."""

    @pytest.fixture(autouse=True)
    async def _cleanup_alert_tables(self, db_session: AsyncSession) -> None:
        """Clean alert_incidents, alert_rules, metrics, and scaling_telemetry_samples tables."""
        await db_session.execute(text("DELETE FROM alert_incidents"))
        await db_session.execute(text("DELETE FROM alert_rules"))
        await db_session.execute(text("DELETE FROM metrics"))
        await db_session.execute(text("DELETE FROM scaling_telemetry_samples"))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_dynamic_queue_depth_threshold_evaluation(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Queue depth rule threshold is evaluated dynamically as 10 * WORKER_POOL_SIZE."""
        # 1. Insert telemetry sample with queue_depth = 25
        sample = ScalingTelemetrySampleRow(
            queue_depth=25,
            worker_utilization_pct=50.0,
            active_worker_count=2,
            busy_worker_count=1,
            recommended_pool_size=3,
        )
        db_session.add(sample)
        await db_session.commit()

        rule = await AlertRepository.upsert_alert_rule(
            session=db_session,
            name="scaling_queue_depth_breach",
            metric="scaling.queue_depth",
            threshold=20.0,
            comparison="gt",
            window="15m",
            severity="warning",
            consecutive_cycles=3,
        )

        # Default pool size is 2 -> dynamic threshold is 20 -> queue_depth 25 violates (25 > 20)
        firings_pool_2 = await evaluate_rules(db_session, [rule])
        assert len(firings_pool_2) == 1
        assert firings_pool_2[0].threshold == 20.0

        # Pool size 4 -> threshold 40 -> queue_depth 25 does NOT violate
        monkeypatch.setenv("WORKER_POOL_SIZE", "4")
        get_settings.cache_clear()

        firings_pool_4 = await evaluate_rules(db_session, [rule])
        assert len(firings_pool_4) == 0

    @pytest.mark.asyncio
    async def test_p95_queue_wait_mathematical_calculation(
        self, db_session: AsyncSession
    ) -> None:
        """Evaluator computes true P95 queue wait from JobStarted metrics and ignores nulls."""
        # Insert 100 JobStarted metric rows: 94 jobs with 10s wait, 6 jobs with 80s wait
        # P95 should be 80s (80000ms)
        for _ in range(94):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, queue_wait_ms, success, cost_estimate)
                    VALUES (:id, 'JobStarted', now(), 0, 10000, true, 0.0)
                """),
                {"id": uuid.uuid4()},
            )
        for _ in range(6):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, queue_wait_ms, success, cost_estimate)
                    VALUES (:id, 'JobStarted', now(), 0, 80000, true, 0.0)
                """),
                {"id": uuid.uuid4()},
            )

        # Insert 10 null queue_wait_ms rows (JobCompleted or old events) — must be ignored!
        for _ in range(10):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, queue_wait_ms, success, cost_estimate)
                    VALUES (:id, 'JobCompleted', now(), 5000, NULL, true, 0.0)
                """),
                {"id": uuid.uuid4()},
            )
        await db_session.commit()

        rule = await AlertRepository.upsert_alert_rule(
            session=db_session,
            name="scaling_p95_queue_wait_breach",
            metric="scaling.p95_queue_wait_s",
            threshold=60.0,
            comparison="gt",
            window="15m",
            severity="warning",
            consecutive_cycles=1,
        )

        firings = await evaluate_rules(db_session, [rule])
        assert len(firings) == 1
        assert firings[0].rule_name == "scaling_p95_queue_wait_breach"
        assert firings[0].current_value >= 80.0

    @pytest.mark.asyncio
    async def test_scaling_alert_lifecycle_fire_suppression_and_resolve(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end integration test for scaling alert incident lifecycle."""
        monkeypatch.setenv("ALERTING_ENABLED", "true")
        get_settings.cache_clear()

        notifications: list[Any] = []

        async def mock_notify(self_obj: Any, payload: Any) -> bool:
            notifications.append(payload)
            return True

        from alerting.channels.webhook import WebhookNotificationChannel

        monkeypatch.setattr(WebhookNotificationChannel, "notify", mock_notify)

        # 1. Upsert worker utilization rule requiring 4 consecutive cycles (>10 min sustained)
        await AlertRepository.upsert_alert_rule(
            session=db_session,
            name="scaling_worker_utilization_breach",
            metric="scaling.worker_utilization_pct",
            threshold=100.0,
            comparison="gte",
            window="15m",
            severity="warning",
            consecutive_cycles=4,
        )

        # 2. Seed 100% worker utilization sample
        sample = ScalingTelemetrySampleRow(
            queue_depth=5,
            worker_utilization_pct=100.0,
            active_worker_count=2,
            busy_worker_count=2,
            recommended_pool_size=4,
        )
        db_session.add(sample)
        await db_session.commit()

        # 3. Cycle 1: Incident created (consecutive_violations = 1), 0 notifications dispatched
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_1 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "scaling_worker_utilization_breach"
        )
        assert inc_1 is not None
        assert inc_1.status == "firing"
        assert inc_1.consecutive_violations == 1
        assert len(notifications) == 0

        # 4. Cycle 2: Incident updated (consecutive_violations = 2), 0 notifications dispatched
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_2 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "scaling_worker_utilization_breach"
        )
        assert inc_2 is not None
        assert inc_2.consecutive_violations == 2
        assert len(notifications) == 0

        # 5. Cycle 3: Incident updated (consecutive_violations = 3), 0 notifications dispatched
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_3 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "scaling_worker_utilization_breach"
        )
        assert inc_3 is not None
        assert inc_3.consecutive_violations == 3
        assert len(notifications) == 0

        # 6. Cycle 4: Threshold reached (consecutive_violations = 4), notify ONCE!
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_4 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "scaling_worker_utilization_breach"
        )
        assert inc_4 is not None
        assert inc_4.consecutive_violations == 4
        assert len(notifications) == 1
        assert notifications[0].rule_name == "scaling_worker_utilization_breach"

        # 7. Cycle 5: Breach continues (consecutive_violations = 5), ZERO duplicate notify!
        await _async_run_alert_evaluation()
        db_session.expire_all()
        assert len(notifications) == 1  # Still exactly 1 notification!

        # 8. Recovery: Update telemetry sample to 50% utilization (clearing breach)
        await db_session.execute(text("DELETE FROM scaling_telemetry_samples"))
        sample_low = ScalingTelemetrySampleRow(
            queue_depth=0,
            worker_utilization_pct=50.0,
            active_worker_count=2,
            busy_worker_count=1,
            recommended_pool_size=2,
        )
        db_session.add(sample_low)
        await db_session.commit()

        # 9. Cycle 6: Incident resolved, resolution notification dispatched!
        await _async_run_alert_evaluation()
        db_session.expire_all()

        resolved_incidents = await AlertRepository.list_incidents(db_session, status="resolved")
        resolved_names = [i.rule_name for i in resolved_incidents]
        assert "scaling_worker_utilization_breach" in resolved_names
        assert len(notifications) == 2  # 1 firing notification + 1 resolution notification!
