"""Authentication and user lifecycle routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from app.dependencies import DbSessionDep
from auth.dependencies import get_current_active_user
from auth.email_service import (
    DevEmailService,
    generate_verification_token,
    hash_verification_token,
)
from auth.jwt_provider import create_access_token
from auth.password_hashing import hash_password, validate_password_policy, verify_password
from auth.roles import Role
from config.settings import get_settings
from db.models.user import User
from db.repository import UserRepository
from logging_config import get_logger

_log = get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


class UserRegisterRequest(BaseModel):
    """Payload to register a new user account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLoginRequest(BaseModel):
    """Payload for account login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT Token response container."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Public user identity response payload."""

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthMessageResponse(BaseModel):
    """Standardized response message container."""

    message: str
    status: str = "success"


class ResendVerificationRequest(BaseModel):
    """Payload to request resending email verification link."""

    email: str


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email already exists"},
        422: {"description": "Password policy or validation error"},
    },
)
async def register(
    payload: UserRegisterRequest,
    db_session: DbSessionDep,
) -> Any:
    """Register a new user account.

    Enforces password strength policy and duplicate email checks.
    Issues a hashed verification token and triggers verification email delivery.
    """
    # 1. Password strength validation
    policy_result = validate_password_policy(payload.password)
    if not policy_result.is_valid:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": policy_result.error_message,
                "error_code": "password_policy_violation",
            },
        )

    # 2. Check for duplicate email (409 Conflict)
    existing_user = await UserRepository.get_user_by_email(db_session, payload.email)
    if existing_user:
        _log.warning("auth.register.duplicate_email", email=payload.email)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "An account with this email already exists.",
                "error_code": "email_already_exists",
            },
        )

    # 3. Hash password and generate hashed verification token
    hashed_pw = hash_password(payload.password)
    raw_token = generate_verification_token()
    hashed_token = hash_verification_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(hours=24)

    # 4. Create user record
    user = await UserRepository.create_user(
        session=db_session,
        email=payload.email,
        hashed_password=hashed_pw,
        full_name=payload.full_name,
        role=Role.USER.value,
        is_verified=False,
        hashed_verification_token=hashed_token,
        verification_token_expires_at=expires_at,
    )

    # 5. Dispatch verification email (Dev logger implementation)
    email_service = DevEmailService()
    await email_service.send_verification_email(user.email, raw_token)

    _log.info("auth.register.success", user_id=str(user.id), email=user.email)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"description": "Invalid credentials, inactive account, or unverified email"},
    },
)
async def login(
    payload: UserLoginRequest,
    db_session: DbSessionDep,
) -> Any:
    """Authenticate user credentials and issue a JWT access token.

    Rejects inactive or unverified users. Never logs passwords or secrets.
    """
    settings = get_settings()
    user = await UserRepository.get_user_by_email(db_session, payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        _log.warning("auth.login.failed_credentials", email_attempted=payload.email)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Invalid email or password.",
                "error_code": "invalid_credentials",
            },
        )

    if not user.is_active:
        _log.warning("auth.login.inactive_account", user_id=str(user.id))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "User account is inactive.",
                "error_code": "account_inactive",
            },
        )

    if not user.is_verified:
        _log.warning("auth.login.unverified_email", user_id=str(user.id))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Email address is not verified.",
                "error_code": "email_unverified",
            },
        )

    # Update last_login_at
    await UserRepository.update_last_login(db_session, user.id)

    # Generate JWT
    token = create_access_token(user.id, user.role)

    _log.info("auth.login.success", user_id=str(user.id))

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiry_minutes * 60,
    )


@auth_router.get(
    "/verify-email",
    response_model=AuthMessageResponse,
    responses={
        400: {"description": "Invalid or expired verification token"},
    },
)
async def verify_email(
    db_session: DbSessionDep,
    token: str = Query(..., description="Email verification token"),
) -> Any:
    """Verify account email via URL verification token (GET link)."""
    hashed_token = hash_verification_token(token)
    user = await UserRepository.get_user_by_hashed_verification_token(db_session, hashed_token)

    if not user or user.verification_token_expires_at is None:
        _log.warning("auth.verify_email.invalid_token")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Invalid or expired verification token.",
                "error_code": "invalid_verification_token",
            },
        )

    now = datetime.now(UTC)
    if user.verification_token_expires_at < now:
        _log.warning("auth.verify_email.expired_token", user_id=str(user.id))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Verification token has expired.",
                "error_code": "verification_token_expired",
            },
        )

    await UserRepository.verify_user_email(db_session, user)
    _log.info("auth.verify_email.success", user_id=str(user.id))

    return AuthMessageResponse(
        message="Email address verified successfully.",
        status="success",
    )


