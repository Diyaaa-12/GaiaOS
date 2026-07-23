# GaiaOS Phase 3 — Milestone 3: Task Execution & Worker Architecture

**Status:** Implemented and Verified  
**Services:** `app` (FastAPI Gateway) & `worker` (RQ Task Worker)  
**Queue Backend:** Redis Queue (RQ)

---

## 1. Architectural Summary

Phase 3 Milestone 3 decouples investigation execution from the main HTTP API process by introducing a Redis Queue (RQ) worker architecture (`workers/worker.py`).

Investigations submitted via `POST /api/v1/investigations` are enqueued onto an RQ Redis queue (`default`), returning `202 Accepted` immediately. Background worker processes pick up the job and execute the LangGraph investigation workflow.

---

## 2. Key Technical Decisions

### Why RQ over Celery?
- **Simplicity & Operational Overhead:** GaiaOS uses Redis as a centralized cache and event broker. RQ provides lightweight, Python-native queueing backed natively by Redis without complex multi-broker configurations or message format abstraction layers.
- **Single-Queue Sufficiency:** Investigation jobs and scheduled ingestion tasks share a unified queue architecture.

### Decoupled Runtime & Worker Image
- `Dockerfile.worker` isolates the worker execution runtime from web gateway routes.
- Worker entry point `workers/worker.py` runs `rq.Worker(['default'], connection=redis_conn)`.
- Invocation site `workers/jobs/investigation_job.py` bridges synchronous RQ execution to asynchronous `LangGraph` invocation (`graph.ainvoke`).

### Failure Recovery & Mid-Job Worker Resume
- `rq.Retry(max=2)` handles transient worker crashes or network disruptions.
- If a worker crashes mid-job, the job is re-enqueued. When picked up by a new worker, the `RedisCheckpointSaver` automatically resumes graph execution from the last saved state checkpoint rather than starting from scratch.
- If retries are exhausted, the job status is set to `failed` with `error_code="job_retries_exhausted"`.

### Feature Flag (`USE_QUEUED_EXECUTION`)
- `USE_QUEUED_EXECUTION: bool` (default `True`) in `config/settings.py` controls whether jobs are enqueued via RQ or handled via FastAPI `BackgroundTasks`.
