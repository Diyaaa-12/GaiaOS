# Production-safe PostgreSQL 16 image with PostGIS and pgvector.
#
# Base: postgres:16-bookworm (Docker Official Image — includes PostgreSQL 16
# and the official PGDG apt repository on Debian 12 Bookworm).
# Extensions: postgresql-16-postgis-3 and postgresql-16-pgvector installed as
# pre-compiled PGDG apt packages; no build toolchain (build-essential, make, git)
# is needed or included in the final image.

# postgres:16-bookworm
FROM postgres:16-bookworm@sha256:efedf3595f1d6f415c08568ba171029bf54052e754cc9f030e3f2412b21f3d67

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
