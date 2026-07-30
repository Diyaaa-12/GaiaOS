"""Unit and regression tests for Phase 5 Milestone 5 cross-domain synthesis."""

from __future__ import annotations

import uuid

import pytest

from orchestrator.agents.critic.agent import verify as critic_verify
from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.agents.synthesis.citation_mapper import CitationMapper
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.synthesis import SynthesisOutput, SynthesizedClaim


def test_citation_mapper_get_cited_domains() -> None:
    """Verifies CitationMapper.get_cited_domains extracts distinct domains correctly."""
    ev_ocean1 = Evidence(
        id=uuid.uuid4(),
        source="NOAA Ocean API",
        claim="SST anomaly in Pacific",
    )
    ev_ocean2 = Evidence(
        id=uuid.uuid4(),
        source="NOAA Ocean API",
        claim="Tsunami buoy reading",
    )
    ev_seismic = Evidence(
        id=uuid.uuid4(),
        source="USGS Seismic API",
        claim="Mag 6.2 quake near Tokyo",
    )

    outputs = [
        AgentOutput(agent_name="ocean", evidence=[ev_ocean1, ev_ocean2]),
        AgentOutput(agent_name="seismic", evidence=[ev_seismic]),
    ]

    mapper = CitationMapper(outputs)

    # Claim citing 2 evidence items from Ocean domain only
    single_domain_claim = SynthesizedClaim(
        text="Ocean temperatures and buoy readings are elevated.",
        claim_type="single_domain",
        supporting_evidence=[ev_ocean1, ev_ocean2],
    )
    ocean_domains = mapper.get_cited_domains(single_domain_claim)
    assert ocean_domains == {"ocean"}

    # Claim citing evidence from Ocean AND Seismic domains
    cross_domain_claim = SynthesizedClaim(
        text="Seismic event linked to ocean sea surface temperature shift.",
        claim_type="cross_domain_pattern",
        supporting_evidence=[ev_ocean1, ev_seismic],
    )
    multi_domains = mapper.get_cited_domains(cross_domain_claim)
    assert multi_domains == {"ocean", "seismic"}


@pytest.mark.asyncio
async def test_cross_domain_rejection_duplicate_same_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: Duplicate citations from the same domain (Ocean, Ocean, Ocean)

    must count as 1 distinct domain, causing cross_domain_pattern claim to be rejected/downgraded.
    """
    ev1 = Evidence(id=uuid.uuid4(), source="NOAA Ocean API", claim="Ocean temp 1")
    ev2 = Evidence(id=uuid.uuid4(), source="NOAA Ocean API", claim="Ocean temp 2")
    ev3 = Evidence(id=uuid.uuid4(), source="NOAA Ocean API", claim="Ocean temp 3")

    ocean_output = AgentOutput(agent_name="ocean", evidence=[ev1, ev2, ev3])

    # Mock LLM returning a cross_domain_pattern claim backed only by Ocean evidence
    mock_llm_json = (
        "{\n"
        '  "claims": [\n'
        "    {\n"
        '      "text": "Fake cross-domain pattern based only on ocean data.",\n'
        '      "claim_type": "cross_domain_pattern",\n'
        '      "supporting_evidence": [\n'
        f'        {{"evidence_id": "{ev1.id}", "source": "{ev1.source}", '
        '"claim": "c1", "confidence": 0.9},\n'
        f'        {{"evidence_id": "{ev2.id}", "source": "{ev2.source}", '
        '"claim": "c2", "confidence": 0.9},\n'
        f'        {{"evidence_id": "{ev3.id}", "source": "{ev3.source}", '
        '"claim": "c3", "confidence": 0.9}\n'
        "      ],\n"
        '      "confidence": 0.9\n'
        "    }\n"
        "  ],\n"
        '  "evidence_gaps": []\n'
        "}"
    )

    async def mock_query_llm(messages: list[dict], response_format: dict) -> str:
        return mock_llm_json

    monkeypatch.setattr("orchestrator.agents.synthesis.agent.query_llm", mock_query_llm)

    result = await synthesize([ocean_output])

    # Verify the invalid cross_domain_pattern claim was rejected (dropped)
    # due to insufficient distinct domains (1 < 2), triggering unable-to-gather fallback claim.
    assert len(result.claims) == 1
    assert "Unable to gather" in result.claims[0].text


@pytest.mark.asyncio
async def test_cross_domain_acceptance_multidomain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that a claim citing >=2 distinct domains is accepted as cross_domain_pattern."""
    ev_seismic = Evidence(id=uuid.uuid4(), source="USGS Seismic API", claim="Quake 6.0")
    ev_ocean = Evidence(id=uuid.uuid4(), source="NOAA Ocean API", claim="Tsunami alert")

    outputs = [
        AgentOutput(agent_name="seismic", evidence=[ev_seismic]),
        AgentOutput(agent_name="ocean", evidence=[ev_ocean]),
    ]

    mock_llm_json = (
        "{\n"
        '  "claims": [\n'
        "    {\n"
        '      "text": "Seismic activity triggered coastal ocean tsunami alerts.",\n'
        '      "claim_type": "cross_domain_pattern",\n'
        '      "supporting_evidence": [\n'
        f'        {{"evidence_id": "{ev_seismic.id}", "source": "{ev_seismic.source}", '
        '"claim": "c1", "confidence": 0.95},\n'
        f'        {{"evidence_id": "{ev_ocean.id}", "source": "{ev_ocean.source}", '
        '"claim": "c2", "confidence": 0.95}\n'
        "      ],\n"
        '      "confidence": 0.95\n'
        "    }\n"
        "  ],\n"
        '  "evidence_gaps": []\n'
        "}"
    )

    async def mock_query_llm(messages: list[dict], response_format: dict) -> str:
        return mock_llm_json

    monkeypatch.setattr("orchestrator.agents.synthesis.agent.query_llm", mock_query_llm)

    result = await synthesize(outputs)

    assert len(result.claims) == 1
    assert result.claims[0].claim_type == "cross_domain_pattern"


