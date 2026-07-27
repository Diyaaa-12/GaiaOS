"""Tests for Evidence ID matching, fallback mechanisms, and citation integrity."""

from __future__ import annotations

import json
import uuid

import pytest
import respx

from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.agents.synthesis.citation_mapper import CitationMapper
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.synthesis import RawCitedEvidence, SynthesizedClaim


def test_successful_id_lookup() -> None:
    """Verify that ID matching succeeds and preserves exact Evidence metadata."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    ev2 = Evidence(source="USGS API", claim="Magnitude 4.2 earthquake", confidence=0.88)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1, ev2])

    mapper = CitationMapper([agent_output])

    cited = RawCitedEvidence(
        evidence_id=ev1.id,
        source="OpenAQ API",
        claim="PM10 is 30 ug/m3 in Paris",
        confidence=0.5,
    )
    verified = mapper.map_citations([cited])
    assert verified is not None
    claim = SynthesizedClaim(text="Air quality claim", supporting_evidence=verified, confidence=0.5)

    assert claim.supporting_evidence[0].id == ev1.id
    assert claim.supporting_evidence[0].confidence == 0.95  # Preserved from pool
    assert mapper.matched_by_id_count == 1
    assert mapper.matched_by_text_fallback_count == 0
    assert mapper.citation_fallback_rate == 0.0


def test_fabricated_id_rejection() -> None:
    """Verify that a fabricated evidence_id without matching text is rejected."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    fake_id = uuid.uuid4()
    cited = RawCitedEvidence(
        evidence_id=fake_id,
        source="Fake Source",
        claim="Fabricated claim text",
        confidence=0.5,
    )
    verified = mapper.map_citations([cited])
    assert verified is None


def test_id_miss_text_fallback_success() -> None:
    """Verify that an unknown ID with unique matching source/claim text falls back to text match."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    unknown_id = uuid.uuid4()
    cited = RawCitedEvidence(
        evidence_id=unknown_id,
        source="OpenAQ API",
        claim="PM10 is 30 ug/m3 in Paris",
        confidence=0.5,
    )
    verified = mapper.map_citations([cited])
    assert verified is not None
    claim = SynthesizedClaim(text="Fallback claim", supporting_evidence=verified, confidence=0.5)

    assert claim.supporting_evidence[0].id == ev1.id
    assert mapper.matched_by_id_count == 0
    assert mapper.matched_by_text_fallback_count == 1
    assert mapper.citation_fallback_rate == 1.0


def test_text_fallback_failure() -> None:
    """Verify that a missing ID with non-matching text is rejected."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    cited = RawCitedEvidence(
        evidence_id=None,
        source="NOAA API",
        claim="Sea surface temperature is 18C",
        confidence=0.5,
    )
    verified = mapper.map_citations([cited])
    assert verified is None


