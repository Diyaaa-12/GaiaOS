FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY requirements/base.txt requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.txt

COPY pyproject.toml .
COPY alembic.ini .
COPY config/ config/
COPY logging_config/ logging_config/
COPY gateway/ gateway/
COPY orchestrator/ orchestrator/
COPY app/ app/
COPY db/ db/
COPY data/ data/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
