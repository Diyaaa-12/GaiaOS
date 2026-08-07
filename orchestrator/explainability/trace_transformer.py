"""Trace transformation layer for GaiaOS Explainability (Phase 7 Milestone 1).

Converts raw investigation execution_trace JSONB and investigation metadata into a
structured, frontend-friendly graph shape (nodes, edges, summary, schema_version metadata).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class TraceEventTaxonomy(StrEnum):
    """Shared canonical event taxonomy enum across GaiaOS explainability surfaces."""

    PLANNING = "planning"
    SUPERVISOR = "supervisor"
    AGENT_STARTED = "agent_started"
    EVIDENCE_FOUND = "evidence_found"
    SYNTHESIZING = "synthesizing"
    CRITIC_FLAG = "critic_flag"
    REPLANNING = "replanning"
    COLLABORATION = "collaboration"
    FINALIZE = "finalize"
    UNKNOWN = "unknown"
    CUSTOM = "custom"


class TraceNode(BaseModel):
    """A node in the reasoning execution graph."""

    id: str
    label: str
    type: str  # TraceEventTaxonomy value or custom string
    status: str = "completed"  # completed | failed | skipped | flagged | degraded
    timestamp: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TraceEdge(BaseModel):
    """A directed edge in the reasoning execution graph."""

    id: str
    source: str
    target: str
    label: str | None = None
    type: str | None = "sequential"  # sequential | replan | collaboration | conditional


class TraceSummary(BaseModel):
    """High-level summary of execution trace statistics."""

    evidence_count: int = 0
    replan_count: int = 0
    critic_flag_count: int = 0
    collaboration_event_count: int = 0
    degraded_sources: list[str] = Field(default_factory=list)


class TraceMetadata(BaseModel):
    """Metadata container including contract schema_version and generated_at timestamp."""

    investigation_id: uuid.UUID
    schema_version: str = SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str
    complexity_tier: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    confidence: float | None = None
    node_count: int = 0
    edge_count: int = 0
    has_replan: bool = False
    has_collaboration: bool = False
    has_degraded_mode: bool = False


class InvestigationTraceResponse(BaseModel):
    """Response payload for GET /api/v1/investigations/{id}/trace."""

    investigation_id: uuid.UUID
    schema_version: str = SCHEMA_VERSION
    metadata: TraceMetadata
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    summary: TraceSummary


KNOWN_NODE_MAPPINGS: dict[str, tuple[str, str]] = {
    "supervisor": ("Supervisor Planner", TraceEventTaxonomy.PLANNING.value),
    "planning": ("Planner Initialized", TraceEventTaxonomy.PLANNING.value),
    "fan_out": ("Parallel Fan-Out Coordinator", TraceEventTaxonomy.AGENT_STARTED.value),
    "air_quality": ("Air Quality Domain Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "seismic": ("Seismic Hazard Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "atmosphere": ("Atmospheric Data Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "ocean": ("Oceanography Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "wildfire": ("Wildfire Risk Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "simulation": ("Plume & Transport Simulation Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "causal_chain": ("Causal Chain Reasoning Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "literature_rag": ("Literature Evidence RAG Agent", TraceEventTaxonomy.AGENT_STARTED.value),
    "synthesis": ("Cross-Domain Synthesis", TraceEventTaxonomy.SYNTHESIZING.value),
    "critic": ("Critic Claim Verification", TraceEventTaxonomy.CRITIC_FLAG.value),
    "replan": ("Targeted Replan Pass", TraceEventTaxonomy.REPLANNING.value),
    "finalize": ("Final Answer Synthesis & Persistence", TraceEventTaxonomy.FINALIZE.value),
}


def _classify_node(node_obj: Any) -> tuple[str, str, str, dict[str, Any]]:
    """Classify a raw node string or dict into (label, taxonomy_type, raw_name, extra_details)."""
    if isinstance(node_obj, dict):
        raw_name = str(
            node_obj.get("name")
            or node_obj.get("node")
            or node_obj.get("event")
            or "unknown_event"
        )
        clean_name = raw_name.strip().lower()
        extra_details = {k: v for k, v in node_obj.items() if k not in ("name", "node", "event")}
    else:
        raw_name = str(node_obj)
        clean_name = raw_name.strip().lower()
        extra_details = {}

    if clean_name in KNOWN_NODE_MAPPINGS:
        label, tax_type = KNOWN_NODE_MAPPINGS[clean_name]
        return label, tax_type, raw_name, extra_details

    if clean_name.endswith("_agent") or "agent" in clean_name:
        label = clean_name.replace("_", " ").title()
        return label, TraceEventTaxonomy.AGENT_STARTED.value, raw_name, extra_details

    label = clean_name.replace("_", " ").title()
    return label, TraceEventTaxonomy.CUSTOM.value, raw_name, extra_details


def transform_execution_trace(investigation: Any) -> InvestigationTraceResponse:
    """Transform an Investigation model instance into a structured InvestigationTraceResponse.

    Gracefully handles:
    - Pre-Phase 5 historical traces (missing collaboration, missing replan)
    - Phase 4 critic/replan traces
    - Phase 6 degraded mode traces
    - Missing or null execution_trace fields
    - Unknown or future plugin event types (preserving full custom payloads)
    """
    inv_id: uuid.UUID = getattr(investigation, "id", uuid.uuid4())
    inv_status: str = str(getattr(investigation, "status", "unknown"))
    complexity_tier: str | None = getattr(investigation, "complexity_tier", None)
    created_at_raw = getattr(investigation, "created_at", None)
    created_at: datetime = (
        created_at_raw if isinstance(created_at_raw, datetime) else datetime.now(UTC)
    )

    completed_at_raw = getattr(investigation, "completed_at", None)
    completed_at: datetime | None = (
        completed_at_raw if isinstance(completed_at_raw, datetime) else None
    )

    confidence_raw = getattr(investigation, "confidence", None)
    confidence: float | None = None
    if isinstance(confidence_raw, (int, float)):
        confidence = float(confidence_raw)
    elif isinstance(confidence_raw, str):
        try:
            confidence = float(confidence_raw)
        except ValueError:
            confidence = None

    raw_trace = getattr(investigation, "execution_trace", None)
    if not isinstance(raw_trace, dict):
        raw_trace = {}

    nodes_executed = raw_trace.get("nodes_executed")
    if not isinstance(nodes_executed, list):
        nodes_executed = []

    evidence_count = raw_trace.get("evidence_count", 0)
    if not isinstance(evidence_count, int):
        try:
            evidence_count = int(evidence_count)
        except (ValueError, TypeError):
            evidence_count = 0

    replan_count = raw_trace.get("replan_count", 0)
    if not isinstance(replan_count, int):
        try:
            replan_count = int(replan_count)
        except (ValueError, TypeError):
            replan_count = 0

    critic_flags_raw = raw_trace.get("critic_flags")
    if not isinstance(critic_flags_raw, list):
        critic_flags_raw = []

    collaboration_raw = raw_trace.get("collaboration") or raw_trace.get("collaboration_events")
    if not isinstance(collaboration_raw, list):
        collaboration_raw = []

    degraded_sources_raw = raw_trace.get("degraded_sources") or raw_trace.get("resilience_degraded")
    if isinstance(degraded_sources_raw, str):
        degraded_sources = [degraded_sources_raw]
    elif isinstance(degraded_sources_raw, list):
        degraded_sources = [str(s) for s in degraded_sources_raw]
    else:
        degraded_sources = []

    errors_raw = raw_trace.get("errors") or raw_trace.get("error")
    if isinstance(errors_raw, str):
        errors_list = [errors_raw]
    elif isinstance(errors_raw, list):
        errors_list = [str(e) for e in errors_raw]
    else:
        errors_list = []

    # Preserve any plugin_metadata or unparsed top-level trace attributes
    reserved_keys = {
        "nodes_executed",
        "evidence_count",
        "replan_count",
        "critic_flags",
        "collaboration",
        "collaboration_events",
        "degraded_sources",
        "resilience_degraded",
        "errors",
        "error",
        "domains",
        "matched_domains",
    }
    extra_plugin_metadata = {k: v for k, v in raw_trace.items() if k not in reserved_keys}

    nodes: list[TraceNode] = []
    edges: list[TraceEdge] = []

    # 1. Build nodes from nodes_executed or infer fallback flow
    if nodes_executed:
        prev_node_id: str | None = None
        for idx, node_item in enumerate(nodes_executed):
            label, tax_type, raw_name, extra_details = _classify_node(node_item)
            node_id = f"node_{idx}_{raw_name}"

            node_status = "completed"
            details: dict[str, Any] = {"raw_item": node_item, **extra_details}

            if extra_plugin_metadata:
                details["plugin_context"] = extra_plugin_metadata

            if str(node_item) == "critic" and critic_flags_raw:
                node_status = "flagged"
                details["critic_flags"] = critic_flags_raw
            elif str(node_item) == "fan_out":
                domains = raw_trace.get("domains") or raw_trace.get("matched_domains")
                if domains:
                    details["domains"] = domains
            elif tax_type == TraceEventTaxonomy.AGENT_STARTED.value:
                details["evidence_count"] = evidence_count
                if any(str(node_item) in s or s in str(node_item) for s in degraded_sources):
                    node_status = "degraded"
                    details["degraded_reason"] = (
                        "Circuit breaker tripped / degraded mode fallback"
                    )

            if inv_status == "failed" and idx == len(nodes_executed) - 1:
                node_status = "failed"
                details["errors"] = errors_list

            nodes.append(
                TraceNode(
                    id=node_id,
                    label=label,
                    type=tax_type,
                    status=node_status,
                    details=details,
                )
            )

            if prev_node_id:
                edge_type = "replan" if str(node_item) == "replan" else "sequential"
                edges.append(
                    TraceEdge(
                        id=f"edge_{prev_node_id}_to_{node_id}",
                        source=prev_node_id,
                        target=node_id,
                        type=edge_type,
                    )
                )
            prev_node_id = node_id
    else:
        # Fallback for empty / minimal traces
        start_id = "node_start"
        status_color = "completed" if inv_status == "complete" else (
            "failed" if inv_status == "failed" else "completed"
        )
        fallback_details = {"errors": errors_list} if errors_list else {"trace": "minimal"}
        if extra_plugin_metadata:
            fallback_details["plugin_context"] = extra_plugin_metadata
        nodes.append(
            TraceNode(
                id=start_id,
                label=f"Investigation ({inv_status})",
                type=TraceEventTaxonomy.PLANNING.value,
                status=status_color,
                details=fallback_details,
            )
        )

    # 2. Process Critic Flags into child details / nodes if present
    if critic_flags_raw:
        critic_nodes = [n for n in nodes if n.type == TraceEventTaxonomy.CRITIC_FLAG.value]
        if not critic_nodes:
            c_id = f"node_critic_flags_{len(nodes)}"
            nodes.append(
                TraceNode(
                    id=c_id,
                    label="Critic Verification",
                    type=TraceEventTaxonomy.CRITIC_FLAG.value,
                    status="flagged",
                    details={"critic_flags": critic_flags_raw},
                )
            )
            if len(nodes) > 1:
                edges.append(
                    TraceEdge(
                        id=f"edge_{nodes[-2].id}_to_{c_id}",
                        source=nodes[-2].id,
                        target=c_id,
                        type="sequential",
                    )
                )

    # 3. Process Collaboration Events
    has_collaboration = len(collaboration_raw) > 0
    if has_collaboration:
        for c_idx, c_event in enumerate(collaboration_raw):
            c_id = f"node_collab_{c_idx}"
            from_agent = (
                c_event.get("from_agent", "unknown")
                if isinstance(c_event, dict)
                else "agent"
            )
            to_agent = (
                c_event.get("to_agent", "all")
                if isinstance(c_event, dict)
                else "peer"
            )
            nodes.append(
                TraceNode(
                    id=c_id,
                    label=f"Collaboration ({from_agent} → {to_agent})",
                    type=TraceEventTaxonomy.COLLABORATION.value,
                    status="completed",
                    details=c_event if isinstance(c_event, dict) else {"event": str(c_event)},
                )
            )
            src_node = next((n for n in nodes if from_agent in n.id), None)
            target_node = next((n for n in nodes if to_agent in n.id), None)
            if src_node and target_node:
                edges.append(
                    TraceEdge(
                        id=f"edge_collab_{c_idx}",
                        source=src_node.id,
                        target=target_node.id,
                        label="peer_refinement",
                        type="collaboration",
                    )
                )

    has_replan = (
        replan_count > 0 or any(n.type == TraceEventTaxonomy.REPLANNING.value for n in nodes)
    )
    has_degraded_mode = len(degraded_sources) > 0 or any(n.status == "degraded" for n in nodes)

    summary = TraceSummary(
        evidence_count=evidence_count,
        replan_count=replan_count,
        critic_flag_count=len(critic_flags_raw),
        collaboration_event_count=len(collaboration_raw),
        degraded_sources=degraded_sources,
    )

    metadata = TraceMetadata(
        investigation_id=inv_id,
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        status=inv_status,
        complexity_tier=complexity_tier,
        created_at=created_at,
        completed_at=completed_at,
        confidence=confidence,
        node_count=len(nodes),
        edge_count=len(edges),
        has_replan=has_replan,
        has_collaboration=has_collaboration,
        has_degraded_mode=has_degraded_mode,
    )

    return InvestigationTraceResponse(
        investigation_id=inv_id,
        schema_version=SCHEMA_VERSION,
        metadata=metadata,
        nodes=nodes,
        edges=edges,
        summary=summary,
    )
