"""Unit and integration tests for investigation_job execution bridge."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis

from metrics.events import JobCompleted, JobStarted
from workers.jobs.investigation_job import _async_run_investigation, run_investigation_job


class TestInvestigationJobBridge:
    """Tests for RQ investigation job bridge and execution handling."""

    @pytest.mark.asyncio
    async def test_async_run_investigation_emits_events(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        inv_id = uuid.uuid4()
        emitted_events = []

        def mock_emit(evt) -> None:
            emitted_events.append(evt)

        monkeypatch.setattr("workers.jobs.investigation_job.emit", mock_emit)

        mock_redis = AsyncMock(spec=Redis)
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_redis",
            AsyncMock(return_value=mock_redis),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {}
        monkeypatch.setattr(
            "workers.jobs.investigation_job.build_graph",
            lambda checkpointer: mock_graph,
        )

        await _async_run_investigation(inv_id, "Test seismic hazard query")

        assert len(emitted_events) == 2
        assert isinstance(emitted_events[0], JobStarted)
        assert isinstance(emitted_events[1], JobCompleted)
        assert emitted_events[0].investigation_id == str(inv_id)
        assert emitted_events[1].investigation_id == str(inv_id)
        assert emitted_events[1].status == "complete"

    def test_run_investigation_job_accepts_str_and_uuid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        inv_id_str = str(uuid.uuid4())
        mock_async_run = AsyncMock()

        monkeypatch.setattr(
            "workers.jobs.investigation_job._async_run_investigation",
            mock_async_run,
        )

        with patch("asyncio.run", lambda coro: None):
            run_investigation_job(inv_id_str, "Test query")

        # Test string UUID conversion
        inv_uuid = uuid.UUID(inv_id_str)
        assert isinstance(inv_uuid, uuid.UUID)
