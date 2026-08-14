# Production-safe PostgreSQL image with PostGIS and pgvector.
#
# Base: postgis/postgis:16-3.4 (Docker Verified Publisher — includes PostGIS and
# the PGDG apt repository for PostgreSQL 16).
# Extension: postgresql-16-pgvector installed as a pre-compiled PGDG apt package;
# no build toolchain (build-essential, make, git) is needed or included in the
# final image.

# postgis/postgis:16-3.4
FROM postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
