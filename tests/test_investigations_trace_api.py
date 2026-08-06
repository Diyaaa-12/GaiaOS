"""Integration tests for GET /api/v1/investigations/{id}/trace explainability endpoint."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_provider import create_access_token
from auth.roles import Role
from config.settings import get_settings
from db.repository import InvestigationRepository, UserRepository


@pytest.mark.asyncio
class TestInvestigationsTraceAPI:
    """Verifies retrieval, authorization, 404, and response schema of trace endpoint."""

    async def _create_user_headers(
        self,
        session: AsyncSession,
        role: str = Role.USER.value,
        monkeypatch: pytest.MonkeyPatch | None = None,
    ) -> tuple[uuid.UUID, dict[str, str]]:
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        if monkeypatch is not None:
            monkeypatch.setenv("JWT_SECRET_KEY", key)
            get_settings.cache_clear()

        email = f"traceuser-{uuid.uuid4().hex[:6]}@example.com"
        user = await UserRepository.create_user(
            session=session,
            email=email,
            hashed_password="HashedPassword123!",
            role=role,
            is_verified=True,
        )
        token = create_access_token(user.id, user.role, secret_key=key)
        return user.id, {"Authorization": f"Bearer {token}"}

    async def test_get_investigation_trace_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user_id, headers = await self._create_user_headers(
            db_session, role=Role.USER.value, monkeypatch=monkeypatch
        )

        inv = await InvestigationRepository.create_investigation(
            session=db_session,
            query="What is the atmospheric PM2.5 in Paris?",
            user_id=user_id,
        )
        await InvestigationRepository.update_investigation_status(
            session=db_session,
            investigation_id=inv.id,
            status="complete",
            complexity_tier="moderate",
            answer="PM2.5 levels are normal.",
            confidence=0.9,
            execution_trace={
                "nodes_executed": ["supervisor", "air_quality", "synthesis", "critic", "finalize"],
                "evidence_count": 2,
            },
        )

        response = await client.get(f"/api/v1/investigations/{inv.id}/trace", headers=headers)
        assert response.status_code == 200
        data = response.json()

        assert data["schema_version"] == "1.0"
        assert data["investigation_id"] == str(inv.id)

        meta = data["metadata"]
        assert meta["schema_version"] == "1.0"
        assert meta["generated_at"] is not None
        assert meta["status"] == "complete"
        assert meta["complexity_tier"] == "moderate"
        assert meta["node_count"] == 5
        assert meta["edge_count"] == 4

        summary = data["summary"]
        assert summary["evidence_count"] == 2

        nodes = data["nodes"]
        assert len(nodes) == 5
        node_labels = [n["label"] for n in nodes]
        assert "Supervisor Planner" in node_labels
        assert "Cross-Domain Synthesis" in node_labels

    async def test_get_investigation_trace_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, headers = await self._create_user_headers(db_session, monkeypatch=monkeypatch)
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/investigations/{fake_id}/trace", headers=headers)
        assert response.status_code == 404
        assert response.json()["error_code"] == "investigation_not_found"

    async def test_get_investigation_trace_rbac_forbidden(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Other non-admin user cannot access another user's investigation trace."""
        user1_id, _ = await self._create_user_headers(
            db_session, role=Role.USER.value, monkeypatch=monkeypatch
        )
        _, user2_headers = await self._create_user_headers(
            db_session, role=Role.USER.value, monkeypatch=monkeypatch
        )

        inv = await InvestigationRepository.create_investigation(
            session=db_session,
            query="Private user investigation",
            user_id=user1_id,
        )

        response = await client.get(
            f"/api/v1/investigations/{inv.id}/trace", headers=user2_headers
        )
        assert response.status_code == 403

    async def test_get_investigation_trace_admin_allowed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Admin user can access any user's investigation trace."""
        user1_id, _ = await self._create_user_headers(
            db_session, role=Role.USER.value, monkeypatch=monkeypatch
        )
        _, admin_headers = await self._create_user_headers(
            db_session, role=Role.ADMIN.value, monkeypatch=monkeypatch
        )

        inv = await InvestigationRepository.create_investigation(
            session=db_session,
            query="User query for admin inspection",
            user_id=user1_id,
        )
        await InvestigationRepository.update_investigation_status(
            session=db_session,
            investigation_id=inv.id,
            status="complete",
            execution_trace={"nodes_executed": ["supervisor", "finalize"]},
        )

        response = await client.get(
            f"/api/v1/investigations/{inv.id}/trace", headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["schema_version"] == "1.0"
