"""Tests for the Literature Agent orchestration, registry, and classifier routing."""

from __future__ import annotations

import os
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import get_settings
from orchestrator.agents.registry import agent_registry
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.agents.literature_rag.agent import run as run_literature
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from db.repository import LiteratureRepository
from db.session import AsyncSessionLocal


class TestLiteratureAgent:
    """Verifies Literature agent registry, query classification, execution, and error flows."""

    def test_agent_is_registered(self) -> None:
        """Verify that the literature agent is registered in the agent registry."""
        assert "literature" in agent_registry.list_domains()
        runner = agent_registry.get("literature")
        assert runner == run_literature

    @pytest.mark.asyncio
    async def test_query_classification_routing(self) -> None:
        """Verify that literature-focused queries are routed to the literature domain."""
        result = await classify_query_complexity("Show me research papers on seismic faults in Tokyo")
        assert "literature" in result["matched_domains"]

        result = await classify_query_complexity("What does the latest literature report say about tsunami risks?")
        assert "literature" in result["matched_domains"]

    @pytest.mark.asyncio
    async def test_agent_successful_execution(self) -> None:
        """Verify Literature agent executes hybrid search successfully and returns AgentOutput."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Planetary risk literature",
            region_hint="Global",
        )

        mock_evidence = [
            MagicMock(spec=Evidence, claim="Found proof", source="doc1", confidence=0.8)
        ]

    @pytest.mark.asyncio
    async def test_agent_successful_execution(self) -> None:
        """Verify Literature agent executes hybrid search successfully and returns AgentOutput."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Planetary risk literature",
            region_hint="Global",
        )

        mock_evidence = [
            MagicMock(spec=Evidence, claim="Found proof", source="doc1", confidence=0.8)
        ]

        # Mock the repository search method and session local
        with patch("orchestrator.agents.literature_rag.agent.AsyncSessionLocal", MagicMock()):
            with patch.object(LiteratureRepository, "hybrid_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = mock_evidence
                
                output = await run_literature(agent_input)

                assert isinstance(output, AgentOutput)
                assert output.agent_name == "literature"
                assert len(output.evidence) == 1
                assert output.evidence[0].claim == "Found proof"
                assert not output.errors

    @pytest.mark.asyncio
    async def test_agent_embedding_failure_handling(self) -> None:
        """Verify embedding provider failure returns explicit error and does not fail silently."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Failing query",
            region_hint=None,
        )

        # Set environment variable to simulate embedding failure in MockEmbeddingProvider
        os.environ["SIMULATE_EMBEDDING_FAILURE"] = "true"
        try:
            with patch("orchestrator.agents.literature_rag.agent.AsyncSessionLocal", MagicMock()):
                output = await run_literature(agent_input)
                
                assert isinstance(output, AgentOutput)
                assert output.agent_name == "literature"
                assert not output.evidence
                assert len(output.errors) == 1
                assert "embedding service unreachable" in output.errors[0]
        finally:
            os.environ.pop("SIMULATE_EMBEDDING_FAILURE", None)

    @pytest.mark.asyncio
    async def test_agent_empty_corpus_handling(self) -> None:
        """Verify empty corpus returns empty evidence and no errors."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="No matching papers",
            region_hint=None,
        )

        with patch("orchestrator.agents.literature_rag.agent.AsyncSessionLocal", MagicMock()):
            with patch.object(LiteratureRepository, "hybrid_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = []
                
                output = await run_literature(agent_input)

                assert isinstance(output, AgentOutput)
                assert output.agent_name == "literature"
                assert not output.evidence
                assert not output.errors
