"""Regression test fixtures representing execution traces across GaiaOS historical phases.

Covers:
- Phase 2: Basic execution trace (nodes_executed, evidence_count)
- Phase 4: Critic verification flags + targeted replan loop
- Phase 5: Multi-agent collaboration bus events
- Phase 6: Degraded mode resilience fallback & evidence gaps
- Future: Unknown/plugin-generated event types
- Edge Case: Missing fields / corrupted / empty trace
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

INV_ID_PHASE2 = uuid.UUID("11111111-1111-4111-8111-111111111111")
INV_ID_PHASE4 = uuid.UUID("22222222-2222-4222-8222-222222222222")
INV_ID_PHASE5 = uuid.UUID("33333333-3333-4333-8333-333333333333")
INV_ID_PHASE6 = uuid.UUID("44444444-4444-4444-8444-444444444444")
INV_ID_PLUGIN = uuid.UUID("55555555-5555-4555-8555-555555555555")
INV_ID_CORRUPTED = uuid.UUID("66666666-6666-4666-8666-666666666666")

PHASE2_HISTORICAL_TRACE = SimpleNamespace(
    id=INV_ID_PHASE2,
    status="complete",
    complexity_tier="trivial",
    created_at=datetime(2026, 2, 10, 10, 0, 0, tzinfo=UTC),
    completed_at=datetime(2026, 2, 10, 10, 0, 2, tzinfo=UTC),
    confidence=0.92,
    execution_trace={
        "nodes_executed": ["supervisor", "air_quality", "synthesis", "critic", "finalize"],
        "evidence_count": 1,
    },
)

PHASE4_REPLAN_CRITIC_TRACE = SimpleNamespace(
    id=INV_ID_PHASE4,
    status="complete",
    complexity_tier="complex",
    created_at=datetime(2026, 4, 15, 14, 30, 0, tzinfo=UTC),
    completed_at=datetime(2026, 4, 15, 14, 30, 8, tzinfo=UTC),
    confidence=0.85,
    execution_trace={
        "nodes_executed": [
            "supervisor",
            "fan_out",
            "synthesis",
            "critic",
            "replan",
            "synthesis",
            "critic",
            "finalize",
        ],
        "evidence_count": 5,
        "replan_count": 1,
        "domains": ["seismic", "ocean"],
        "critic_flags": [
            {
                "claim_text": "Tsunami wave height unverified",
                "flagged_reason": "Low confidence citation from source B",
                "severity": "medium",
            }
        ],
    },
)

PHASE5_COLLABORATION_TRACE = SimpleNamespace(
    id=INV_ID_PHASE5,
    status="complete",
    complexity_tier="complex",
    created_at=datetime(2026, 5, 20, 9, 15, 0, tzinfo=UTC),
    completed_at=datetime(2026, 5, 20, 9, 15, 12, tzinfo=UTC),
    confidence=0.94,
    execution_trace={
        "nodes_executed": [
            "supervisor",
            "fan_out",
            "simulation",
            "synthesis",
            "critic",
            "finalize",
        ],
        "evidence_count": 8,
        "replan_count": 0,
        "domains": ["air_quality", "atmosphere", "simulation"],
        "collaboration": [
            {
                "from_agent": "air_quality",
                "to_agent": "simulation",
                "topic": "pm25_wind_vector",
                "payload": "High surface PM2.5 detected in Nord sector",
            }
        ],
    },
)

PHASE6_DEGRADED_MODE_TRACE = SimpleNamespace(
    id=INV_ID_PHASE6,
    status="complete",
    complexity_tier="moderate",
    created_at=datetime(2026, 6, 30, 16, 0, 0, tzinfo=UTC),
    completed_at=datetime(2026, 6, 30, 16, 0, 4, tzinfo=UTC),
    confidence=0.78,
    execution_trace={
        "nodes_executed": ["supervisor", "fan_out", "synthesis", "critic", "finalize"],
        "evidence_count": 3,
        "domains": ["openaq", "copernicus"],
        "degraded_sources": ["openaq"],
        "evidence_gaps": ["No recent ground sensor measurements due to openaq timeout"],
    },
)

FUTURE_PLUGIN_EVENT_TRACE = SimpleNamespace(
    id=INV_ID_PLUGIN,
    status="complete",
    complexity_tier="experimental",
    created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
    completed_at=datetime(2026, 8, 1, 12, 0, 5, tzinfo=UTC),
    confidence=0.88,
    execution_trace={
        "nodes_executed": [
            "supervisor",
            "custom_hydrology_plugin_agent",
            "future_quantum_synthesizer",
            "finalize",
        ],
        "evidence_count": 4,
        "plugin_metadata": {"author": "external_researcher", "version": "2.1.0"},
    },
)

CORRUPTED_EMPTY_TRACE = SimpleNamespace(
    id=INV_ID_CORRUPTED,
    status="failed",
    complexity_tier=None,
    created_at=datetime(2026, 8, 5, 18, 0, 0, tzinfo=UTC),
    completed_at=None,
    confidence=None,
    execution_trace=None,  # Null execution trace
)
