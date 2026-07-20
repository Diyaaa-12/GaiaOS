"""Unit tests for the Causal Chain agent registry, classifier, and execution pathways."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.agents.causal_chain.agent import run as run_causal_chain
from orchestrator.agents.registry import agent_registry
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence


class TestCausalChainAgent:
    """Verifies Causal Chain agent registration, classification patterns, and run execution."""

    def test_agent_is_registered(self) -> None:
        """Verify that the causal_chain agent is registered in the agent registry."""
        assert "causal_chain" in agent_registry.list_domains()
        runner = agent_registry.get("causal_chain")
        assert runner == run_causal_chain

    @pytest.mark.asyncio
    async def test_query_classification_routing(self) -> None:
        """Verify that causal-focused queries are routed to the causal_chain domain."""
        result = await classify_query_complexity(
            "Find causal chains for earthquake triggered landslides"
        )
        assert "causal_chain" in result["matched_domains"]

        result = await classify_query_complexity(
            "Show historical analogues for Tokyo seismic triggers"
        )
        assert "causal_chain" in result["matched_domains"]

    @pytest.mark.asyncio
    async def test_agent_successful_execution(self) -> None:
        """Verify Causal Chain agent runs find_causal_chain and returns AgentOutput."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Tokyo seismic triggers",
            region_hint="Tokyo",
        )

        mock_evidence = [
            Evidence(
                source="Causal Chain Traversal",
                claim="Tokyo earthquake triggered landslide",
                confidence=0.85,
                document_id="causal_chain",
                chunk_id="evt_123",
                title="Causal Path",
                source_url="http://db.planetaryrisk.org",
                extra_metadata={
                    "visited_event_ids": ["evt_123"],
                    "event_chain_path": ["earthquake", "landslide"],
                },
            )
        ]

        with patch(
            "orchestrator.agents.causal_chain.agent.find_causal_chain",
            new_callable=AsyncMock,
        ) as mock_find:
            mock_find.return_value = mock_evidence

            output = await run_causal_chain(agent_input)

            assert isinstance(output, AgentOutput)
            assert output.agent_name == "causal_chain"
            assert len(output.evidence) == 1
            assert output.evidence[0].claim == "Tokyo earthquake triggered landslide"
            assert output.evidence[0].confidence == 0.85
            assert not output.errors

    @pytest.mark.asyncio
    async def test_agent_timeout_handling(self) -> None:
        """Verify that a statement timeout from find_causal_chain is caught gracefully."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Trigger recursive timeout query",
            region_hint="Tokyo",
        )

        with patch(
            "orchestrator.agents.causal_chain.agent.find_causal_chain",
            new_callable=AsyncMock,
        ) as mock_find:
            mock_find.side_effect = TimeoutError("causal chain query exceeded time budget")

            output = await run_causal_chain(agent_input)

            assert isinstance(output, AgentOutput)
            assert output.agent_name == "causal_chain"
            assert not output.evidence
            assert len(output.errors) == 1
            assert "causal chain query exceeded time budget" in output.errors[0]

    @pytest.mark.asyncio
    async def test_agent_general_error_handling(self) -> None:
        """Verify unexpected exceptions are caught and reported in errors list."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Trigger error",
            region_hint="Tokyo",
        )

        with patch(
            "orchestrator.agents.causal_chain.agent.find_causal_chain",
            new_callable=AsyncMock,
        ) as mock_find:
            mock_find.side_effect = RuntimeError("Fatal DB connection lost")

            output = await run_causal_chain(agent_input)

            assert isinstance(output, AgentOutput)
            assert output.agent_name == "causal_chain"
            assert not output.evidence
            assert len(output.errors) == 1
            assert "Failed to query causal chain: Fatal DB connection lost" in output.errors[0]
