"""FastAPI Dependency Injection helpers for Authentication and Authorization."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from auth.roles import Role
from db.models.user import User
from logging_config import get_logger

_log = get_logger(__name__)


async def get_current_user(request: Request) -> User:
    """Retrieve current authenticated user from request state.

    Raises 401 if request state lacks an authenticated user.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure current authenticated user is active and email verified."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
        )
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email address is not verified.",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_active_user)]


def RequireRole(*allowed_roles: Role) -> Callable:
    """FastAPI dependency factory to enforce role-based access control.

    ADMIN role automatically bypasses specific role restrictions.
    """

    async def _role_checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role == Role.ADMIN or user.role in allowed_roles:
            return user
        _log.warning(
            "auth.role_denied", user_id=str(user.id), role=user.role, allowed=allowed_roles
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this resource.",
        )

    return _role_checker


def check_owner_or_role(
    resource_user_id: uuid.UUID | None,
    current_user: User,
    *allowed_roles: Role,
) -> None:
    """Helper function to check resource ownership or role authorization.

    Raises 403 HTTP Exception if user is neither owner nor holds an allowed role (e.g. ADMIN).
    """
    if current_user.role == Role.ADMIN or current_user.role in allowed_roles:
        return
    if resource_user_id is not None and resource_user_id == current_user.id:
        return

    _log.warning(
        "auth.ownership_denied",
        user_id=str(current_user.id),
        resource_user_id=str(resource_user_id) if resource_user_id else None,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this resource.",
    )
