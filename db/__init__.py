"""Database package.

Public surface
--------------
``Base``
    SQLAlchemy declarative base.  Import from here for all model definitions.

``db.session``
    Engine lifecycle (``init_engine``, ``dispose_engine``), session factory
    (``AsyncSessionLocal``), session DI generator (``get_db_session``), and
    extension verification (``verify_extensions``).  Import directly from
    ``db.session`` rather than from this package — the engine and session
    factory are mutable singletons that are ``None`` until ``init_engine()``
    is called, so re-exporting them here would snapshot the ``None`` value
    at import time.

Import direction (enforced, no cycles allowed):
    db  →  config
    app →  db
    db  ✗→ app
"""

from db.base import Base

__all__ = ["Base"]
