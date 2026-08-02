"""Exhaustive privacy unit tests for AnonymizationPolicy — Phase 5 Milestone 9."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.v1.anonymization import AnonymizationPolicy
from db.models.investigation import Investigation


def test_anonymization_policy_non_consented_investigation() -> None:
    """Non-consented investigation MUST strip query_text, user_id, and PII fields."""
    inv = Investigation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query_text="What was the magnitude of the seismic event near Tokyo?",
        complexity_tier="complex",
        status="complete",
        answer="Magnitude 6.2 seismic tremor recorded.",
        confidence=0.92,
        consent_public_research=False,
        execution_trace={
            "domains": ["seismic"],
            "user_id": "sensitive_user_123",
            "client_ip": "192.168.1.1",
            "active_agents": ["seismic_agent"],
        },
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    anon = AnonymizationPolicy.apply(inv)

    # Privacy assertions
    assert "user_id" not in anon or anon.get("user_id") is None
    assert anon["consent_public_research"] is False
    assert anon["query_text"] is None
    assert anon["query_category"] == "seismic_research"
    assert anon["domains_involved"] == ["seismic"]

    # Trace assertions
    trace = anon["execution_trace"]
    assert trace is not None
    assert "client_ip" not in trace
    assert "user_id" not in trace
    assert trace["domains"] == ["seismic"]


def test_anonymization_policy_consented_investigation() -> None:
    """Consented investigation includes query_text but still strips user_id and PII."""
    inv = Investigation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query_text="Analyze wildfire risk in Northern California.",
        complexity_tier="moderate",
        status="complete",
        confidence=0.88,
        consent_public_research=True,
        execution_trace={"domains": ["wildfire"]},
        created_at=datetime.now(UTC),
    )

    anon = AnonymizationPolicy.apply(inv)

    assert anon["consent_public_research"] is True
    assert anon["query_text"] == "Analyze wildfire risk in Northern California."
    assert anon["query_category"] == "wildfire_research"
    assert "user_id" not in anon or anon.get("user_id") is None


def test_derive_query_categories() -> None:
    """Verify category derivation for different environmental domains."""
    assert AnonymizationPolicy.derive_query_category("earthquake fault line") == "seismic_research"
    assert (
        AnonymizationPolicy.derive_query_category("wildfire smoke emissions")
        == "wildfire_research"
    )
    assert (
        AnonymizationPolicy.derive_query_category("ocean sea surface temp")
        == "oceanographic_research"
    )
    assert (
        AnonymizationPolicy.derive_query_category("air quality pm2.5 concentration")
        == "atmospheric_research"
    )
    assert (
        AnonymizationPolicy.derive_query_category("generic research query", "complex")
        == "complex_environmental_research"
    )
