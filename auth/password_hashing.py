"""Password hashing and strength validation using Argon2id.

Isolated module to ensure argon2 library imports are confined to auth package.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from logging_config import get_logger

_log = get_logger(__name__)

# Initialize Argon2id password hasher with production-grade parameters
_ph = PasswordHasher()


class PasswordPolicyResult(NamedTuple):
    is_valid: bool
    error_message: str | None


def validate_password_policy(password: str) -> PasswordPolicyResult:
    """Validate password against GaiaOS policy requirements.

    Policy:
    - Minimum 8 characters
    - At least 1 uppercase letter (A-Z)
    - At least 1 lowercase letter (a-z)
    - At least 1 digit (0-9)
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    """
    if len(password) < 8:
        return PasswordPolicyResult(
            is_valid=False,
            error_message="Password must be at least 8 characters long.",
        )
    if not re.search(r"[A-Z]", password):
        return PasswordPolicyResult(
            is_valid=False,
            error_message="Password must contain at least one uppercase letter.",
        )
    if not re.search(r"[a-z]", password):
        return PasswordPolicyResult(
            is_valid=False,
            error_message="Password must contain at least one lowercase letter.",
        )
    if not re.search(r"[0-9]", password):
        return PasswordPolicyResult(
            is_valid=False,
            error_message="Password must contain at least one digit.",
        )
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        return PasswordPolicyResult(
            is_valid=False,
            error_message="Password must contain at least one special character.",
        )

    return PasswordPolicyResult(is_valid=True, error_message=None)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id.

    Never logs the password.
    """
    return _ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify plaintext password against Argon2id hash.

    Returns True if valid, False otherwise.  Never logs raw password or secret.
    """
    try:
        return _ph.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
    except Exception as exc:
        _log.error("auth.password_hashing.unexpected_error", error=str(exc))
        return False