@auth_router.post(
    "/resend-verification",
    response_model=AuthMessageResponse,
)
async def resend_verification(
    payload: ResendVerificationRequest,
    db_session: DbSessionDep,
) -> Any:
    """Resend email verification link for unverified accounts."""
    user = await UserRepository.get_user_by_email(db_session, payload.email)

    if user and not user.is_verified and user.is_active:
        raw_token = generate_verification_token()
        hashed_token = hash_verification_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(hours=24)

        await UserRepository.update_verification_token(
            session=db_session,
            user=user,
            hashed_token=hashed_token,
            expires_at=expires_at,
        )

        email_service = DevEmailService()
        await email_service.send_verification_email(user.email, raw_token)
        _log.info("auth.resend_verification.sent", user_id=str(user.id))

    # Generic response to prevent account enumeration
    return AuthMessageResponse(
        message=(
            "If an unverified account exists with that email, a verification link has been sent."
        ),
        status="success",
    )


@auth_router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retrieve profile details for current authenticated user."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


class PasswordResetRequestPayload(BaseModel):
    """Payload to initiate a password reset."""

    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    """Payload to confirm password reset with raw token and new password."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


@auth_router.post(
    "/request-reset",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset link",
    description=(
        "Initiates password reset flow. Returns HTTP 202 with generic response "
        "regardless of whether the email exists to prevent account enumeration."
    ),
)
async def request_password_reset(
    payload: PasswordResetRequestPayload,
    db_session: DbSessionDep,
) -> Any:
    """Request password reset link.

    Security features:
    1. Account non-enumeration: returns HTTP 202 Accepted unconditionally.
    2. Constant-time execution: performs dummy token generation/hashing if user missing.
    3. Host-header poisoning safety: uses app_base_url for reset links.
    4. Sanitized logging: logs user_id/email, NEVER raw token.
    """
    settings = get_settings()
    user = await UserRepository.get_user_by_email(db_session, payload.email)

    if user and user.is_active:
        raw_token = generate_verification_token()
        hashed_token = hash_verification_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_expiry_minutes)

        await UserRepository.create_password_reset_token(
            session=db_session,
            user_id=user.id,
            hashed_token=hashed_token,
            expires_at=expires_at,
        )

        email_service = DevEmailService()
        await email_service.send_password_reset_email(
            email=user.email,
            raw_token=raw_token,
            user_id=str(user.id),
        )
        _log.info("auth.request_reset.success", user_id=str(user.id))
    else:
        # Constant-time dummy cryptographic work for non-existent accounts
        dummy_raw = generate_verification_token()
        _ = hash_verification_token(dummy_raw)
        _log.info("auth.request_reset.processed")

    return AuthMessageResponse(
        message="If an account with this email exists, a password reset link has been sent.",
        status="success",
    )


@auth_router.post(
    "/reset",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using valid reset token",
    responses={
        400: {"description": "Invalid or expired token"},
        422: {"description": "Password policy violation"},
    },
)
async def reset_password(
    payload: PasswordResetConfirmPayload,
    db_session: DbSessionDep,
) -> Any:
    """Reset account password using plaintext token and new password.

    Security features:
    1. Validates password strength policy.
    2. Hashes new password with Argon2id.
    3. Single transaction boundary: validates token, updates user password, consumes token,
       and invalidates ALL remaining active tokens for the user atomically (SELECT FOR UPDATE).
    """
    # 1. Password strength policy validation
    policy_result = validate_password_policy(payload.new_password)
    if not policy_result.is_valid:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": policy_result.error_message,
                "error_code": "password_policy_violation",
            },
        )

    # 2. Hash raw token and new password
    hashed_token = hash_verification_token(payload.token)
    new_hashed_pw = hash_password(payload.new_password)

    # 3. Atomic reset execution via repository
    user = await UserRepository.reset_password_with_token(
        session=db_session,
        hashed_token=hashed_token,
        new_hashed_password=new_hashed_pw,
    )

    if not user:
        _log.warning("auth.reset.invalid_or_expired_token")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Invalid or expired password reset token.",
                "error_code": "invalid_or_expired_token",
            },
        )

    _log.info("auth.reset.success", user_id=str(user.id))

    return AuthMessageResponse(
        message="Password has been reset successfully. Please log in with your new password.",
        status="success",
    )
