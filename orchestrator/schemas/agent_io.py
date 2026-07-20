"""Typed I/O contracts for domain agents."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A supporting evidence item extracted by a domain agent."""

    source: str = Field(description="Name or URL of the data source.")
    claim: str = Field(description="The factual claim or observation extracted.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Assigned confidence level for this evidence item.",
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when this evidence was queried/scraped.",
    )
    document_id: str | None = Field(
        None,
        description="Identifier of the specific literature document.",
    )
    chunk_id: str | int | None = Field(
        None,
        description="Identifier of the specific text chunk within the document.",
    )
    title: str | None = Field(
        None,
        description="Title of the source document.",
    )
    source_url: str | None = Field(
        None,
        description="Original source URL of the document.",
    )
    extra_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra domain-specific metadata.",
    )


class AgentInput(BaseModel):
    """Input payload expected by a domain agent's run function."""

    investigation_id: uuid.UUID = Field(description="Unique ID of the parent investigation.")
    query: str = Field(description="User search query or instructions.")
    region_hint: str | None = Field(
        None,
        description="Optional location query boundary (e.g. 'Paris').",
    )


class AgentOutput(BaseModel):
    """Standardized output structure returned by all domain agents."""

    agent_name: str = Field(description="Name of the agent generating this output.")
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="List of retrieved evidence blocks.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Non-blocking tool-call or querying errors encountered.",
    )
