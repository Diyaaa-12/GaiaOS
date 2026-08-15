# GaiaOS Python SDK (`gaiaos-sdk`)

<!-- [![PyPI Version](https://img.shields.io/pypi/v/gaiaos-sdk.svg)](https://pypi.org/project/gaiaos-sdk/) -->
<!-- [![Python Versions](https://img.shields.io/pypi/pyversions/gaiaos-sdk.svg)](https://pypi.org/project/gaiaos-sdk/) -->
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Official typed Python client library for [GaiaOS](https://github.com/Diyaaa-12/GaiaOS) — the Agentic Planetary Risk Intelligence Platform.

---

## Installation

```bash
pip install gaiaos-sdk
```

---

## Quickstart

### 1. Synchronous Client Usage (Jupyter / Scripts)

```python
from gaiaos_sdk import GaiaClient

# Initialize client (uses GAIAOS_API_URL and GAIAOS_API_KEY environment variables if unprovided)
with GaiaClient(base_url="http://localhost:8000", api_key="your_api_key_here") as client:
    # Optional server compatibility validation
    client.validate_server()

    # Submit an investigation
    resp = client.investigations.create(
        query="Assess coastal flood and sea level rise risks for Miami, Florida",
        domain_hint="climate"
    )
    print(f"Investigation ID: {resp.investigation_id}, Status: {resp.status}")

    # Stream real-time execution trace events
    for event in client.investigations.stream(resp.investigation_id):
        print(f"[{event.event_type}] {event.data}")

    # Fetch structured trace graph (Milestone 1 endpoint)
    trace = client.investigations.get_trace(resp.investigation_id)
    print(f"Trace Graph Nodes: {len(trace.nodes)}, Edges: {len(trace.edges)}")
```

### 2. Asynchronous Client Usage (`asyncio`)

```python
import asyncio
from gaiaos_sdk import AsyncGaiaClient

async def main():
    async with AsyncGaiaClient(base_url="http://localhost:8000", api_key="your_api_key_here") as client:
        # Submit an investigation
        resp = await client.investigations.create(
            query="Analyze wildfire spread probability in Southern California",
            domain_hint="wildfire"
        )

        # Stream SSE events asynchronously
        async for event in client.investigations.stream(resp.investigation_id):
            print(f"[{event.event_type}] {event.data}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Error Handling

All SDK exceptions inherit from `GaiaSDKError`.

```python
from gaiaos_sdk import (
    GaiaClient,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    IncompatibleServerError,
)

client = GaiaClient()

try:
    client.validate_server()
    status = client.investigations.get("non-existent-id")
except AuthenticationError:
    print("Invalid or missing API key.")
except RateLimitError as e:
    print(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
except NotFoundError:
    print("Investigation ID not found.")
except IncompatibleServerError as e:
    print(f"Server version mismatch: {e}")
```

---

## Public API Stability Policy

- **Stable Surface**: Only symbols exported from `gaiaos_sdk` (`import gaiaos_sdk`) and listed in `__all__` constitute the public, semver-stable API surface.
- **Internal Modules**: Modules under `gaiaos_sdk._generated` are auto-generated from OpenAPI specs and considered internal implementation details. Do not import directly from `_generated`.
- **API Stability Contract**: See the binding [v1.0 API Stability Contract](../../docs/api/STABILITY.md) for endpoint stability, deprecation timelines, and `/v2/` migration guarantees.


---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
