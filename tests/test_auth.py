"""Unit and integration tests for Authentication and Authorization (Milestone 1)."""

from __future__ import annotations

import uuid

import jwt
import pytest
from httpx import AsyncClient

from auth.email_service import generate_verification_token, hash_verification_token
from auth.jwt_provider import create_access_token, decode_access_token
from auth.password_hashing import hash_password, validate_password_policy, verify_password
from auth.roles import Role
from config.settings import get_settings


class TestPasswordHashingAndPolicy:
    """Unit tests for password policy enforcement and Argon2id hashing."""

    def test_password_policy_enforcement(self) -> None:
        """Password policy requires length >= 8, uppercase, lowercase, digit, and special char."""
        assert not validate_password_policy("short").is_valid
        assert not validate_password_policy("nouppercase1!").is_valid
        assert not validate_password_policy("NOLOWERCASE1!").is_valid
        assert not validate_password_policy("NoDigitsHere!").is_valid
        assert not validate_password_policy("NoSpecial123").is_valid

        valid_res = validate_password_policy("Valid123!@#")
        assert valid_res.is_valid
        assert valid_res.error_message is None

    def test_argon2id_hashing_and_verification(self) -> None:
        """Verify Argon2id hash generation and password verification."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword123!", hashed)


class TestVerificationTokenHashing:
    """Unit tests for token hashing logic."""

    def test_token_hashing_sha256(self) -> None:
        """Verification tokens are hashed using SHA-256."""
        raw_token = generate_verification_token()
        hashed = hash_verification_token(raw_token)

        assert len(raw_token) >= 32
        assert len(hashed) == 64  # SHA-256 hex digest length
        assert hashed == hash_verification_token(raw_token)
        assert hashed != raw_token


class TestJWTClaimsAndValidation:
    """Unit tests for JWT generation and claims validation."""

    def test_create_and_decode_jwt_token(self, monkeypatch) -> None:
        """JWT access token contains sub, role, iat, exp, iss, aud."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        get_settings.cache_clear()
        settings = get_settings()

        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id, role=Role.USER.value, secret_key=key)

        payload = decode_access_token(token, secret_key=key)

        assert payload["sub"] == str(user_id)
        assert payload["role"] == Role.USER.value
        assert payload["iss"] == settings.jwt_issuer
        assert payload["aud"] == settings.jwt_audience
        assert "iat" in payload
        assert "exp" in payload

    def test_invalid_issuer_rejected(self, monkeypatch) -> None:
        """JWT decoder rejects tokens with mismatched issuer."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        get_settings.cache_clear()

        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=user_id, role=Role.USER.value, secret_key=key, issuer="wrong-issuer"
        )

        with pytest.raises(jwt.InvalidIssuerError):
            decode_access_token(token, secret_key=key)

    def test_invalid_audience_rejected(self, monkeypatch) -> None:
        """JWT decoder rejects tokens with mismatched audience."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        get_settings.cache_clear()

        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=user_id, role=Role.USER.value, secret_key=key, audience="wrong-audience"
        )

        with pytest.raises(jwt.InvalidAudienceError):
            decode_access_token(token, secret_key=key)


class TestAuthAPIEndpoints:
    """Integration tests for Auth API routes."""

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        """Registering an existing email returns HTTP 409 Conflict."""
        email = f"duplicate-{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "email": email,
            "password": "ValidPassword123!",
            "full_name": "Test User",
        }

        res1 = await client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        res2 = await client.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == 409
        body = res2.json()
        assert body["error_code"] == "email_already_exists"

    async def test_unverified_user_cannot_login(self, client: AsyncClient) -> None:
        """Unverified accounts are blocked from logging in with HTTP 401."""
        email = f"unverified-{uuid.uuid4().hex[:6]}@example.com"
        password = "ValidPassword123!"

        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert reg_res.status_code == 201

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 401
        body = login_res.json()
        assert body["error_code"] == "email_unverified"

    async def test_register_verify_and_login_flow(self, client: AsyncClient, monkeypatch) -> None:
        """Complete register -> verify via GET link -> login -> /me flow."""
        key = "super-secret-key-that-is-at-least-32-chars-long!"
        monkeypatch.setenv("JWT_SECRET_KEY", key)
        monkeypatch.setenv("ENABLE_AUTH", "true")
        get_settings.cache_clear()

        captured_tokens = []

        from auth.email_service import DevEmailService

        async def mock_send(self, email: str, raw_token: str) -> None:
            captured_tokens.append(raw_token)

        monkeypatch.setattr(DevEmailService, "send_verification_email", mock_send)

        email = f"flow-{uuid.uuid4().hex[:6]}@example.com"
        password = "ValidPassword123!"

        # 1. Register
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Flow User"},
        )
        assert reg_res.status_code == 201
        assert len(captured_tokens) == 1
        raw_token = captured_tokens[0]

        # 2. Verify via GET endpoint
        verify_res = await client.get(f"/api/v1/auth/verify-email?token={raw_token}")
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "success"

        # 3. Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        access_token = token_data["access_token"]

        # 4. Access /me
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_res.status_code == 200
        me_body = me_res.json()
        assert me_body["email"] == email
        assert me_body["is_verified"] is True
        assert me_body["last_login_at"] is not None
