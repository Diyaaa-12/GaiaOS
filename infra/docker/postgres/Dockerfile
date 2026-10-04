# Production-safe PostgreSQL 16 image with PostGIS and pgvector.
#
# Base: postgres:16-bookworm (Docker Official Image — includes PostgreSQL 16
# and the official PGDG apt repository on Debian 12 Bookworm).
# Extensions: postgresql-16-postgis-3 and postgresql-16-pgvector installed as
# pre-compiled PGDG apt packages; no build toolchain (build-essential, make, git)
# is needed or included in the final image.

# postgres:16-bookworm
FROM postgres:18-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
