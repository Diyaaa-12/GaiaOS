"""CLI script for bootstrapping initial administrator account out-of-band.

Usage:
    python tools/create_admin.py --email admin@gaiaos.ai \
        --password 'AdminSecureP@ss1' --full-name 'System Administrator'
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from auth.password_hashing import hash_password, validate_password_policy
from auth.roles import Role
from config.settings import get_settings
from db.repository import UserRepository
from db.session import AsyncSessionLocal, init_engine
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


async def create_admin(email: str, password: str, full_name: str | None) -> None:
    """Create or promote an administrator account in the database."""
    policy_res = validate_password_policy(password)
    if not policy_res.is_valid:
        print(f"Error: Password policy violation — {policy_res.error_message}", file=sys.stderr)
        sys.exit(1)

    init_engine()
    if AsyncSessionLocal is None:
        print("Error: Could not initialise database session.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        user = await UserRepository.get_user_by_email(session, email)

        hashed_pw = hash_password(password)

        if user:
            user.role = Role.ADMIN.value
            user.is_active = True
            user.is_verified = True
            user.hashed_password = hashed_pw
            if full_name:
                user.full_name = full_name
            await session.commit()
            print(f"Successfully promoted existing user '{email}' to ADMIN role.")
        else:
            await UserRepository.create_user(
                session=session,
                email=email,
                hashed_password=hashed_pw,
                full_name=full_name,
                role=Role.ADMIN.value,
                is_verified=True,
            )
            print(f"Successfully created administrator account for '{email}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap initial administrator account for GaiaOS."
    )
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument(
        "--password", required=False, help="Administrator password (prompted if omitted)"
    )
    parser.add_argument(
        "--full-name",
        required=False,
        help="Administrator full name",
        default="System Administrator",
    )

    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Enter administrator password: ")
        confirm = getpass.getpass("Confirm administrator password: ")
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    settings = get_settings()
    configure_logging(settings)

    asyncio.run(create_admin(args.email, password, args.full_name))


if __name__ == "__main__":
    main()
