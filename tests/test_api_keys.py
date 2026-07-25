"""Unit and integration tests for API Key authentication and management — Phase 3 Milestone 10.

Test strategy (per Roadmap §13):
- Unit: Key generation & SHA-256 hashing functions.
- Unit: Chain fallback logic (API key absent → falls through to JWT).
- Integration: Researcher issues an API key via POST /api/v1/api-keys.
- Integration: Public-role user (USER) blocked from self-issuing API keys (403).
- Integration: External test client using ONLY an API key (zero JWT knowledge)
  submits, polls, and retrieves an investigation.
- Integration: Revoked key is immediately rejected on the next request with
  error_code: "api_key_revoked".
- Edge Case: Both X-API-Key and Authorization JWT present -> API key takes precedence.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.api_key_provider import (
    generate_key_id,
    generate_raw_api_key,
    hash_api_key,
)
from auth.jwt_provider import create_access_token
from auth.roles import Role
from config.settings import get_settings
from db.repository import UserRepository

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(session: AsyncSession, role: Role):
    """Helper to create a verified user with the given role."""
    email = f"{role.value}-{uuid.uuid4().hex[:6]}@gaiaos-test.example"
    return await UserRepository.create_user(
        session=session,
        email=email,
        hashed_password="HashedPassword123!",
        role=role.value,
        is_verified=True,
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestApiKeyUnit:
    """Unit tests for API key generation and hashing functions."""

    async def test_raw_key_format(self) -> None:
        key = generate_raw_api_key()
        assert key.startswith("gaios_live_")
        assert len(key) > 20

    async def test_key_id_format(self) -> None:
        key_id = generate_key_id()
        assert key_id.startswith("gaios_key_")
        assert len(key_id) == 22

    async def test_hash_api_key_deterministic(self) -> None:
        raw_key = "gaios_live_test_12345"
        h1 = hash_api_key(raw_key)
        h2 = hash_api_key(raw_key)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex string length


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestApiKeyEndpoints:
    """Integration tests for POST/GET/DELETE /api/v1/api-keys."""

    async def test_researcher_can_issue_api_key(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """RESEARCHER role user can issue an API key."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        researcher = await _create_user(db_session, Role.RESEARCHER)
        token = create_access_token(researcher.id, researcher.role)

        res = await client.post(
            "/api/v1/api-keys",
            json={"name": "Research Pipeline Key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201
        body = res.json()
        assert "key" in body
        assert body["key"].startswith("gaios_live_")
        assert body["key_id"].startswith("gaios_key_")
        assert body["name"] == "Research Pipeline Key"

    async def test_public_user_blocked_from_issuing_key(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Regular USER role is forbidden from issuing API keys (403)."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        user = await _create_user(db_session, Role.USER)
        token = create_access_token(user.id, user.role)

        res = await client.post(
            "/api/v1/api-keys",
            json={"name": "Attempted User Key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    async def test_external_consumer_flow_using_only_api_key(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """External client using ONLY X-API-Key (zero JWT knowledge) completes submission flow."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        # 1. Researcher issues key
        researcher = await _create_user(db_session, Role.RESEARCHER)
        token = create_access_token(researcher.id, researcher.role)

        issue_res = await client.post(
            "/api/v1/api-keys",
            json={"name": "External Integration"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert issue_res.status_code == 201
        raw_key = issue_res.json()["key"]

        # 2. External client submits investigation using ONLY X-API-Key header
        sub_res = await client.post(
            "/api/v1/investigations",
            json={"query": "Tsunami risk assessment for Pacific coast?"},
            headers={"X-API-Key": raw_key},
        )
        assert sub_res.status_code == 202
        inv_id = sub_res.json()["investigation_id"]

        # 3. External client retrieves investigation using ONLY X-API-Key header
        get_res = await client.get(
            f"/api/v1/investigations/{inv_id}",
            headers={"X-API-Key": raw_key},
        )
        assert get_res.status_code == 200
        assert get_res.json()["investigation_id"] == inv_id

    async def test_revoked_key_immediately_rejected(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """Revoked API key is immediately rejected with error_code: 'api_key_revoked'."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        # Issue key
        admin = await _create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        issue_res = await client.post(
            "/api/v1/api-keys",
            json={"name": "Temporary Key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert issue_res.status_code == 201
        raw_key = issue_res.json()["key"]
        key_id = issue_res.json()["key_id"]

        # Verify key works
        res1 = await client.get(
            "/api/v1/admin/metrics",
            headers={"X-API-Key": raw_key},
        )
        assert res1.status_code == 200

        # Revoke key
        del_res = await client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "revoked"

        # Verify key is rejected on next request
        res2 = await client.get(
            "/api/v1/admin/metrics",
            headers={"X-API-Key": raw_key},
        )
        assert res2.status_code == 401
        body = res2.json()
        assert body["detail"]["error_code"] == "api_key_revoked"

    async def test_api_key_precedence_over_jwt(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ) -> None:
        """When both X-API-Key and Authorization JWT are present, X-API-Key takes precedence."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        # Admin user issues an API key
        admin = await _create_user(db_session, Role.ADMIN)
        token = create_access_token(admin.id, admin.role)

        issue_res = await client.post(
            "/api/v1/api-keys",
            json={"name": "Precedence Test Key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert issue_res.status_code == 201
        raw_key = issue_res.json()["key"]
        key_id = issue_res.json()["key_id"]

        # Revoke the API key
        await client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Valid JWT + REVOKED API KEY -> API key takes precedence -> 401 api_key_revoked
        res = await client.get(
            "/api/v1/admin/metrics",
            headers={
                "Authorization": f"Bearer {token}",
                "X-API-Key": raw_key,
            },
        )
        assert res.status_code == 401
        assert res.json()["detail"]["error_code"] == "api_key_revoked"
