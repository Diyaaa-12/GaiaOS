"""Integration tests for GET /api/v1/admin/metrics — Phase 3 Milestone 9.

Test strategy (per Roadmap §13):
- Integration: ADMIN user receives 200 with MetricRollup[]
- Integration: Non-admin user receives 403
- Integration: Empty DB window returns 200 with rollups: []
- Edge case: invalid window parameter returns 422 (FastAPI validation)
- Edge case: invalid group_by parameter returns 422
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_provider import create_access_token
from auth.roles import Role
from config.settings import get_settings
from db.repository import UserRepository

pytestmark = pytest.mark.asyncio


class TestAdminMetricsEndpoint:
    """Integration tests for the /admin/metrics endpoint."""

    async def _create_user(self, session: AsyncSession, role: Role):
        """Create a verified user with the given role."""
        email = f"{role.value}-{uuid.uuid4().hex[:6]}@gaiaos-test.example"
        user = await UserRepository.create_user(
            session=session,
            email=email,
            hashed_password="HashedPassword123!",
            role=role.value,
            is_verified=True,
        )
        return user

    async def test_admin_gets_200_with_rollups_key(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """ADMIN user receives 200 and a response with a 'rollups' list."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "complexity_tier"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "rollups" in body
        assert isinstance(body["rollups"], list)
        assert body["window"] == "7d"
        assert body["group_by"] == "complexity_tier"

    async def test_empty_window_returns_200_not_error(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """No metrics data in the window → 200 with empty rollups list, not an error."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        # 90d window — almost certainly no data for a freshly-seeded test DB
        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "1d", "group_by": "day"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "rollups" in body
        assert isinstance(body["rollups"], list)

    async def test_non_admin_user_gets_403(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """A regular USER is forbidden from accessing the admin metrics endpoint."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        regular_user = await self._create_user(db_session, Role.USER)
        token = create_access_token(regular_user.id, regular_user.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "complexity_tier"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    async def test_researcher_gets_403(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """A RESEARCHER is also forbidden — only ADMIN is allowed."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        researcher = await self._create_user(db_session, Role.RESEARCHER)
        token = create_access_token(researcher.id, researcher.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "complexity_tier"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    async def test_unauthenticated_gets_401(self, client: AsyncClient, monkeypatch) -> None:
        """Unauthenticated request returns 401."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()
        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "complexity_tier"},
        )
        assert res.status_code == 401

    async def test_invalid_window_parameter_returns_422(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch,
    ) -> None:
        """An unrecognised window value is rejected by FastAPI validation."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "999d", "group_by": "complexity_tier"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    async def test_invalid_group_by_parameter_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """An unrecognised group_by value is rejected by FastAPI validation."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "DROP TABLE metrics"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    async def test_all_group_by_values_accepted(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """All valid group_by values return 200."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        for group_by_val in ("complexity_tier", "day"):
            res = await client.get(
                "/api/v1/admin/metrics",
                params={"window": "7d", "group_by": group_by_val},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200, f"Expected 200 for group_by={group_by_val!r}"

    async def test_all_window_values_accepted(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """All valid window values return 200."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        for window_val in ("1d", "7d", "30d", "90d"):
            res = await client.get(
                "/api/v1/admin/metrics",
                params={"window": window_val, "group_by": "day"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200, f"Expected 200 for window={window_val!r}"

    async def test_response_schema_fields(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Response body contains all required MetricRollup fields when data is present."""
        import uuid as _uuid
        from datetime import UTC, datetime
        from decimal import Decimal

        from db.models.metric_event import MetricEventRow

        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        # Seed one row so rollups is non-empty
        db_session.add(
            MetricEventRow(
                id=_uuid.uuid4(),
                event_type="JobCompleted",
                group_key=None,
                duration_ms=1500,
                cost_estimate=Decimal("0"),
                success=True,
                ts=datetime.now(UTC),
            )
        )
        await db_session.commit()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "1d", "group_by": "complexity_tier"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "generated_at" in body
        assert len(body["rollups"]) >= 1
        rollup = body["rollups"][0]
        expected_keys = {
            "group_key",
            "count",
            "p50_latency_ms",
            "p95_latency_ms",
            "avg_cost_estimate",
            "success_rate",
        }
        assert expected_keys <= set(rollup.keys())

    async def test_event_type_group_by_and_filtering(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Test group_by=event_type and event_type filtering."""
        import uuid as _uuid
        from datetime import UTC, datetime
        from decimal import Decimal

        from db.models.metric_event import MetricEventRow

        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        db_session.add(
            MetricEventRow(
                id=_uuid.uuid4(),
                event_type="JobCompleted",
                group_key="trivial",
                duration_ms=1000,
                cost_estimate=Decimal("0"),
                success=True,
                ts=datetime.now(UTC),
            )
        )
        db_session.add(
            MetricEventRow(
                id=_uuid.uuid4(),
                event_type="IngestionCompleted",
                group_key="usgs",
                duration_ms=200,
                cost_estimate=Decimal("0"),
                success=True,
                ts=datetime.now(UTC),
            )
        )
        await db_session.commit()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        # 1. Test group_by=event_type
        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "1d", "group_by": "event_type"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        event_types = {r["group_key"] for r in body["rollups"]}
        assert "JobCompleted" in event_types
        assert "IngestionCompleted" in event_types

        # 2. Test event_type filter
        res_filter = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "1d", "group_by": "event_type", "event_type": "JobCompleted"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_filter.status_code == 200
        filter_body = res_filter.json()
        assert len(filter_body["rollups"]) == 1
        assert filter_body["rollups"][0]["group_key"] == "JobCompleted"

    async def test_invalid_event_type_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Unsupported event_type parameter returns 422."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics",
            params={"window": "7d", "group_by": "complexity_tier", "event_type": "InvalidEvent"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    async def test_admin_gets_prometheus_metrics_text(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """ADMIN user receives 200 with valid OpenMetrics text content."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        admin = await self._create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        res = await client.get(
            "/api/v1/admin/metrics/prometheus",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        text_body = res.text
        assert "# TYPE gaiaos_planner_region_hint_missing_total counter" in text_body
        assert "# TYPE gaiaos_location_regex_fallback_total counter" in text_body
        assert "# TYPE gaiaos_circuit_breaker_state gauge" in text_body
        assert 'gaiaos_circuit_breaker_state{source="usgs"}' in text_body
        assert "gaiaos_queue_depth" in text_body
        assert 'gaiaos_location_regex_fallback_total{agent="seismic"}' in text_body

    async def test_prometheus_metrics_static_token_auth(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        """Static PROMETHEUS_METRICS_TOKEN allows scraping without user authentication."""
        static_token = "my-long-lived-prometheus-scrape-token-12345"
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("PROMETHEUS_METRICS_TOKEN", static_token)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        # 1. Unauthenticated / invalid token fails with 401
        res_fail = await client.get("/api/v1/admin/metrics/prometheus")
        assert res_fail.status_code == 401

        # 2. Valid static token header succeeds with 200
        res_ok = await client.get(
            "/api/v1/admin/metrics/prometheus",
            headers={"Authorization": f"Bearer {static_token}"},
        )
        assert res_ok.status_code == 200
        assert "# TYPE gaiaos_planner_region_hint_missing_total counter" in res_ok.text

