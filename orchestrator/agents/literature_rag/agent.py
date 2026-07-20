"""Literature domain agent using hybrid retrieval."""

from __future__ import annotations

import time

from config.settings import get_settings
from db.repository import LiteratureRepository
from db.session import AsyncSessionLocal
from orchestrator.agents.literature_rag.embedding import get_embedding_provider
from orchestrator.schemas.agent_io import AgentInput, AgentOutput


async def run(agent_input: AgentInput) -> AgentOutput:
    """Execute hybrid retrieval over planetary risk literature chunks.

    Orchestration-only: delegates the actual hybrid search and db queries
    completely to the LiteratureRepository layer.
    """
    settings = get_settings()
    errors: list[str] = []

    # 1. Resolve active embedding provider
    provider = get_embedding_provider(settings)

    # 2. Compute vector embedding for query
    embedding_start = time.perf_counter()
    try:
        query_embedding = await provider.embed_query(agent_input.query)
        embedding_duration_ms = int((time.perf_counter() - embedding_start) * 1000)
    except Exception as e:
        # Strict requirement: embedding service failure is returned as an error
        # and does not silently fall back to FTS-only retrieval.
        return AgentOutput(
            agent_name="literature",
            evidence=[],
            errors=[f"embedding service unreachable: {str(e)}"],
        )

    # 3. Query the database using LiteratureRepository
    if AsyncSessionLocal is None:
        return AgentOutput(
            agent_name="literature",
            evidence=[],
            errors=["Database session factory is not initialised."],
        )

    try:
        async with AsyncSessionLocal() as session:
            retrieval_start = time.perf_counter()
            evidence_list = await LiteratureRepository.hybrid_search(
                session=session,
                query=agent_input.query,
                query_embedding=query_embedding,
                k=10,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                embedding_duration_ms=embedding_duration_ms,
                retrieval_start_time=retrieval_start,
            )
            return AgentOutput(
                agent_name="literature",
                evidence=evidence_list,
                errors=errors,
            )
    except Exception as e:
        return AgentOutput(
            agent_name="literature",
            evidence=[],
            errors=[f"Hybrid search failed: {str(e)}"],
        )