def test_graceful_degradation_model_ignores_ids() -> None:
    """Verify model output omitting evidence_id completely still succeeds via fallback path."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    cited = RawCitedEvidence(
        evidence_id=None,
        source="OpenAQ API",
        claim="PM10 is 30 ug/m3 in Paris",
        confidence=0.95,
    )
    verified = mapper.map_citations([cited])
    assert verified is not None

    assert mapper.citation_missing_id_count == 1
    assert mapper.matched_by_text_fallback_count == 1
    assert mapper.citation_fallback_rate == 1.0


def test_duplicate_claim_text_disambiguation() -> None:
    """Prove ID matching selects correct Evidence when multiple items share claim text."""
    # Two evidence items with identical source and claim text, but different confidence scores / IDs
    ev_high = Evidence(source="OpenAQ API", claim="PM10 high level", confidence=0.99)
    ev_low = Evidence(source="OpenAQ API", claim="PM10 high level", confidence=0.20)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev_high, ev_low])

    mapper = CitationMapper([agent_output])

    # Cite specifically ev_low by its ID
    cited = RawCitedEvidence(
        evidence_id=ev_low.id,
        source="OpenAQ API",
        claim="PM10 high level",
        confidence=0.20,
    )
    verified = mapper.map_citations([cited])
    assert verified is not None
    claim = SynthesizedClaim(
        text="Low confidence observation",
        supporting_evidence=verified,
        confidence=0.20,
    )

    assert claim.supporting_evidence[0].id == ev_low.id
    assert claim.supporting_evidence[0].confidence == 0.20
    assert mapper.matched_by_id_count == 1
    assert mapper.matched_by_text_fallback_count == 0


def test_ambiguous_text_fallback_rejection() -> None:
    """Verify multiple evidence items with identical text without valid IDs are rejected."""
    ev1 = Evidence(source="OpenAQ API", claim="Duplicate claim text", confidence=0.99)
    ev2 = Evidence(source="OpenAQ API", claim="Duplicate claim text", confidence=0.20)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1, ev2])

    mapper = CitationMapper([agent_output])

    cited = RawCitedEvidence(
        evidence_id=None,
        source="OpenAQ API",
        claim="Duplicate claim text",
        confidence=0.5,
    )
    verified = mapper.map_citations([cited])
    assert verified is None
    assert mapper.citation_ambiguous_fallback_count == 1


def test_invalid_uuid_string_falls_back_to_text() -> None:
    """Verify invalid UUID strings fail parsing, emit missing_id, and succeed via text fallback."""
    ev1 = Evidence(source="OpenAQ API", claim="PM10 is 30 ug/m3 in Paris", confidence=0.95)
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    invalid_cited = RawCitedEvidence(
        evidence_id=None,
        source="OpenAQ API",
        claim="PM10 is 30 ug/m3 in Paris",
        confidence=0.95,
    )
    invalid_cited.evidence_id = "hello-world"  # type: ignore[assignment]

    verified = mapper.map_citations([invalid_cited])
    assert verified is not None
    claim = SynthesizedClaim(
        text="Invalid UUID claim",
        supporting_evidence=verified,
        confidence=0.95,
    )

    assert claim.supporting_evidence[0].id == ev1.id
    assert mapper.citation_missing_id_count == 1
    assert mapper.matched_by_text_fallback_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_full_synthesis_integration_with_evidence_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full synthesis integration test verifying ID-based citations end-to-end with mocked LLM."""
    monkeypatch.setenv("EMBEDDING_API_KEY", "mock-key")
    from config.settings import get_settings

    get_settings.cache_clear()

    ev1 = Evidence(
        source="OpenAQ API (Station: Paris-South)",
        claim="PM10 is 30 ug/m3 in Paris",
        confidence=0.95,
    )
    agent_output = AgentOutput(agent_name="air_quality", evidence=[ev1])

    mock_llm_response = {
        "claims": [
            {
                "text": "At station Paris-South, PM10 is 30.0 ug/m3.",
                "supporting_evidence": [
                    {
                        "evidence_id": str(ev1.id),
                        "source": "OpenAQ API (Station: Paris-South)",
                        "claim": "PM10 is 30 ug/m3 in Paris",
                        "confidence": 0.95,
                    }
                ],
                "confidence": 0.95,
            }
        ],
        "evidence_gaps": [],
    }

    respx.post("https://api.openai.com/v1/chat/completions").respond(
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(mock_llm_response),
                    }
                }
            ]
        },
        status_code=200,
    )

    result = await synthesize([agent_output])

    assert len(result.claims) == 1
    assert result.claims[0].text == "At station Paris-South, PM10 is 30.0 ug/m3."
    assert result.claims[0].supporting_evidence[0].id == ev1.id


def test_backward_compatibility_legacy_text_citations() -> None:
    """Verify legacy claims without IDs pass via fallback."""
    ev1 = Evidence(source="USGS API", claim="Earthquake magnitude 5.1", confidence=0.90)
    agent_output = AgentOutput(agent_name="seismic", evidence=[ev1])

    mapper = CitationMapper([agent_output])

    legacy_cited = RawCitedEvidence(
        evidence_id=None,
        source="USGS API",
        claim="Earthquake magnitude 5.1",
        confidence=0.90,
    )
    verified = mapper.map_citations([legacy_cited])
    assert verified is not None

    assert mapper.matched_by_text_fallback_count == 1
