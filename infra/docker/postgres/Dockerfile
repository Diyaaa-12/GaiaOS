# Production-safe PostgreSQL image with PostGIS and pgvector.
#
# Base: postgis/postgis:16-3.4 (Docker Verified Publisher — includes PostGIS and
# the PGDG apt repository for PostgreSQL 16).
# Extension: postgresql-16-pgvector installed as a pre-compiled PGDG apt package;
# no build toolchain (build-essential, make, git) is needed or included in the
# final image.

# postgis/postgis:16-3.4
FROM postgis/postgis:16-3.5@sha256:4e07b425403ba55c20b541884db2e80c686dd6476bf9265046ac9c163895605d

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
