"""JWT Auth Provider satisfying gateway.auth_stub.AuthProvider protocol."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, Request, status

import db.session as db_session
from config.settings import get_settings
from db.repository import UserRepository
from logging_config import get_logger

_log = get_logger(__name__)


def create_access_token(
    user_id: uuid.UUID | str,
    role: str,
    secret_key: str | None = None,
    expiry_minutes: int | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Issue a signed JWT access token with full GaiaOS claim set.

    Payload claims:
    - sub: Subject user ID (str UUID)
    - role: User role string
    - iat: Issued at timestamp (UTC int)
    - exp: Expiration timestamp (UTC int)
    - iss: Token issuer ("gaiaos")
    - aud: Token audience ("gaiaos-api")
    """
    settings = get_settings()
    key = secret_key or settings.jwt_secret_key
    if not key:
        raise ValueError("JWT_SECRET_KEY must be set to issue access tokens.")

    alg = algorithm or settings.jwt_algorithm
    exp_mins = expiry_minutes or settings.jwt_expiry_minutes
    iss = issuer or settings.jwt_issuer
    aud = audience or settings.jwt_audience

    now = datetime.now(UTC)
    expires = now + timedelta(minutes=exp_mins)

    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": iss,
        "aud": aud,
    }

    return jwt.encode(payload, key, algorithm=alg)


def decode_access_token(token: str, secret_key: str | None = None) -> dict[str, Any]:
    """Decode and validate JWT access token claims.

    Validates signature, expiration, issuer (iss), and audience (aud).
    Raises jwt.PyJWTError subclasses on failure.
    """
    settings = get_settings()
    key = secret_key or settings.jwt_secret_key
    if not key:
        raise ValueError("JWT_SECRET_KEY is not configured.")

    return jwt.decode(
        token,
        key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


class JWTAuthProvider:
    """Production AuthProvider implementation.

    Satisfies ``gateway.auth_stub.AuthProvider`` protocol without exposing
    JWT internals to the Gateway layer.
    """

    async def authenticate(self, request: Request) -> None:
        """Validate Bearer token credentials from request headers.

        Attaches authenticated principal model to ``request.state.user``.
        """
        settings = get_settings()

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            if not settings.enable_auth:
                request.state.user = None
                return
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = parts[1]

        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            _log.warning("auth.jwt.expired_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        except jwt.InvalidTokenError as exc:
            _log.warning("auth.jwt.invalid_token", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            user_uuid = uuid.UUID(sub)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user identity claim.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")

        async with db_session.AsyncSessionLocal() as session:
            user = await UserRepository.get_user_by_id(session, user_uuid)

        if not user or user.deleted_at is not None:
            _log.warning("auth.jwt.user_not_found", user_id=sub)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            _log.warning("auth.jwt.inactive_user", user_id=sub)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_verified:
            _log.warning("auth.jwt.unverified_user", user_id=sub)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email address is not verified.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Attach validated user model to request state
        request.state.user = user
