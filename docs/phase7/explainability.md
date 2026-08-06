# GaiaOS Phase 7 Milestone 1 — Explainability & Reasoning Trace Exploration

## Overview

GaiaOS records complete execution traces for every query investigation. Phase 7 Milestone 1 introduces a dedicated, read-only explainability surface allowing developers, researchers, and system administrators to inspect *how* and *why* an investigation reached its conclusions.

The explainability layer consists of:
1. **API Endpoint**: `GET /api/v1/investigations/{id}/trace`
2. **Transformation Layer**: `orchestrator/explainability/trace_transformer.py`
3. **Admin Dashboard UI**: Investigation Reasoning Explorer in `admin_ui/`

---

## 1. Trace Endpoint & Schema (`GET /api/v1/investigations/{id}/trace`)

### Endpoint Specification
- **URL**: `GET /api/v1/investigations/{id}/trace`
- **Authentication**: JWT Bearer token or API Key
- **Authorization**: Reuses existing RBAC rules (`check_owner_or_role`: investigation owner or `ADMIN` role required).
- **HTTP Statuses**:
  - `200 OK`: Returns structured `InvestigationTraceResponse`
  - `401 Unauthorized`: Missing or invalid authentication token
  - `403 Forbidden`: Authenticated user is neither owner nor `ADMIN`
  - `404 Not Found`: Investigation UUID does not exist

### Response Schema (`schema_version: "1.0"`)

```json
{
  "investigation_id": "11111111-1111-4111-8111-111111111111",
  "schema_version": "1.0",
  "metadata": {
    "investigation_id": "11111111-1111-4111-8111-111111111111",
    "schema_version": "1.0",
    "generated_at": "2026-08-06T20:00:00Z",
    "status": "complete",
    "complexity_tier": "complex",
    "created_at": "2026-08-06T19:55:00Z",
    "completed_at": "2026-08-06T19:55:05Z",
    "confidence": 0.92,
    "node_count": 6,
    "edge_count": 5,
    "has_replan": true,
    "has_collaboration": true,
    "has_degraded_mode": false
  },
  "nodes": [
    {
      "id": "node_0_supervisor",
      "label": "Supervisor Planner",
      "type": "planning",
      "status": "completed",
      "timestamp": "2026-08-06T19:55:00Z",
      "details": {
        "raw_name": "supervisor"
      }
    },
    {
      "id": "node_1_fan_out",
      "label": "Parallel Fan-Out Coordinator",
      "type": "agent_started",
      "status": "completed",
      "details": {
        "domains": ["air_quality", "simulation"]
      }
    }
  ],
  "edges": [
    {
      "id": "edge_node_0_to_node_1",
      "source": "node_0_supervisor",
      "target": "node_1_fan_out",
      "label": null,
      "type": "sequential"
    }
  ],
  "summary": {
    "evidence_count": 5,
    "replan_count": 1,
    "critic_flag_count": 1,
    "collaboration_event_count": 1,
    "degraded_sources": []
  }
}
```

---

## 2. Event Taxonomy (`TraceEventTaxonomy`)

To prevent taxonomy drift across services and UI components, all trace node types map to `TraceEventTaxonomy`:

| Taxonomy Enum Value | Node Type Category | Visual Badge Style |
|---|---|---|
| `planning` | Initial planning / supervisor node | Indigo (`#e0e7ff`) |
| `supervisor` | Supervisor query classification | Indigo (`#e0e7ff`) |
| `agent_started` | Domain agent execution start | Blue (`#dbeafe`) |
| `evidence_found` | Evidence collection event | Cyan (`#cffafe`) |
| `synthesizing` | Cross-domain synthesis pass | Purple (`#f3e8ff`) |
| `critic_flag` | Critic claim verification / flag | Amber (`#fef3c7`) |
| `replanning` | Targeted replan loop pass | Orange (`#ffedd5`) |
| `collaboration` | Peer-to-peer agent refinement broadcast | Teal (`#ccfbf1`) |
| `finalize` | Final answer rendering & persistence | Green (`#dcfce7`) |
| `degraded` | Resilience fallback / circuit breaker | Rose (`#ffe4e6`) |
| `unknown` / `custom` | Plugin / external custom event | Slate (`#f1f5f9`) |

---

## 3. Backward Compatibility & API Contract Policy

- **`schema_version` Guarantee**: The top-level and metadata `schema_version` field indicates the contract version (currently `"1.0"`).
- **Additive Non-Breaking Changes**: Any future additions (new metadata attributes, new summary metrics) will be strictly additive.
- **Unknown Event Preservation**: If a future plugin or custom agent emits unrecognized event types or extra key-values, the transformer preserves full raw payloads inside `TraceNode.details` under `type="custom"` or `type="unknown"`, guaranteeing zero breakage for custom extensions.

---

## 4. Admin UI Architecture & Performance

The Admin UI includes an **Investigation Reasoning Explorer**:
- **Isolated Component Architecture**: Graph rendering is encapsulated in `<InvestigationTraceGraph />`, decoupling rendering logic from page state.
- **Lazy Loading (Refinement 5)**: `<InvestigationTraceView />` is lazy-loaded using `React.lazy()` and `<Suspense />` so initial dashboard bundle load remains fast.

### Large Trace Performance Verification Scenario (Refinement 7)

To verify UI responsiveness under heavy workloads:
1. Generate synthetic investigation with 50+ execution nodes (e.g. 5 replan passes, multi-agent collaboration, 20 evidence items).
2. Load `/investigations/{id}` in Admin UI.
3. Assert that initial DOM layout renders under 100ms without freezing the main thread.
4. Click through individual nodes to confirm the Inspection Drawer displays detailed payloads instantly.
