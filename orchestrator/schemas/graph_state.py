"""Shared state TypedDict representing LangGraph channel states."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, TypedDict

from orchestrator.schemas.agent_io import AgentOutput
from orchestrator.schemas.complexity import ComplexityTier
from orchestrator.schemas.synthesis import CriticFlag, SynthesisOutput


class TaskGraphState(TypedDict):
    """The graph execution state.

    Carried across nodes in LangGraph. Matches our schema contracts.
    """

    investigation_id: uuid.UUID
    query: str
    complexity_tier: ComplexityTier | None
    matched_domains: list[str]
    agent_outputs: Annotated[list[AgentOutput], operator.add]
    synthesis_output: SynthesisOutput | None
    critic_flags: list[CriticFlag]
    needs_simulation: bool
    final_answer: str | None
