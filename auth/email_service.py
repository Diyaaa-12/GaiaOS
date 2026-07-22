"""Email verification service protocol and development implementation."""

from __future__ import annotations

import hashlib
import secrets
from typing import Protocol, runtime_checkable

from logging_config import get_logger

_log = get_logger(__name__)


def generate_verification_token() -> str:
    """Generate a secure, URL-safe random verification token."""
    return secrets.token_urlsafe(32)


def hash_verification_token(raw_token: str) -> str:
    """Hash plaintext verification token using SHA-256 for safe DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@runtime_checkable
class EmailService(Protocol):
    """Protocol for email verification delivery."""

    async def send_verification_email(self, email: str, raw_token: str) -> None:
        """Deliver email verification link to user."""
        ...


class DevEmailService:
    """Development email service implementation that logs verification links."""

    async def send_verification_email(self, email: str, raw_token: str) -> None:
        """Log the verification URL and raw token for local dev testing."""
        verification_url = f"/api/v1/auth/verify-email?token={raw_token}"
        _log.info(
            "auth.email.verification_sent",
            email=email,
            verification_url=verification_url,
            token_preview=f"{raw_token[:6]}...",
        )
