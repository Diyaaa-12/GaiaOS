"""Integration tests for Investigation Ownership and Role Authorization (Milestone 1)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_provider import create_access_token
from auth.roles import Role
from config.settings import get_settings
from db.repository import UserRepository


class TestInvestigationOwnership:
    """Ownership and Role Access tests for investigations."""

    async def _create_verified_user(
        self, session: AsyncSession, email: str, role: str = Role.USER.value
    ):
        user = await UserRepository.create_user(
            session=session,
            email=email,
            hashed_password="HashedPassword123!",
            role=role,
            is_verified=True,
        )
        return user

    async def test_investigation_creation_attaches_user_id(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Creating an investigation when authenticated attaches current_user.id."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        user = await self._create_verified_user(
            db_session, f"owner-{uuid.uuid4().hex[:6]}@example.com"
        )
        token = create_access_token(user.id, user.role)

        res = await client.post(
            "/api/v1/investigations",
            json={"query": "What is the seismic risk in Tokyo?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 202
        inv_id = uuid.UUID(res.json()["investigation_id"])

        # Fetch investigation
        get_res = await client.get(
            f"/api/v1/investigations/{inv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200

    async def test_non_owner_forbidden_from_accessing_investigation(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Non-owner user gets HTTP 403 Forbidden when fetching another user's investigation."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        owner = await self._create_verified_user(
            db_session, f"owner-{uuid.uuid4().hex[:6]}@example.com"
        )
        other = await self._create_verified_user(
            db_session, f"other-{uuid.uuid4().hex[:6]}@example.com"
        )

        owner_token = create_access_token(owner.id, owner.role)
        other_token = create_access_token(other.id, other.role)

        # Owner creates investigation
        res = await client.post(
            "/api/v1/investigations",
            json={"query": "Flood risks in Jakarta?"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res.status_code == 202
        inv_id = res.json()["investigation_id"]

        # Other user attempts to fetch investigation -> 403
        get_res = await client.get(
            f"/api/v1/investigations/{inv_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert get_res.status_code == 403

        # Other user attempts to stream investigation -> 403
        stream_res = await client.get(
            f"/api/v1/investigations/{inv_id}/stream",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert stream_res.status_code == 403

    async def test_admin_can_access_any_investigation(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Admin user can access any user's investigation."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        owner = await self._create_verified_user(
            db_session, f"owner-{uuid.uuid4().hex[:6]}@example.com"
        )
        admin = await self._create_verified_user(
            db_session, f"admin-{uuid.uuid4().hex[:6]}@example.com", role=Role.ADMIN.value
        )

        owner_token = create_access_token(owner.id, owner.role)
        admin_token = create_access_token(admin.id, admin.role)

        # Owner creates investigation
        res = await client.post(
            "/api/v1/investigations",
            json={"query": "Wildfire risk in California?"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res.status_code == 202
        inv_id = res.json()["investigation_id"]

        # Admin fetches investigation -> 200
        get_res = await client.get(
            f"/api/v1/investigations/{inv_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_res.status_code == 200

