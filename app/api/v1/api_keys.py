"""API Key management router — Phase 3 Milestone 10.

Endpoints:
- POST   /api/v1/api-keys          [RequireRole(RESEARCHER, ADMIN)] -> issue key
- GET    /api/v1/api-keys          [RequireRole(RESEARCHER, ADMIN)] -> list keys
- DELETE /api/v1/api-keys/{key_id} [Owner or ADMIN]                  -> revoke key
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import DbSessionDep
from auth.api_key_provider import generate_key_id, generate_raw_api_key, hash_api_key
from auth.dependencies import CurrentUser, RequireRole, check_owner_or_role
from auth.roles import Role
from db.models.api_key import ApiKey
from db.models.user import User

api_keys_router = APIRouter(prefix="/api-keys", tags=["API Keys"])


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateApiKeyRequest(BaseModel):
    """Payload for issuing a new API key."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable label for this API key (e.g. 'Research CLI Script')",
    )


class ApiKeyCreatedResponse(BaseModel):
    """Response returned when an API key is created.

    `key` is shown ONLY ONCE and cannot be retrieved later.
    """

    id: uuid.UUID
    key_id: str
    name: str
    key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyResponse(BaseModel):
    """Response schema for listing API keys (does NOT contain raw secret key)."""

    id: uuid.UUID
    key_id: str
    name: str
    is_revoked: bool
    created_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyRevokedResponse(BaseModel):
    """Response returned when an API key is revoked."""

    status: str = "revoked"
    key_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@api_keys_router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new API Key",
    description=(
        "Issues a new API key for external consumers. Restricted to RESEARCHER "
        "and ADMIN roles. The raw key is returned ONLY ONCE in this response "
        "and is never stored or retrievable again."
    ),
)
async def create_api_key(
    payload: CreateApiKeyRequest,
    session: DbSessionDep,
    user: User = Depends(RequireRole(Role.RESEARCHER, Role.ADMIN)),
) -> ApiKeyCreatedResponse:
    """Create a new API key for the authenticated researcher or admin."""
    raw_key = generate_raw_api_key()
    key_id = generate_key_id()
    key_hash = hash_api_key(raw_key)

    api_key_row = ApiKey(
        id=uuid.uuid4(),
        key_id=key_id,
        key_hash=key_hash,
        name=payload.name,
        owner_id=user.id,
        is_revoked=False,
        created_at=datetime.now(UTC),
    )
    session.add(api_key_row)
    await session.commit()
    await session.refresh(api_key_row)

    return ApiKeyCreatedResponse(
        id=api_key_row.id,
        key_id=api_key_row.key_id,
        name=api_key_row.name,
        key=raw_key,
        created_at=api_key_row.created_at,
    )


@api_keys_router.get(
    "",
    response_model=list[ApiKeyResponse],
    summary="List API Keys",
    description=(
        "Returns all non-revoked API keys owned by the current user (or all keys "
        "if requested by an ADMIN). Does not return secret key values."
    ),
)
async def list_api_keys(
    session: DbSessionDep,
    user: User = Depends(RequireRole(Role.RESEARCHER, Role.ADMIN)),
) -> list[ApiKeyResponse]:
    """List API keys owned by user or all keys if admin."""
    stmt = select(ApiKey)
    if user.role != Role.ADMIN:
        stmt = stmt.where(ApiKey.owner_id == user.id)
    stmt = stmt.order_by(ApiKey.created_at.desc())

    result = await session.execute(stmt)
    keys = result.scalars().all()
    return [ApiKeyResponse.model_validate(k) for k in keys]


@api_keys_router.delete(
    "/{key_id}",
    response_model=ApiKeyRevokedResponse,
    summary="Revoke an API Key",
    description="Revokes an existing API key by key_id. Restricted to the owner or ADMIN.",
)
async def revoke_api_key(
    key_id: str,
    session: DbSessionDep,
    user: CurrentUser,
) -> ApiKeyRevokedResponse:
    """Revoke an API key."""
    stmt = select(ApiKey).where(ApiKey.key_id == key_id)
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )

    check_owner_or_role(api_key.owner_id, user, Role.ADMIN)

    if not api_key.is_revoked:
        api_key.is_revoked = True
        api_key.revoked_at = datetime.now(UTC)
        await session.commit()

    return ApiKeyRevokedResponse(status="revoked", key_id=key_id)


__all__ = ["api_keys_router"]
