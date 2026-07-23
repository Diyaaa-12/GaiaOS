"""Tests for RQ worker retry mechanics and failure handling."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis

from metrics.events import JobFailed
from workers.jobs.investigation_job import _async_run_investigation


class TestWorkerRetryFailure:
    """Tests for worker retry exhausted handling and metric emissions."""

    @pytest.mark.asyncio
    async def test_job_failure_emits_job_failed_metric(
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
        mock_graph.ainvoke.side_effect = RuntimeError("Agent execution failed")
        monkeypatch.setattr(
            "workers.jobs.investigation_job.build_graph",
            lambda checkpointer: mock_graph,
        )

        mock_job = MagicMock()
        mock_job.retries_left = 1
        mock_job.origin = 1
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_current_job",
            lambda: mock_job,
        )

        with pytest.raises(RuntimeError, match="Agent execution failed"):
            await _async_run_investigation(inv_id, "Failing query")

        failed_events = [e for e in emitted_events if isinstance(e, JobFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].investigation_id == str(inv_id)
        assert failed_events[0].error_code == "job_attempt_failed"
        assert "Agent execution failed" in failed_events[0].error_message

    @pytest.mark.asyncio
    async def test_terminal_retry_exhausted_updates_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        inv_id = uuid.uuid4()
        emitted_events = []

        monkeypatch.setattr(
            "workers.jobs.investigation_job.emit",
            lambda evt: emitted_events.append(evt),
        )

        mock_redis = AsyncMock(spec=Redis)
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_redis",
            AsyncMock(return_value=mock_redis),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = RuntimeError("Fatal LLM crash")
        monkeypatch.setattr(
            "workers.jobs.investigation_job.build_graph",
            lambda checkpointer: mock_graph,
        )

        mock_job = MagicMock()
        mock_job.retries_left = 0
        mock_job.origin = 3
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_current_job",
            lambda: mock_job,
        )

        mock_update_status = AsyncMock()
        monkeypatch.setattr(
            "db.repository.InvestigationRepository.update_investigation_status",
            mock_update_status,
        )

        # Mock db session context
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        monkeypatch.setattr("db.session.AsyncSessionLocal", mock_factory)

        with pytest.raises(RuntimeError, match="Fatal LLM crash"):
            await _async_run_investigation(inv_id, "Fatal query")

        failed_events = [e for e in emitted_events if isinstance(e, JobFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].error_code == "job_retries_exhausted"

        assert mock_update_status.called
        call_kwargs = mock_update_status.call_args.kwargs
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["execution_trace"]["error_code"] == "job_retries_exhausted"

    @pytest.mark.asyncio
    async def test_worker_crash_mid_job_resumes_from_checkpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulates worker 1 crashing mid-job after saving checkpoint.

        Verifies worker 2 picks up the job and passes thread_id to graph,
        resuming state execution via RedisCheckpointSaver.
        """
        inv_id = uuid.uuid4()
        thread_id = str(inv_id)
        emitted_events = []

        monkeypatch.setattr(
            "workers.jobs.investigation_job.emit",
            lambda evt: emitted_events.append(evt),
        )

        mock_redis = AsyncMock(spec=Redis)
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_redis",
            AsyncMock(return_value=mock_redis),
        )

        passed_configs = []

        async def mock_ainvoke(input_state: dict, config: dict | None = None) -> dict:
            passed_configs.append(config)
            return {"final_answer": "Resumed answer after worker crash"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = mock_ainvoke
        monkeypatch.setattr(
            "workers.jobs.investigation_job.build_graph",
            lambda checkpointer: mock_graph,
        )

        # Worker 2 picks up job after Worker 1 crash
        mock_job = MagicMock()
        mock_job.retries_left = 1  # 2nd attempt after crash
        monkeypatch.setattr(
            "workers.jobs.investigation_job.get_current_job",
            lambda: mock_job,
        )

        await _async_run_investigation(inv_id, "Resumed query after crash")

        # Verify thread_id was passed to graph for checkpoint loading
        assert len(passed_configs) == 1
        cfg = passed_configs[0]
        assert cfg is not None and cfg["configurable"]["thread_id"] == thread_id


        # Verify job completed event
        completed_events = [e for e in emitted_events if getattr(e, "status", None) == "complete"]
        assert len(completed_events) == 1
        assert completed_events[0].investigation_id == str(inv_id)
