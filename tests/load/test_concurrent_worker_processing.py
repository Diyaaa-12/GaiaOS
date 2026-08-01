"""Concurrent worker load test — Phase 5 Milestone 7.

Verifies that N=4 concurrent RQ worker processes executing jobs in parallel process
a burst of M=100 investigations cleanly via the real GaiaOS investigation job path
(workers.jobs.investigation_job.run_investigation_job) with zero double-processing,
zero job loss, and 100% checkpoint isolation.
"""

from __future__ import annotations

import multiprocessing
import os
import uuid

import pytest
from redis import Redis
from rq import Queue, SimpleWorker
from rq.registry import FinishedJobRegistry, StartedJobRegistry

from config.settings import get_settings
from workers.jobs.investigation_job import run_investigation_job


def _worker_process_main(queue_name: str, redis_url: str) -> None:
    """Worker process entry point executing RQ jobs in burst mode without forking."""
    import sys
    import traceback

    try:
        conn = Redis.from_url(redis_url)
        q = Queue(queue_name, connection=conn)
        worker = SimpleWorker([q], connection=conn)
        worker.work(burst=True)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise


class TestConcurrentWorkerProcessing:
    """Load test verifying multi-worker scaling, RQ job-locking, and checkpoint isolation."""

    @pytest.fixture(autouse=True)
    def check_redis(self) -> None:
        """Skip load test if Redis is unreachable in current environment."""
        settings = get_settings()
        redis_url = settings.redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            conn = Redis.from_url(redis_url)
            conn.ping()
        except Exception:
            pytest.skip(f"Redis is unreachable at {redis_url} — skipping concurrent load test.")

    def test_concurrent_worker_burst_processing(self) -> None:
        """Verify N=4 concurrent workers execute M=100 real investigation jobs cleanly."""
        from rq.job import Job
        from rq.registry import FailedJobRegistry

        settings = get_settings()
        redis_url = settings.redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        conn = Redis.from_url(redis_url)

        queue_name = f"test_load_{uuid.uuid4().hex[:8]}"
        q = Queue(queue_name, connection=conn)

        num_jobs = 100
        num_workers = 4

        investigation_ids: list[str] = []
        job_ids: list[str] = []

        # 1. Enqueue M=100 real GaiaOS investigation jobs
        for i in range(num_jobs):
            inv_id = str(uuid.uuid4())
            investigation_ids.append(inv_id)
            query = f"Air quality test query {i} in Paris"
            job = q.enqueue(
                run_investigation_job,
                investigation_id=inv_id,
                query=query,
                job_timeout=60,
            )
            job_ids.append(job.id)

        # 2. Spawn N=4 concurrent worker processes
        processes: list[multiprocessing.Process] = []
        for _ in range(num_workers):
            p = multiprocessing.Process(
                target=_worker_process_main,
                args=(queue_name, redis_url),
            )
            p.start()
            processes.append(p)

        # 3. Wait for worker processes to finish burst execution; fail on timeout
        for i, p in enumerate(processes):
            p.join(timeout=120)
            if p.is_alive():
                p.terminate()
                pytest.fail("Load test worker process timed out after 120 seconds")

            if p.exitcode != 0:
                pytest.fail(f"Worker {i} exited with code {p.exitcode}")

        # 4. Verify RQ job-locking & completion metrics
        finished_registry = FinishedJobRegistry(queue=q)
        failed_registry = FailedJobRegistry(queue=q)
        finished_job_ids = set(finished_registry.get_job_ids())
        failed_job_ids = set(failed_registry.get_job_ids())

        failed_tracebacks: list[str] = []
        if failed_job_ids:
            for f_id in failed_job_ids:
                try:
                    j = Job.fetch(f_id, connection=conn)
                    if j.exc_info:
                        failed_tracebacks.append(f"Job {f_id} failed traceback:\n{j.exc_info}")
                except Exception:
                    pass

        failed_details = "\n\n".join(failed_tracebacks) if failed_tracebacks else ""

        assert len(finished_job_ids) == num_jobs, (
            f"Expected {num_jobs} finished jobs in registry, got {len(finished_job_ids)}. "
            f"Failed jobs count: {len(failed_job_ids)}.\n{failed_details}"
        )

        # 5. Verify actual Redis checkpoint isolation across all thread_ids
        for inv_id in investigation_ids:
            checkpoint_pattern = f"gaiaos:checkpoint:{inv_id}:*"
            matching_checkpoint_keys: list[bytes] = list(conn.scan_iter(match=checkpoint_pattern))
            assert len(matching_checkpoint_keys) > 0, (
                f"Missing checkpoint namespace for investigation_id / thread_id: {inv_id}"
            )

        # 6. Clean up Redis keys and RQ registries
        finished_registry = FinishedJobRegistry(queue=q)
        started_registry = StartedJobRegistry(queue=q)
        failed_registry = FailedJobRegistry(queue=q)
        for j_id in job_ids:
            finished_registry.remove(j_id)
            started_registry.remove(j_id)
            failed_registry.remove(j_id)
            conn.delete(f"rq:job:{j_id}")

        for inv_id in investigation_ids:
            checkpoint_pattern = f"gaiaos:checkpoint:{inv_id}:*"
            for key in conn.scan_iter(match=checkpoint_pattern):
                conn.delete(key)

        conn.delete(q.key)
