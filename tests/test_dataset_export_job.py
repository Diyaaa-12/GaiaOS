"""Unit and integration tests for dataset export job — Phase 5 Milestone 9."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.repository import InvestigationRepository
from workers.jobs.dataset_export_job import _async_run_dataset_export


@pytest.mark.asyncio
async def test_dataset_export_job_execution(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dataset export job writes .jsonl.gz archive, manifest.json, and checksum file."""
    # Seed consenting investigation
    inv = await InvestigationRepository.create_investigation(
        session=db_session,
        query="Wildfire spread prediction model query",
        consent_public_research=True,
    )
    await InvestigationRepository.update_investigation_status(
        session=db_session,
        investigation_id=inv.id,
        status="complete",
        complexity_tier="moderate",
        answer="Wildfire spread report generated.",
        confidence=0.91,
        execution_trace={"domains": ["wildfire"]},
    )

    export_dir = tmp_path / "exports"
    monkeypatch.setenv("DATASET_EXPORT_ENABLED", "true")
    monkeypatch.setenv("DATASET_EXPORT_DIR", str(export_dir))
    get_settings.cache_clear()

    try:
        manifest = await _async_run_dataset_export()

        assert manifest.get("status") != "disabled"
        assert manifest["dataset_version"] == "v1.0"
        assert manifest["record_count"] >= 1
        assert manifest["consenting_investigations_count"] >= 1
        assert manifest["checksum"] is not None

        # Verify filesystem artifacts
        manifest_file = export_dir / "manifest.json"
        assert manifest_file.exists()

        archive_file = export_dir / manifest["archive_filename"]
        assert archive_file.exists()

        # Read archive contents and verify JSON lines
        records = []
        with gzip.open(archive_file, "rt", encoding="utf-8") as gz:
            for line in gz:
                records.append(json.loads(line))

        assert len(records) == manifest["record_count"]

        consenting_record = next(
            (r for r in records if r.get("investigation_id") == str(inv.id)), None
        )
        assert consenting_record is not None
        assert consenting_record["consent_public_research"] is True
        assert consenting_record["query_text"] == "Wildfire spread prediction model query"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dataset_export_disabled_by_feature_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DATASET_EXPORT_ENABLED is false, export job returns status=disabled."""
    monkeypatch.setenv("DATASET_EXPORT_ENABLED", "false")
    get_settings.cache_clear()

    try:
        res = await _async_run_dataset_export()
        assert res["status"] == "disabled"
    finally:
        get_settings.cache_clear()
