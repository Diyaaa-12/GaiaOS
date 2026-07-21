"""Schemas for investigation streaming events."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlanningData(BaseModel):
    """Payload for planning event."""

    status: str = "planning"


class PlanningEvent(BaseModel):
    """Event emitted when planning begins."""

    event: Literal["planning"] = "planning"
    data: PlanningData = Field(default_factory=PlanningData)


class AgentStartedData(BaseModel):
    """Payload for agent_started event."""

    agent: str
    at: str  # ISO-8601 string timestamp


class AgentStartedEvent(BaseModel):
    """Event emitted when a domain agent starts execution."""

    event: Literal["agent_started"] = "agent_started"
    data: AgentStartedData


class AgentCompletedData(BaseModel):
    """Payload for agent_completed event."""

    agent: str
    evidence_count: int


class AgentCompletedEvent(BaseModel):
    """Event emitted when a domain agent completes execution."""

    event: Literal["agent_completed"] = "agent_completed"
    data: AgentCompletedData


class SynthesizingEvent(BaseModel):
    """Event emitted when synthesis starts."""

    event: Literal["synthesizing"] = "synthesizing"
    data: dict = Field(default_factory=dict)


class CriticFlagData(BaseModel):
    """Payload for critic_flag event."""

    claim: str
    confidence: float
    reason: str


class CriticFlagEvent(BaseModel):
    """Event emitted when the Critic agent flags a claim."""

    event: Literal["critic_flag"] = "critic_flag"
    data: CriticFlagData


class DoneData(BaseModel):
    """Payload for done event."""

    investigation_id: UUID
    status: str = "complete"


class DoneEvent(BaseModel):
    """Event emitted when the investigation has completed execution."""

    event: Literal["done"] = "done"
    data: DoneData


InvestigationEvent = (
    PlanningEvent
    | AgentStartedEvent
    | AgentCompletedEvent
    | SynthesizingEvent
    | CriticFlagEvent
    | DoneEvent
)
