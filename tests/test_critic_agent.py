"""Unit tests for the Critic Agent verification pass."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.agents.critic.agent import verify
from orchestrator.schemas.agent_io import Evidence
from orchestrator.schemas.synthesis import SynthesisOutput, SynthesizedClaim


class TestCriticAgent:
    """Verifies Critic agent verification pass and error handling rules."""

    @pytest.mark.asyncio
    async def test_critic_verification_success(self) -> None:
        """Verify that Critic correctly flags claims that over-generalize."""
        ev = Evidence(source="seismic_api", claim="Micro-tremor detected", confidence=0.7)
        claim = SynthesizedClaim(
            text="Tokyo is expecting a major earthquake tomorrow.",
            supporting_evidence=[ev],
            confidence=0.7,
        )
        synthesis = SynthesisOutput(claims=[claim], evidence_gaps=[])

        mock_llm_json = (
            '{"flags": [{'
            '"claim_text": "Tokyo is expecting a major earthquake tomorrow.",'
            '"flagged_reason": "Evidence only reports a micro-tremor; '
            'predicting a major quake tomorrow is an over-extrapolation.",'
            '"severity": "high"}]}'
        )

        with patch(
            "orchestrator.agents.critic.agent.query_llm", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_llm_json

            flags = await verify(synthesis)

            assert len(flags) == 1
            assert flags[0].claim_text == "Tokyo is expecting a major earthquake tomorrow."
            assert flags[0].severity == "high"
            assert "over-extrapolation" in flags[0].flagged_reason

    @pytest.mark.asyncio
    async def test_critic_fails_open(self) -> None:
        """Verify that Critic fails open (returns empty list) if LLM call fails."""
        ev = Evidence(source="seismic_api", claim="Micro-tremor detected", confidence=0.7)
        claim = SynthesizedClaim(
            text="Tokyo is expecting a major earthquake tomorrow.",
            supporting_evidence=[ev],
            confidence=0.7,
        )
        synthesis = SynthesisOutput(claims=[claim], evidence_gaps=[])

        with patch(
            "orchestrator.agents.critic.agent.query_llm", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = RuntimeError("OpenAI API rate limit exceeded")

            flags = await verify(synthesis)

            # Verification fails open, returns empty list
            assert flags == []
