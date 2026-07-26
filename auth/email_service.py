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
    """Protocol for email verification and password reset delivery."""

    async def send_verification_email(self, email: str, raw_token: str) -> None:
        """Deliver email verification link to user."""
        ...

    async def send_password_reset_email(
        self, email: str, raw_token: str, user_id: str | None = None
    ) -> None:
        """Deliver password reset link to user."""
        ...


class DevEmailService:
    """Development email service implementation that logs delivery events."""

    async def send_verification_email(self, email: str, raw_token: str) -> None:
        """Log the verification URL for local dev testing."""
        from config.settings import get_settings

        settings = get_settings()
        verification_url = f"{settings.app_base_url}/api/v1/auth/verify-email?token={raw_token}"
        _log.info(
            "auth.email.verification_sent",
            email=email,
            verification_url=verification_url,
        )

    async def send_password_reset_email(
        self, email: str, raw_token: str, user_id: str | None = None
    ) -> None:
        """Log password reset link using configured app_base_url (prevents host-header poisoning).

        Security requirement: Raw tokens and token previews are NEVER logged.
        Only user_id / email and the target reset URL are logged in dev environments.
        """
        from config.settings import get_settings

        settings = get_settings()
        reset_url = f"{settings.app_base_url}/api/v1/auth/reset?token={raw_token}"
        _log.info(
            "auth.email.password_reset_sent",
            user_id=user_id,
            email=email,
            reset_url=reset_url,
        )
