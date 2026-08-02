# GaiaOS Public Research API & Dataset Publishing

## Overview

The GaiaOS Public Research API (`/api/v1/research/*`) provides open, read-only access to aggregated, anonymized environmental investigation findings and historical hazard datasets.

---

## Data Privacy & Consent Policy (ADR-504)

GaiaOS follows an explicit **Opt-In Consent, Never Opt-Out** policy for public research data sharing:

1. **User Identity (`user_id`)**: Strictly disassociated and omitted from all public research endpoints and dataset exports.
2. **Raw Query Text**: Included in public research findings **only** if the submitting user explicitly opted in (`consent_public_research = true`) at submission time.
3. **Non-Consented Queries**: For queries where consent was not granted (`consent_public_research = false`), raw query text is stripped and replaced with generalized, non-identifying query categories (e.g. `seismic_research`, `atmospheric_research`).
4. **Execution Traces**: Automatically sanitized to strip internal identifiers, client IP addresses, headers, and credentials.

---

## Endpoints

### 1. List Public Research Investigations

`GET /api/v1/research/investigations`

#### Query Parameters

- `domain` (optional): Filter findings by environmental domain (e.g., `seismic`, `atmosphere`, `wildfire`, `ocean`).
- `since` (optional): ISO 8601 timestamp filtering findings created after a given date.
- `limit` (optional, default `50`, max `200`): Pagination limit.
- `offset` (optional, default `0`): Pagination offset.

#### Example Response

```json
[
  {
    "investigation_id": "11111111-2222-3333-4444-555555555555",
    "query_category": "seismic_research",
    "domains_involved": ["seismic", "literature"],
    "complexity_tier": "complex",
    "confidence_summary": 0.92,
    "consent_public_research": false,
    "query_text": null,
    "created_at": "2026-08-01T12:00:00+00:00",
    "completed_at": "2026-08-01T12:00:05+00:00"
  }
]
```

### 2. List Public Hazard Events

`GET /api/v1/research/hazard-events`

#### Query Parameters

- `event_type` (optional): Filter events (e.g., `earthquake`, `wildfire`).
- `source` (optional): Data provider source (e.g., `USGS`, `NOAA`, `FIRMS`).
- `limit` (optional, default `50`, max `200`): Pagination limit.
- `offset` (optional, default `0`): Pagination offset.

---

## Rate Limits & SLA

- Public Research API endpoints are rate-limited under the `research_api` scope (`60 requests/minute`).
- Endpoints are backed by GaiaOS Service Level Objectives (SLOs) covering uptime and response latency.

---

## Monthly Dataset Exports

A monthly export job publishes compressed, checksummed archives (`.jsonl.gz`) alongside a `manifest.json` describing dataset versioning, record counts, and SHA-256 hashes.
