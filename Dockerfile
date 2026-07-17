FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY requirements/base.txt requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.txt

COPY pyproject.toml .
COPY config/ config/
COPY gateway/ gateway/
COPY orchestrator/ orchestrator/

CMD ["python", "-c", "import time\nfrom config import get_settings\n\nsettings = get_settings()\nprint(\n    'GaiaOS placeholder started:',\n    f'env={settings.gaiaos_env}',\n    f'log_level={settings.log_level}',\n    f'database_url={settings.database_url}',\n    flush=True,\n)\nwhile True:\n    time.sleep(3600)\n"]
