# Production-safe PostgreSQL image with PostGIS and pgvector.
#
# Base: postgis/postgis:16-3.4 (Docker Verified Publisher — includes PostGIS and
# the PGDG apt repository for PostgreSQL 16).
# Extension: postgresql-16-pgvector installed as a pre-compiled PGDG apt package;
# no build toolchain (build-essential, make, git) is needed or included in the
# final image.

# postgis/postgis:16-3.4
FROM postgis/postgis:17-3.5@sha256:0a23a2b5e4fbd9b4c6980d20ee80dd6b63dec52669379c75a506db58a4116708

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
