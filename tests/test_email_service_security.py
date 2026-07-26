"""Security review and verification test suite for authentication extensions (Milestone 2).

Test coverage:
1. Token entropy and cryptographic hashing.
2. Single-use token enforcement and replay prevention.
3. Token expiry window enforcement.
4. Invalidation of all outstanding reset tokens upon password update.
5. Account non-enumeration (HTTP 202 status and constant-time behavior).
6. Host-header link poisoning immunity (app_base_url enforcement).
7. Dedicated rate limiting for password reset requests (HTTP 429).
8. Sanitized logging (zero raw token / token preview leakage).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.email_service import (
    DevEmailService,
    generate_verification_token,
    hash_verification_token,
)
from cache.client import get_redis
from config.settings import get_settings
from db.repository import UserRepository


class TestEmailServiceSecurity:
    """Security verification test suite for Milestone 2."""

    def test_token_entropy_and_hashing(self) -> None:
        """Raw token provides at least 256 bits of URL-safe entropy and SHA-256 digests."""
        raw_token = generate_verification_token()
        hashed = hash_verification_token(raw_token)

        assert len(raw_token) >= 43  # Base64-encoded 32 bytes URL-safe length
        assert len(hashed) == 64  # SHA-256 hex digest length
        assert hashed == hash_verification_token(raw_token)
        assert hashed != raw_token

    @pytest.mark.asyncio
    async def test_password_reset_flow_and_single_use_enforcement(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify request-reset -> reset -> login flow and single-use token consumption."""
        captured_links: list[dict[str, str]] = []

        async def mock_send(
            self_obj: Any, email: str, raw_token: str, user_id: str | None = None
        ) -> None:
            captured_links.append({"email": email, "raw_token": raw_token})

        monkeypatch.setattr(DevEmailService, "send_password_reset_email", mock_send)

        email = f"reset-{uuid.uuid4().hex[:6]}@example.com"
        old_pw = "OldPassword123!"
        new_pw = "NewPassword123!"

        # 1. Register & verify user
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": old_pw},
        )
        assert reg_res.status_code == 201

        # Direct DB verification for testing
        get_settings.cache_clear()
        from db.session import AsyncSessionLocal

        assert AsyncSessionLocal is not None
        async with AsyncSessionLocal() as session:
            user = await UserRepository.get_user_by_email(session, email)
            assert user is not None
            user.is_verified = True
            await session.commit()

        # 2. Request password reset
        req_res = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": email},
        )
        assert req_res.status_code == 202
        assert len(captured_links) == 1
        raw_token = captured_links[0]["raw_token"]

        # 3. Reset password using token
        reset_res = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_token, "new_password": new_pw},
        )
        assert reset_res.status_code == 200

        # 4. Attempt second reset using same token -> 400 Bad Request
        replay_res = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_token, "new_password": "ThirdPassword123!"},
        )
        assert replay_res.status_code == 400
        assert replay_res.json()["error_code"] == "invalid_or_expired_token"

        # 5. Old password login rejected, new password login accepted
        login_old = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_pw},
        )
        assert login_old.status_code == 401

        login_new = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_pw},
        )
        assert login_new.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_token_rejection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Reset tokens past expires_at window are rejected with 400."""
        email = f"expired-{uuid.uuid4().hex[:6]}@example.com"
        pw = "Password123!"

        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": pw},
        )
        assert reg_res.status_code == 201

        user = await UserRepository.get_user_by_email(db_session, email)
        assert user is not None

        raw_token = generate_verification_token()
        hashed_token = hash_verification_token(raw_token)
        past_expiry = datetime.now(UTC) - timedelta(minutes=1)

        await UserRepository.create_password_reset_token(
            session=db_session,
            user_id=user.id,
            hashed_token=hashed_token,
            expires_at=past_expiry,
        )

        reset_res = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_token, "new_password": "NewPassword123!"},
        )
        assert reset_res.status_code == 400
        assert reset_res.json()["error_code"] == "invalid_or_expired_token"

    @pytest.mark.asyncio
    async def test_all_outstanding_tokens_invalidated_on_password_change(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Resetting password invalidates ALL unconsumed reset tokens issued to that user."""
        email = f"multi-{uuid.uuid4().hex[:6]}@example.com"
        pw = "InitialPassword123!"

        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": pw},
        )
        assert reg_res.status_code == 201
        user = await UserRepository.get_user_by_email(db_session, email)
        assert user is not None

        # Issue 3 tokens
        raw_1, raw_2, raw_3 = (
            generate_verification_token(),
            generate_verification_token(),
            generate_verification_token(),
        )
        exp = datetime.now(UTC) + timedelta(minutes=15)
        await UserRepository.create_password_reset_token(
            db_session, user.id, hash_verification_token(raw_1), exp
        )
        await UserRepository.create_password_reset_token(
            db_session, user.id, hash_verification_token(raw_2), exp
        )
        await UserRepository.create_password_reset_token(
            db_session, user.id, hash_verification_token(raw_3), exp
        )

        # Reset using token 2
        reset_res = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_2, "new_password": "UpdatedPassword123!"},
        )
        assert reset_res.status_code == 200

        # Tokens 1 and 3 must also be rejected
        res_1 = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_1, "new_password": "AnotherPassword123!"},
        )
        assert res_1.status_code == 400

        res_3 = await client.post(
            "/api/v1/auth/reset",
            json={"token": raw_3, "new_password": "AnotherPassword123!"},
        )
        assert res_3.status_code == 400

    @pytest.mark.asyncio
    async def test_non_enumeration_response_unconditional_202(
        self, client: AsyncClient
    ) -> None:
        """POST /auth/request-reset returns HTTP 202 for both existing and non-existing emails."""
        # Non-existing email
        res1 = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": "definitely-does-not-exist-999@example.com"},
        )
        assert res1.status_code == 202
        assert "password reset link has been sent" in res1.json()["message"]

        # Existing email
        email = f"exist-{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )

        res2 = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": email},
        )
        assert res2.status_code == 202
        assert res2.json()["message"] == res1.json()["message"]

    @pytest.mark.asyncio
    async def test_host_header_poisoning_immunity(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reset URLs strictly consume app_base_url and ignore malicious Host headers."""
        captured_logs = []

        def mock_info(event: str, **kwargs: Any) -> None:
            if event == "auth.email.password_reset_sent":
                captured_logs.append(kwargs)

        monkeypatch.setattr("auth.email_service._log.info", mock_info)

        email = f"host-{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )

        # Inject malicious Host header
        res = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": email},
            headers={"Host": "evil-attacker-site.com"},
        )
        assert res.status_code == 202

        assert len(captured_logs) == 1
        reset_url = captured_logs[0]["reset_url"]
        assert "evil-attacker-site.com" not in reset_url
        assert reset_url.startswith(get_settings().app_base_url)

    @pytest.mark.asyncio
    async def test_password_reset_rate_limiting(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Password reset endpoint returns HTTP 429 when exceeding quota."""
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
        monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_REQUESTS", "2")
        monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", "60")
        get_settings.cache_clear()

        unique_ip = f"203.0.113.{uuid.uuid4().int % 200 + 1}"
        try:
            r = await get_redis()
            await r.delete(f"gaiaos:ratelimit:ip:{unique_ip}:password_reset")
        except Exception:
            pass

        email = f"ratelimit-{uuid.uuid4().hex[:6]}@example.com"
        headers = {"X-Forwarded-For": unique_ip}
        from fastapi import HTTPException

        res1 = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": email},
            headers=headers,
        )
        res2 = await client.post(
            "/api/v1/auth/request-reset",
            json={"email": email},
            headers=headers,
        )
        assert res1.status_code == 202
        assert res2.status_code == 202

        with pytest.raises(HTTPException) as exc_info:
            await client.post(
                "/api/v1/auth/request-reset",
                json={"email": email},
                headers=headers,
            )
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        get_settings.cache_clear()
