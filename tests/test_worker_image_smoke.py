"""CI worker/scheduler deployment smoke test and environment gate test suite."""

from __future__ import annotations

import os
import sys
import time

import httpx
import pytest
from httpx import AsyncClient

from config.settings import get_settings

# ---------------------------------------------------------------------------
# Unit Test Suite: Environment Gate Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_job_gated_in_production(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert POST /internal/smoke-job returns 404 when GAIAOS_ENV=prod."""
    get_settings.cache_clear()
    monkeypatch.setenv("GAIAOS_ENV", "prod")
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret-key-that-is-at-least-32-chars-long!")
    monkeypatch.setenv("DATABASE_URL", "postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    response = await client.post("/internal/smoke-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_smoke_job_allowed_in_non_prod(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert POST /internal/smoke-job returns 202 and job_id in non-prod environment."""
    get_settings.cache_clear()
    monkeypatch.setenv("GAIAOS_ENV", "dev")

    # Mock Redis Queue enqueue to prevent needing real Redis for unit test
    class MockJob:
        id = "mock-job-id"

    monkeypatch.setattr("rq.Queue.enqueue", lambda *a, **kw: MockJob())

    response = await client.post("/internal/smoke-job")

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "enqueued"
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Integration CLI Runner: Live Stack Worker Verification
# ---------------------------------------------------------------------------


def run_live_smoke_verification(
    base_url: str = "http://localhost:8000",
    timeout_seconds: int = 30,
) -> bool:
    """Execute live end-to-end smoke job test against containerized stack."""
    print(f"[*] Starting deployment smoke verification against {base_url}...")

    # 1. Trigger smoke job
    endpoint = f"{base_url}/internal/smoke-job"
    try:
        resp = httpx.post(endpoint, timeout=10.0)
    except Exception as exc:
        print(f"[!] Failed to reach smoke job endpoint {endpoint}: {exc}")
        return False

    if resp.status_code != 202:
        print(
            f"[!] Expected HTTP 202 from {endpoint}, got status {resp.status_code}: {resp.text}"
        )
        return False

    job_data = resp.json()
    job_id_str = job_data.get("job_id")
    if not job_id_str:
        print(f"[!] Invalid response structure from smoke endpoint: {job_data}")
        return False

    print(f"[*] Smoke job enqueued with investigation_id: {job_id_str}")

    # 2. Poll DB status via PostgreSQL or API
    poll_url = f"{base_url}/api/v1/investigations/{job_id_str}"
    start_time = time.monotonic()

    while (time.monotonic() - start_time) < timeout_seconds:
        try:
            poll_resp = httpx.get(poll_url, timeout=5.0)
            if poll_resp.status_code == 200:
                data = poll_resp.json()
                status = data.get("status")
                elapsed = time.monotonic() - start_time
                print(f"[*] Polled job status: '{status}' ({elapsed:.1f}s elapsed)")
                if status == "complete":
                    print("[+] SUCCESS: Worker completed smoke job!")
                    return True
                elif status == "failed":
                    print(f"[!] FAIL: Worker job marked as failed: {data}")
                    return False
        except Exception as exc:
            print(f"[*] Polling warning: {exc}")

        time.sleep(1.0)

    print(f"[!] FAIL: Smoke job timed out after {timeout_seconds} seconds.")
    return False


if __name__ == "__main__":
    url = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")
    success = run_live_smoke_verification(base_url=url, timeout_seconds=30)
    if not success:
        sys.exit(1)
    sys.exit(0)