@pytest.mark.asyncio
async def test_single_domain_behavior_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: Existing single-domain claims remain unchanged."""
    ev = Evidence(id=uuid.uuid4(), source="OpenAQ API", claim="PM2.5 reading")
    aq_output = AgentOutput(agent_name="air_quality", evidence=[ev])

    mock_llm_json = (
        "{\n"
        '  "claims": [\n'
        "    {\n"
        '      "text": "Air quality PM2.5 level is 15 ug/m3.",\n'
        '      "claim_type": "single_domain",\n'
        '      "supporting_evidence": [\n'
        f'        {{"evidence_id": "{ev.id}", "source": "{ev.source}", '
        '"claim": "c1", "confidence": 0.9}\n'
        "      ],\n"
        '      "confidence": 0.9\n'
        "    }\n"
        "  ],\n"
        '  "evidence_gaps": []\n'
        "}"
    )

    async def mock_query_llm(messages: list[dict], response_format: dict) -> str:
        return mock_llm_json

    monkeypatch.setattr("orchestrator.agents.synthesis.agent.query_llm", mock_query_llm)

    result = await synthesize([aq_output])

    assert len(result.claims) == 1
    assert result.claims[0].claim_type == "single_domain"
    assert result.claims[0].text == "Air quality PM2.5 level is 15 ug/m3."


@pytest.mark.asyncio
async def test_critic_elevated_scrutiny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies Critic agent receives claim_type and scrutinizes claims."""
    ev1 = Evidence(id=uuid.uuid4(), source="USGS", claim="Quake 6.0")
    ev2 = Evidence(id=uuid.uuid4(), source="NOAA", claim="Sea temp rise")

    claim_cross = SynthesizedClaim(
        text="Seismic activity causing warming ocean currents.",
        claim_type="cross_domain_pattern",
        supporting_evidence=[ev1, ev2],
    )

    synthesis_output = SynthesisOutput(claims=[claim_cross], evidence_gaps=[])

    mock_critic_json = """{
        "flags": [
            {
                "claim_text": "Seismic activity causing warming ocean currents.",
                "flagged_reason": "Correlation implied without direct physical mechanism proof.",
                "severity": "high",
                "flagged_domains": ["seismic", "ocean"]
            }
        ]
    }"""

    async def mock_query_llm(messages: list[dict], response_format: dict) -> str:
        # Assert system prompt includes elevated scrutiny directive
        sys_msg = messages[0]["content"]
        assert "cross_domain_pattern" in sys_msg
        assert "elevated scrutiny" in sys_msg.lower()
        return mock_critic_json

    monkeypatch.setattr("orchestrator.agents.critic.agent.query_llm", mock_query_llm)

    flags = await critic_verify(synthesis_output)

    assert len(flags) == 1
    assert flags[0].severity == "high"
    assert flags[0].flagged_domains == ["seismic", "ocean"]
