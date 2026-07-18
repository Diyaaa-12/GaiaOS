"""Declarative base for SQLAlchemy ORM models.

All domain model classes inherit from ``Base``.  Placing it in its own
module keeps the import graph clean:

- ``db.session``  imports nothing from ``db.base``
- ``db.base``     imports nothing from ``db.session``
- Future model modules import ``Base`` from here, not from ``db.session``

This separation is required for Alembic (Milestone 6) to auto-detect
models without creating circular imports between the migration environment,
the session factory, and the model definitions.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by all GaiaOS ORM models.

    No columns are defined here.  Domain-specific tables are added in
    later milestones.  The base class exists now so that ``Base.metadata``
    is a stable, importable target for Alembic's ``target_metadata``.
    """


__all__ = ["Base"]
