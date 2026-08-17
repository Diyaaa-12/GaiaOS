# python:3.12-slim-bookworm
FROM python:3.14-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY requirements/base.lock requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.lock

COPY pyproject.toml .
COPY README.md .
COPY alembic.ini .
COPY config/ config/
COPY logging_config/ logging_config/
COPY metrics/ metrics/
COPY gateway/ gateway/
COPY orchestrator/ orchestrator/
COPY app/ app/
COPY auth/ auth/
COPY db/ db/
COPY data/ data/
COPY cache/ cache/
COPY resilience/ resilience/
COPY tools/ tools/
COPY workers/ workers/

COPY mcp_servers/ mcp_servers/
COPY ingestion/ ingestion/
COPY simulation_engine/ simulation_engine/
COPY eval/ eval/
COPY alerting/ alerting/

RUN pip install --no-cache-dir --no-deps -e .

# Create a non-root user and group
RUN groupadd -g 10000 gaiaos \
    && useradd -u 10000 -g gaiaos -s /bin/bash -m gaiaos \
    && chown -R gaiaos:gaiaos /app

USER gaiaos

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
