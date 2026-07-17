# Production-safe PostgreSQL image with PostGIS and pgvector.
#
# Base: postgis/postgis:16-3.4 (Docker Verified Publisher — includes PostGIS and
# the PGDG apt repository for PostgreSQL 16).
# Extension: postgresql-16-pgvector installed as a pre-compiled PGDG apt package;
# no build toolchain (build-essential, make, git) is needed or included in the
# final image.

FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
