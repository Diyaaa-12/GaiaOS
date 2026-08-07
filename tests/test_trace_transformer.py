"""Unit tests for the GaiaOS trace transformation layer (Phase 7 Milestone 1)."""

from __future__ import annotations

from orchestrator.explainability.trace_transformer import (
    SCHEMA_VERSION,
    InvestigationTraceResponse,
    transform_execution_trace,
)
from tests.fixtures.historical_traces import (
    CORRUPTED_EMPTY_TRACE,
    FUTURE_PLUGIN_EVENT_TRACE,
    PHASE2_HISTORICAL_TRACE,
    PHASE4_REPLAN_CRITIC_TRACE,
    PHASE5_COLLABORATION_TRACE,
    PHASE6_DEGRADED_MODE_TRACE,
)


class TestTraceTransformer:
    """Test suite for transform_execution_trace across historical and future trace formats."""

    def test_phase2_historical_trace_transformation(self) -> None:
        """Phase 2 trace (nodes_executed, evidence_count) transforms cleanly."""
        res = transform_execution_trace(PHASE2_HISTORICAL_TRACE)
        assert isinstance(res, InvestigationTraceResponse)
        assert res.schema_version == SCHEMA_VERSION
        assert res.metadata.schema_version == SCHEMA_VERSION
        assert res.metadata.investigation_id == PHASE2_HISTORICAL_TRACE.id
        assert res.metadata.status == "complete"
        assert res.metadata.has_replan is False
        assert res.metadata.has_collaboration is False
        assert res.metadata.has_degraded_mode is False
        assert res.summary.evidence_count == 1
        assert len(res.nodes) == 5
        assert len(res.edges) == 4

        node_types = [n.type for n in res.nodes]
        expected_types = ["planning", "agent_started", "synthesizing", "critic_flag", "finalize"]
        assert node_types == expected_types

    def test_phase4_replan_critic_trace_transformation(self) -> None:
        """Phase 4 trace with critic flags and replan pass transforms and sets flags."""
        res = transform_execution_trace(PHASE4_REPLAN_CRITIC_TRACE)
        assert res.metadata.has_replan is True
        assert res.summary.replan_count == 1
        assert res.summary.critic_flag_count == 1

        critic_nodes = [n for n in res.nodes if n.type == "critic_flag"]
        assert len(critic_nodes) >= 1
        assert critic_nodes[0].status == "flagged"

        replan_nodes = [n for n in res.nodes if n.type == "replanning"]
        assert len(replan_nodes) >= 1

    def test_phase5_collaboration_trace_transformation(self) -> None:
        """Phase 5 trace with collaboration bus events creates collaboration nodes/edges."""
        res = transform_execution_trace(PHASE5_COLLABORATION_TRACE)
        assert res.metadata.has_collaboration is True
        assert res.summary.collaboration_event_count == 1

        collab_nodes = [n for n in res.nodes if n.type == "collaboration"]
        assert len(collab_nodes) == 1
        assert "air_quality" in collab_nodes[0].label

    def test_phase6_degraded_mode_trace_transformation(self) -> None:
        """Phase 6 trace with degraded sources marks nodes with degraded status."""
        res = transform_execution_trace(PHASE6_DEGRADED_MODE_TRACE)
        assert res.metadata.has_degraded_mode is True
        assert res.summary.degraded_sources == ["openaq"]

    def test_future_plugin_event_trace_transformation(self) -> None:
        """Unknown/future plugin event types transform gracefully and preserve payloads."""
        res = transform_execution_trace(FUTURE_PLUGIN_EVENT_TRACE)
        assert res.schema_version == SCHEMA_VERSION
        assert res.metadata.generated_at is not None
        labels = [n.label for n in res.nodes]
        assert "Custom Hydrology Plugin Agent" in labels
        assert "Future Quantum Synthesizer" in labels

        # Refinement 2: Assert unknown/plugin payload is preserved in node details
        hydrology_node = next(n for n in res.nodes if n.label == "Custom Hydrology Plugin Agent")
        expected_context = {
            "plugin_metadata": {"author": "external_researcher", "version": "2.1.0"}
        }
        assert hydrology_node.details.get("plugin_context") == expected_context

    def test_corrupted_empty_trace_transformation(self) -> None:
        """Corrupted/null trace returns valid response instead of throwing exception."""
        res = transform_execution_trace(CORRUPTED_EMPTY_TRACE)
        assert res.schema_version == SCHEMA_VERSION
        assert res.metadata.generated_at is not None
        assert res.metadata.status == "failed"
        assert len(res.nodes) >= 1
        assert res.summary.evidence_count == 0

    def test_malformed_plugin_payload_transformation(self) -> None:
        """Malformed plugin payloads (nested objects, invalid types) return valid response."""
        import uuid
        from types import SimpleNamespace

        malformed_inv = SimpleNamespace(
            id=uuid.uuid4(),
            status="complete",
            complexity_tier="complex",
            created_at=None,
            completed_at=None,
            confidence="invalid_confidence",
            execution_trace={
                "nodes_executed": [
                    {"event": "custom_plugin", "payload": {"deep": {"nested": [1, 2, 3]}}},
                    12345,  # Non-string, non-dict item
                    None,
                ],
                "evidence_count": "invalid_count",
                "replan_count": {"invalid": "dict_instead_of_int"},
                "critic_flags": "not_a_list",
                "collaboration": [{"invalid_event": True}],
                "degraded_sources": 999,
            },
        )

        res = transform_execution_trace(malformed_inv)
        assert res.schema_version == SCHEMA_VERSION
        assert res.metadata.generated_at is not None
        assert len(res.nodes) >= 1
        assert res.summary.evidence_count == 0
        assert res.summary.replan_count == 0

        custom_node = next((n for n in res.nodes if "custom_plugin" in n.id), None)
        assert custom_node is not None
        assert custom_node.details.get("payload") == {"deep": {"nested": [1, 2, 3]}}

