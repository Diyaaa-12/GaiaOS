"""API Key Authentication Provider satisfying gateway.auth_stub.AuthProvider protocol.

Phase 3 Milestone 10: API-key-based access for external consumers.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import select

import db.session as db_session
from db.models.api_key import ApiKey
from db.models.user import User
from logging_config import get_logger

_log = get_logger(__name__)


def generate_raw_api_key() -> str:
    """Generate a fresh random API secret key shown only once to the issuer."""
    return f"gaios_live_{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"


def generate_key_id() -> str:
    """Generate a non-sensitive public identifier for an API key."""
    return f"gaios_key_{uuid.uuid4().hex[:12]}"


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 digest hex string of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyAuthProvider:
    """Authentication provider for X-API-Key header credentials."""

    async def authenticate(self, request: Request) -> None:
        """Inspect X-API-Key header and validate key against the database.

        If X-API-Key is absent: returns without setting user or error state
        so that subsequent providers in the auth chain (JWT) can execute.
        If X-API-Key is present and valid: attaches authenticated owner User
        to request.state.user and stores request.state.api_key_id.
        If X-API-Key is revoked or invalid: sets request.state.api_key_error
        and sets request.state.user = None.
        """
        api_key_header = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if not api_key_header:
            # Fall through to JWT provider
            return

        key_hash = hash_api_key(api_key_header)

        if db_session.AsyncSessionLocal is None:
            _log.warning("auth.api_key.db_not_initialised")
            return

        async with db_session.AsyncSessionLocal() as session:
            stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
            result = await session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if api_key is None:
                _log.warning("auth.api_key.invalid_key")
                request.state.api_key_error = ("invalid_api_key", "Invalid API key.")
                request.state.user = None
                return

            if api_key.is_revoked:
                _log.warning("auth.api_key.revoked_key", key_id=api_key.key_id)
                request.state.api_key_error = ("api_key_revoked", "API key has been revoked.")
                request.state.user = None
                return

            # Query owner user
            user_stmt = select(User).where(User.id == api_key.owner_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if user is None or user.deleted_at is not None or not user.is_active:
                _log.warning("auth.api_key.inactive_owner", key_id=api_key.key_id)
                request.state.api_key_error = (
                    "account_inactive",
                    "User account is inactive or deleted.",
                )
                request.state.user = None
                return

            # Update last_used_at timestamp
            api_key.last_used_at = datetime.now(UTC)
            await session.commit()

            # Attach user and key metadata to request state
            request.state.user = user
            request.state.api_key_id = api_key.key_id
            request.state.auth_type = "api_key"
            _log.info("auth.api_key.success", key_id=api_key.key_id, user_id=str(user.id))


__all__ = [
    "ApiKeyAuthProvider",
    "generate_key_id",
    "generate_raw_api_key",
    "hash_api_key",
]
