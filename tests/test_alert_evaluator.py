"""Integration tests for alert evaluator engine and admin API endpoints (Milestone 3)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alerting.evaluator import evaluate_rules
from auth.jwt_provider import create_access_token
from auth.roles import Role
from config.settings import get_settings
from db.repository import AlertRepository, UserRepository
from workers.jobs.alert_evaluation_job import _async_run_alert_evaluation


class TestAlertEvaluatorIntegration:
    """Integration tests for evaluation job and incident tracking."""

    @pytest.fixture(autouse=True)
    async def _cleanup_alert_tables(self, db_session: AsyncSession) -> None:
        """Clean alert_incidents, alert_rules, and metrics tables before each test."""
        await db_session.execute(text("DELETE FROM alert_incidents"))
        await db_session.execute(text("DELETE FROM alert_rules"))
        await db_session.execute(text("DELETE FROM metrics"))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_evaluate_rules_firing_transition(self, db_session: AsyncSession) -> None:
        """Evaluator detects threshold violation and returns AlertFiring."""
        # 1. Seed metric row crossing 10000ms threshold
        await db_session.execute(
            text("""
                INSERT INTO metrics
                (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                VALUES (:id, 'JobCompleted', now(), 15000, true, 0.05, 'complex')
            """),
            {"id": uuid.uuid4()},
        )
        await db_session.commit()

        # 2. Upsert high_p95_latency rule
        rule = await AlertRepository.upsert_alert_rule(
            session=db_session,
            name="test_p95_latency",
            metric="investigation.p95_latency_ms",
            threshold=10000.0,
            comparison="gt",
            window="15m",
            severity="warning",
        )

        # 3. Evaluate rules
        firings = await evaluate_rules(db_session, [rule])

        assert len(firings) == 1
        assert firings[0].rule_name == "test_p95_latency"
        assert firings[0].current_value >= 15000.0

    @pytest.mark.asyncio
    async def test_alert_evaluation_job_lifecycle(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full evaluation job creates AlertIncident, handles firing, and resolves on recovery."""
        monkeypatch.setenv("ALERTING_ENABLED", "true")
        get_settings.cache_clear()

        # 1. Run evaluation on empty DB (seeds default rules)
        await _async_run_alert_evaluation()

        rules = await AlertRepository.list_alert_rules(db_session)
        assert len(rules) >= 2

        # 2. Insert high latency metric to cause firing
        await db_session.execute(
            text("""
                INSERT INTO metrics
                (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                VALUES (:id, 'JobCompleted', now(), 25000, true, 0.05, 'complex')
            """),
            {"id": uuid.uuid4()},
        )
        await db_session.commit()

        # 3. Run evaluation -> creates firing incident
        await _async_run_alert_evaluation()

        open_inc = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "high_p95_latency"
        )
        assert open_inc is not None
        assert open_inc.status == "firing"
        assert open_inc.last_value >= 25000.0

        # 4. Clean metrics table to simulate metric recovery
        await db_session.execute(text("DELETE FROM metrics"))
        await db_session.commit()

        # 5. Run evaluation -> resolves firing incident
        await _async_run_alert_evaluation()
        db_session.expire_all()

        incidents = await AlertRepository.list_incidents(db_session, status="resolved")
        resolved_names = [i.rule_name for i in incidents]
        assert "high_p95_latency" in resolved_names

    @pytest.mark.asyncio
    async def test_flapping_suppression_consecutive_cycles(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify consecutive_cycles > 1 requires multiple evaluation runs before notifying."""
        monkeypatch.setenv("ALERTING_ENABLED", "true")
        get_settings.cache_clear()

        notifications: list[Any] = []

        async def mock_notify(self_obj: Any, payload: Any) -> bool:
            notifications.append(payload)
            return True

        from alerting.channels.webhook import WebhookNotificationChannel

        monkeypatch.setattr(WebhookNotificationChannel, "notify", mock_notify)

        # 1. Upsert rule requiring 2 consecutive cycles
        await AlertRepository.upsert_alert_rule(
            session=db_session,
            name="strict_flapping_rule",
            metric="investigation.p95_latency_ms",
            threshold=5000.0,
            comparison="gt",
            window="15m",
            severity="warning",
            consecutive_cycles=2,
        )

        # 2. Insert metric violating threshold
        await db_session.execute(
            text("""
                INSERT INTO metrics
                (id, event_type, ts, duration_ms, success, cost_estimate, group_key)
                VALUES (:id, 'JobCompleted', now(), 8000, true, 0.05, 'complex')
            """),
            {"id": uuid.uuid4()},
        )
        await db_session.commit()

        # 3. 1st cycle: incident created (consecutive_violations = 1, NO notification sent)
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_1 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "strict_flapping_rule"
        )
        assert inc_1 is not None
        assert inc_1.status == "firing"
        assert inc_1.consecutive_violations == 1
        assert len(notifications) == 0  # Zero notifications dispatched on cycle 1

        # 4. 2nd cycle: consecutive_violations = 2, notification dispatched EXACTLY ONCE
        await _async_run_alert_evaluation()
        db_session.expire_all()

        inc_2 = await AlertRepository.get_open_incident_by_rule_name(
            db_session, "strict_flapping_rule"
        )
        assert inc_2 is not None
        assert inc_2.consecutive_violations == 2
        assert len(notifications) == 1  # Exactly 1 notification dispatched on cycle 2!
        assert notifications[0].rule_name == "strict_flapping_rule"


class TestAdminAlertAPIEndpoints:
    """Integration tests for Admin Alert API endpoints."""

    async def _create_admin_headers(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, str]:
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
        user = await UserRepository.create_user(
            session=session,
            email=email,
            hashed_password="Password123!",
            role=Role.ADMIN.value,
            is_verified=True,
        )
        token = create_access_token(user.id, user.role, secret_key=key)
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_admin_upsert_and_delete_alert_rule(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADMIN role can list, upsert, and delete alert rules."""
        headers = await self._create_admin_headers(db_session, monkeypatch)

        # 1. Upsert new rule
        payload = {
            "name": "custom_api_rule",
            "metric": "investigation.p95_latency_ms",
            "threshold": 5000.0,
            "comparison": "gt",
            "window": "15m",
            "severity": "critical",
            "consecutive_cycles": 2,
            "is_enabled": True,
        }
        res_upsert = await client.post(
            "/api/v1/admin/alert-rules",
            json=payload,
            headers=headers,
        )
        assert res_upsert.status_code == 200
        rule_data = res_upsert.json()
        assert rule_data["name"] == "custom_api_rule"
        rule_id = rule_data["id"]

        # 2. List alert rules
        res_list = await client.get(
            "/api/v1/admin/alert-rules",
            headers=headers,
        )
        assert res_list.status_code == 200
        rule_names = [r["name"] for r in res_list.json()]
        assert "custom_api_rule" in rule_names

        # 3. Delete alert rule
        res_del = await client.delete(
            f"/api/v1/admin/alert-rules/{rule_id}",
            headers=headers,
        )
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_non_admin_forbidden(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """USER role receives 403 Forbidden on admin alert endpoints."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        email = f"user-{uuid.uuid4().hex[:6]}@example.com"
        user = await UserRepository.create_user(
            session=db_session,
            email=email,
            hashed_password="Password123!",
            role=Role.USER.value,
            is_verified=True,
        )
        token = create_access_token(user.id, user.role, secret_key=key)
        user_headers = {"Authorization": f"Bearer {token}"}

        res = await client.get(
            "/api/v1/admin/alerts",
            headers=user_headers,
        )
        assert res.status_code == 403
