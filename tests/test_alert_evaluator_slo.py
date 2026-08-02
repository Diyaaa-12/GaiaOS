"""Integration tests for SLO evaluation and SLO-tagged AlertIncident lifecycle — Phase 5 M8."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alerting.evaluator import evaluate_slos
from alerting.slo import SLODefinition
from db.repository import AlertRepository
from workers.jobs.alert_evaluation_job import _async_run_alert_evaluation


class TestSLOEvaluatorIntegration:
    """Integration test suite for SLO burn-rate evaluation and incident creation."""

    @pytest.fixture(autouse=True)
    async def _cleanup_tables(self, db_session: AsyncSession) -> None:
        """Clean alert_incidents, alert_rules, and metrics tables before each test."""
        await db_session.execute(text("DELETE FROM alert_incidents"))
        await db_session.execute(text("DELETE FROM alert_rules"))
        await db_session.execute(text("DELETE FROM metrics"))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_evaluate_slos_firing_incident(self, db_session: AsyncSession) -> None:
        """Seed metric failures causing SLO burn rate > 10.0 and assert AlertFiring."""
        for _ in range(80):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                    VALUES (:id, 'JobCompleted', now(), 100, true, 0.01, 'general')
                """),
                {"id": uuid.uuid4()},
            )
        for _ in range(20):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                    VALUES (:id, 'JobFailed', now(), 100, false, 0.01, 'general')
                """),
                {"id": uuid.uuid4()},
            )
        await db_session.commit()

        slo = SLODefinition(
            name="job_success_rate",
            target=0.99,
            window="30d",
            error_budget_burn_alert_threshold=10.0,
            metric="job_success_rate",
            threshold=0.99,
            comparison="lt",
        )

        firings, burn_results = await evaluate_slos(db_session, [slo])

        assert len(firings) == 1
        firing = firings[0]
        assert firing.rule_name == "job_success_rate"
        assert firing.slo_name == "job_success_rate"
        assert firing.current_value == 20.0
        assert firing.severity == "critical"

        # Create incident with slo_name tag
        incident = await AlertRepository.create_incident(
            session=db_session,
            rule_id=None,
            rule_name=firing.rule_name,
            severity=firing.severity,
            last_value=firing.current_value,
            threshold=firing.threshold,
            slo_name=firing.slo_name,
        )

        assert incident.slo_name == "job_success_rate"
        assert incident.status == "firing"

    @pytest.mark.asyncio
    async def test_full_alert_evaluation_job_with_slos(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full alert evaluation worker job creates SLO-tagged incidents in DB."""

        from config.settings import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "alerting_enabled", True)

        for _ in range(8):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                    VALUES (:id, 'JobCompleted', now(), 200, true, 0.01, 'general')
                """),
                {"id": uuid.uuid4()},
            )
        for _ in range(2):
            await db_session.execute(
                text("""
                    INSERT INTO metrics
                    (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                    VALUES (:id, 'JobFailed', now(), 200, false, 0.01, 'general')
                """),
                {"id": uuid.uuid4()},
            )
        await db_session.commit()

        await _async_run_alert_evaluation()

        incidents = await AlertRepository.list_incidents(db_session)
        slo_incidents = [inc for inc in incidents if inc.slo_name is not None]
        assert len(slo_incidents) >= 1
        assert slo_incidents[0].slo_name == "job_success_rate"
