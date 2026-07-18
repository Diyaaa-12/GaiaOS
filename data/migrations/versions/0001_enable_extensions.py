"""Enable PostGIS and pgvector extensions.

Revision ID: 0001
Revises:     (none — this is the initial migration)
Create Date: 2026-07-18 09:00:00.000000 UTC

Why this migration exists
-------------------------
GaiaOS requires two PostgreSQL extensions that must be present before any
domain schema is created:

- **PostGIS** — geospatial types (geometry, geography) and functions used
  for location-aware risk modelling.
- **pgvector** — the ``vector`` column type used for embedding-based
  similarity search throughout the retrieval and synthesis layers.

These extensions were verified ad-hoc during Milestone 5 via the container's
``init-extensions.sql`` script.  This migration *formally* installs them as
a versioned, reproducible step in the migration chain so that:

1.  A fresh database (e.g. in CI or a new environment) is fully functional
    after ``alembic upgrade head`` with no manual intervention.
2.  The migration history is auditable and reversible.

Idempotency
-----------
Both ``CREATE EXTENSION IF NOT EXISTS`` statements are safe to run multiple
times.  If the extension already exists (e.g. because the Postgres container
``init-extensions.sql`` script ran first), the statement succeeds silently.

Reversibility
-------------
``DROP EXTENSION IF EXISTS`` is used in ``downgrade()``.  Dropping an
extension removes all objects that depend on it (types, functions, operators,
indexes), so downstream code that depends on PostGIS or pgvector types must
also be migrated down before this migration can safely be reversed.
In practice, ``alembic downgrade base`` is a full wipe intended for dev/CI
use only.  Production downgrades should be planned carefully.

Note on superuser privileges
-----------------------------
``CREATE EXTENSION`` requires superuser or ``pg_extension_owner`` membership
in Postgres 15+, or the ``rds_superuser`` role on Amazon RDS.  The GaiaOS
dev environment runs as the ``gaiaos`` superuser inside the Docker container
(see ``docker-compose.yml``), so this requirement is already satisfied.
In managed environments, grant the necessary privileges before running
migrations for the first time.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None  # initial migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable the PostGIS and pgvector extensions.

    Uses ``IF NOT EXISTS`` so the migration is idempotent — safe to run
    against a database where the extensions were already installed manually
    (e.g. via the container's ``init-extensions.sql`` initialisation script).
    """
    # PostGIS: geospatial types and functions.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # pgvector: vector column type and similarity-search operators.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    """Remove pgvector, PostGIS companion extensions, and PostGIS itself.

    Root-cause context — why CASCADE is required on the postgis drop
    -----------------------------------------------------------------
    The ``postgis/postgis`` Docker image registers ``postgis_topology`` and
    ``postgis_tiger_geocoder`` against ``postgis`` with ``deptype = 'n'``
    (NORMAL dependency) in ``pg_depend``, not ``deptype = 'x'`` (auto /
    extension-owned).

    The critical difference:

    * ``deptype = 'x'`` records are deleted automatically when their parent
      extension is dropped (``DROP EXTENSION`` does a cascading delete of all
      'x' records whose ``objid`` matches the dropped extension).
    * ``deptype = 'n'`` records survive the ``DROP EXTENSION`` of the *owning*
      extension — they are only used by PostgreSQL to BLOCK the drop of the
      *referenced* extension (postgis in this case).

    Consequence:

    1. ``DROP EXTENSION IF EXISTS postgis_tiger_geocoder`` — succeeds: the
       extension row is removed from ``pg_extension``.
    2. ``DROP EXTENSION IF EXISTS postgis_topology``       — succeeds: the
       extension row is removed from ``pg_extension``.
    3. ``DROP EXTENSION IF EXISTS postgis`` — FAILS: PostgreSQL walks
       ``pg_depend`` looking for any row whose ``refobjid`` is the postgis
       OID.  It still finds the two ``deptype = 'n'`` rows (their ``objid``
       OIDs now point at deleted pg_extension rows, but the pg_depend rows
       themselves were NOT removed by steps 1–2).  PostgreSQL reports the
       familiar "extension postgis_topology depends on extension postgis"
       error and aborts.

    Fix: Use ``CASCADE`` on the postgis drop.  CASCADE tells PostgreSQL to
    drop postgis *and* remove all objects — including orphaned ``pg_depend``
    records — that reference it, regardless of ``deptype``.

    Why CASCADE is safe here:

    * This is the **base** migration (``down_revision = None``).  By the time
      ``alembic downgrade base`` reaches this step, every domain migration
      above it has already reversed its geometry/vector columns, spatial
      indexes, and any other PostGIS-dependent objects.  There is nothing
      user-owned left for CASCADE to accidentally destroy.
    * The explicit companion drops above are kept as belt-and-suspenders: they
      cleanly remove the extension entries first so CASCADE has less work to
      do and the intent remains explicit and auditable.

    ``IF EXISTS`` on every statement keeps the downgrade idempotent — safe
    to re-run even if a previous partial downgrade already removed some
    extensions.

    Drop order (strict reverse-dependency, then CASCADE fallback):
        1. postgis_tiger_geocoder  — depends on postgis_topology + postgis
        2. postgis_topology        — depends on postgis
        3. vector                  — no cross-extension dependencies
        4. postgis CASCADE         — removes postgis + orphaned pg_depend rows
        5. fuzzystrmatch           — installed by the PostGIS image as a
                                     dependency of postgis_tiger_geocoder;
                                     benign no-op if already absent
    """
    # Drop PostGIS companion extensions first (explicit, clean, auditable).
    op.execute("DROP EXTENSION IF EXISTS postgis_tiger_geocoder;")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology;")
    # Drop pgvector — independent of PostGIS, no cross-dependency.
    op.execute("DROP EXTENSION IF EXISTS vector;")
    # CASCADE is required: the postgis/postgis Docker image registers companion
    # extensions with deptype='n' in pg_depend; those records survive the
    # companion DROP EXTENSION calls above and block a plain DROP EXTENSION
    # postgis.  CASCADE clears all remaining pg_depend references to postgis.
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")
    # fuzzystrmatch is auto-installed by the PostGIS image as a dependency of
    # postgis_tiger_geocoder.  Drop it last so it is also removed on a full
    # teardown.  Safe no-op if not present.
    op.execute("DROP EXTENSION IF EXISTS fuzzystrmatch;")
