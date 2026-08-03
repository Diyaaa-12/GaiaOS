# Async Resource Lifecycle & Event Loop Isolation

## Overview

During Phase 5 Milestone 7 (Horizontal Scalability & Performance Tuning), load testing under RQ `SimpleWorker` and multi-task async execution exposed a critical class of async Python issues: **Loop-Bound Shared Async Resources**.

This document outlines the root cause, architectural patterns, and guidelines to ensure shared async resources (database engines, Redis clients, HTTP clients) remain safe across different worker task event loops.

---

## The Problem: Event Loop Mismatch

In async Python (asyncio), resources created on one event loop (e.g. during application startup or module import) maintain internal connections bound to that specific loop.

When background job workers (such as RQ `SimpleWorker`) run jobs across fresh event loops via `asyncio.run()`, referencing a pre-existing loop-bound client raises runtime errors:

```text
RuntimeError: Task <Task ...> got Future <Future ...> attached to a different loop
```

or:

```text
asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress / bound to a different event loop
```

---

## Architectural Guidelines & Best Practices

### 1. Database Session & Engine Lifecycle

- **Web Application Context**: The engine is initialized during FastAPI app startup lifespan (`init_engine()`) and disposed at shutdown lifespan (`dispose_engine()`).
- **Background Worker Context**: Workers executing discrete background jobs must re-initialize or dispose engine instances per job:
  ```python
  if settings.database_url and AsyncSessionLocal is None:
      init_engine()

  async with AsyncSessionLocal() as session:
      # Perform database operations
      ...
  ```
- **Testing Context**: Test fixtures in `conftest.py` use `NullPool` to prevent asyncpg connection pooling across pytest event loops:
  ```python
  engine = create_async_engine(async_url, poolclass=NullPool)
  ```

### 2. Redis Connection Management

- Avoid module-level static Redis client singletons across worker jobs.
- Use explicit helper functions (`get_redis()`) that check or reconstruct clients per loop context:
  ```python
  from cache.client import get_redis, close_redis

  async with get_redis() as client:
      await client.ping()
  ```

### 3. HTTP Client (httpx) Lifecycle

- Avoid sharing a single global `httpx.AsyncClient` instance across separate background worker tasks running in different event loops.
- Use short-lived `async with AsyncClient() as client:` context managers inside background job handlers.
