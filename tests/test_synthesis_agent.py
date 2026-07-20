"""Unit tests for the Synthesis Agent and CitationMapper component."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.agents.synthesis.citation_mapper import CitationMapper
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.synthesis import SynthesizedClaim


class TestCitationMapper:
    """Verifies CitationMapper validation and structural integrity rules."""

    def test_valid_citation_mapping(self) -> None:
        """Verify that legitimate citations are correctly mapped and preserve original metadata."""
        actual_evidence = Evidence(
            source="air_quality_api",
            claim="PM2.5 index is 12 in Tokyo",
            confidence=0.9,
            document_id="aq_tokyo",
            chunk_id=1,
            title="Tokyo AQI Report",
            source_url="http://tokyo-aq.com",
            extra_metadata={"key": "val"},
        )

        outputs = [AgentOutput(agent_name="air_quality", evidence=[actual_evidence])]
        mapper = CitationMapper(outputs)

        claim = SynthesizedClaim(
            text="Tokyo has good air quality.",
            supporting_evidence=[
                Evidence(
                    source="air_quality_api",
                    claim="PM2.5 index is 12 in Tokyo",
                    confidence=0.5,  # basic/mocked fields
                )
            ],
            confidence=0.7,
        )

        assert mapper.validate_claim(claim) is True
        # Original rich metadata must be preserved
        assert claim.supporting_evidence[0].document_id == "aq_tokyo"
        assert claim.supporting_evidence[0].chunk_id == 1
        assert claim.supporting_evidence[0].extra_metadata == {"key": "val"}

    def test_fabricated_citation_dropped(self) -> None:
        """Verify that fabricated citations (not in the gathered pool) are rejected."""
        actual_evidence = Evidence(
            source="air_quality_api",
            claim="PM2.5 index is 12 in Tokyo",
            confidence=0.9,
        )

        outputs = [AgentOutput(agent_name="air_quality", evidence=[actual_evidence])]
        mapper = CitationMapper(outputs)

        # Claim tries to cite a fabricated piece of evidence
        claim = SynthesizedClaim(
            text="San Francisco is cloudy.",
            supporting_evidence=[
                Evidence(
                    source="sf_weather_api",
                    claim="Cloud cover is 90% in SF",
                    confidence=0.9,
                )
            ],
            confidence=0.8,
        )

        assert mapper.validate_claim(claim) is False


class TestSynthesisAgent:
    """Verifies Synthesis agent orchestration and edge case handling."""

    @pytest.mark.asyncio
    async def test_zero_evidence_fallback(self) -> None:
        """Verify zero evidence results in explicit 'unable to gather evidence' claim."""
        outputs = [
            AgentOutput(agent_name="air_quality", evidence=[], errors=["API timeout"]),
            AgentOutput(agent_name="wildfire", evidence=[]),
        ]

        result = await synthesize(outputs)

        assert len(result.claims) == 1
        assert "Unable to gather sufficient evidence" in result.claims[0].text
        assert result.claims[0].confidence == 0.0
        assert "air_quality" in result.evidence_gaps
        assert "wildfire" in result.evidence_gaps

    @pytest.mark.asyncio
    async def test_synthesis_successful_llm_run(self) -> None:
        """Verify synthesis merge and post-hoc confidence average calculation."""
        ev1 = Evidence(source="aq_api", claim="PM2.5 is 12", confidence=0.8)
        ev2 = Evidence(source="seismic_api", claim="No quakes", confidence=0.9)

        outputs = [
            AgentOutput(agent_name="air_quality", evidence=[ev1]),
            AgentOutput(agent_name="seismic", evidence=[ev2]),
        ]

        mock_llm_json = """{
            "claims": [
                {
                    "text": "The air quality is good.",
                    "supporting_evidence": [
                        {"source": "aq_api", "claim": "PM2.5 is 12", "confidence": 0.8}
                    ],
                    "confidence": 0.5
                },
                {
                    "text": "Seismic activity is quiet.",
                    "supporting_evidence": [
                        {"source": "seismic_api", "claim": "No quakes", "confidence": 0.9}
                    ],
                    "confidence": 0.5
                }
            ],
            "evidence_gaps": []
        }"""

        with patch(
            "orchestrator.agents.synthesis.agent.query_llm", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_llm_json

            result = await synthesize(outputs)

            assert len(result.claims) == 2
            # Confidence must be calculated as average of supporting evidence confidences
            assert result.claims[0].confidence == 0.8
            assert result.claims[1].confidence == 0.9
            assert not result.evidence_gaps
