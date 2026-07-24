"""Unit and integration tests for bounded Critic replan loop logic and graph routing."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.agents.critic.replan import build_replan_targets, should_replan
from orchestrator.graph.builder import build_graph, route_after_critic
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.graph_state import TaskGraphState
from orchestrator.schemas.synthesis import CriticFlag, SynthesisOutput, SynthesizedClaim
from langchain_core.runnables import RunnableConfig


class TestShouldReplanUnit:
    """Unit tests for should_replan decision logic."""

    def test_disabled_by_flag_returns_false(self) -> None:
        """When enabled=False, should_replan returns False even with high severity flag."""
        high_flag = CriticFlag(
            claim_text="Contradictory PM2.5 claim",
            flagged_reason="High severity contradiction",
            severity="high",
        )
        assert should_replan([high_flag], replan_count=0, max_replans=2, enabled=False) is False

    def test_high_severity_flag_triggers_replan(self) -> None:
        """High severity flag triggers replan when replan_count < max_replans."""
        high_flag = CriticFlag(
            claim_text="Contradictory seismic magnitude",
            flagged_reason="USGS vs local station discrepancy",
            severity="high",
        )
        assert should_replan([high_flag], replan_count=0, max_replans=2, enabled=True) is True
        assert should_replan([high_flag], replan_count=1, max_replans=2, enabled=True) is True

    def test_medium_or_low_severity_does_not_trigger_replan(self) -> None:
        """Medium or low severity flags do not trigger replan."""
        med_flag = CriticFlag(
            claim_text="Slight overgeneralization",
            flagged_reason="Minor extrapolation",
            severity="medium",
        )
        low_flag = CriticFlag(
            claim_text="Formatting issue",
            flagged_reason="Unclear terminology",
            severity="low",
        )
        res = should_replan([med_flag, low_flag], replan_count=0, max_replans=2, enabled=True)
        assert res is False

    def test_max_replans_cap_boundary(self) -> None:
        """Replan count reaching max_replans returns False."""
        high_flag = CriticFlag(
            claim_text="Unresolved contradiction",
            flagged_reason="Persistent conflict",
            severity="high",
        )
        assert should_replan([high_flag], replan_count=2, max_replans=2, enabled=True) is False
        assert should_replan([high_flag], replan_count=3, max_replans=2, enabled=True) is False


class TestBuildReplanTargetsUnit:
    """Unit tests for build_replan_targets domain resolution."""

    def test_structured_metadata_priority(self) -> None:
        """Uses structured flagged_domains metadata when present on high-severity flags."""
        high_flag = CriticFlag(
            claim_text="Fault line depth anomaly",
            flagged_reason="Inconsistent hypocenter depth",
            severity="high",
            flagged_domains=["seismic", "ocean"],
        )
        targets = build_replan_targets([high_flag])
        assert targets == ["seismic", "ocean"]

    def test_keyword_mapping_fallback(self) -> None:
        """Falls back to keyword matching when flagged_domains metadata is absent."""
        high_flag = CriticFlag(
            claim_text="Wildfire smoke plume PM2.5 concentrations in San Francisco",
            flagged_reason="Smoke dispersion thermal hotspot mismatch",
            severity="high",
        )
        targets = build_replan_targets([high_flag])
        assert "air_quality" in targets or "wildfire" in targets

    def test_fallback_domains_used_when_no_match(self) -> None:
        """Uses fallback_domains when no metadata or keyword matches."""
        generic_flag = CriticFlag(
            claim_text="Abstract claim X",
            flagged_reason="Unspecified logical issue Z",
            severity="high",
        )
        targets = build_replan_targets([generic_flag], fallback_domains=["ocean"])
        assert targets == ["ocean"]

    def test_route_after_critic_routing(self) -> None:
        """route_after_critic routes to 'replan' or 'finalize' based on should_replan."""
        high_flag = CriticFlag(
            claim_text="Severe claim",
            flagged_reason="High error",
            severity="high",
        )
        state_trigger: TaskGraphState = {
            "investigation_id": uuid.uuid4(),
            "query": "Test query",
            "complexity_tier": None,
            "matched_domains": ["air_quality"],
            "agent_outputs": [],
            "synthesis_output": None,
            "critic_flags": [high_flag],
            "needs_simulation": False,
            "final_answer": None,
            "replan_count": 0,
        }

        with patch("orchestrator.agents.critic.replan.get_settings") as mock_settings:
            mock_settings.return_value.enable_replan_loop = True
            assert route_after_critic(state_trigger) == "replan"

        state_cap: TaskGraphState = dict(state_trigger)  # type: ignore
        state_cap["replan_count"] = 2
        with patch("orchestrator.agents.critic.replan.get_settings") as mock_settings:
            mock_settings.return_value.enable_replan_loop = True
            assert route_after_critic(state_cap) == "finalize"


@pytest.mark.asyncio
class TestReplanLoopIntegration:
    """Integration tests for graph replan loop execution and fallback."""

    async def test_graph_replan_loop_capped_unresolved_evidence_fallback(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Replan loop capping at 2 cycles appends 'Unresolved conflicting evidence.'."""
        from langgraph.checkpoint.memory import MemorySaver

        inv_id = uuid.uuid4()

        from db.models.investigation import Investigation
        inv = Investigation(
            id=inv_id,
            user_id="test_user",
            query="Conflicting seismic query",
            status="in_progress",
        )
        db_session.add(inv)
        await db_session.commit()

        synthesis_result = SynthesisOutput(
            claims=[
                SynthesizedClaim(
                    text="Conflicting fault displacement claim",
                    supporting_evidence=[
                        Evidence(source="USGS", claim="M4.2 event", confidence=0.8)
                    ],
                    confidence=0.8,
                )
            ]
        )
        high_flag = CriticFlag(
            claim_text="Conflicting fault displacement claim",
            flagged_reason="Persistent hypocenter contradiction",
            severity="high",
            flagged_domains=["seismic"],
        )

        dummy_output = AgentOutput(
            agent_name="seismic",
            evidence=[Evidence(source="USGS", claim="M4.2 event", confidence=0.8)],
        )

        patch_sess = patch("orchestrator.graph.builder.db_session.AsyncSessionLocal")
        patch_class = patch("orchestrator.graph.builder.classify_query_complexity")
        patch_fan = patch("orchestrator.graph.builder.FanOutCoordinator.run")
        patch_syn = patch("orchestrator.graph.builder.synthesize")
        patch_ver = patch("orchestrator.graph.builder.verify")
        patch_set = patch("orchestrator.agents.critic.replan.get_settings")

        with patch_sess as mock_session_factory, patch_class as mock_classify, \
             patch_fan as mock_fanout, patch_syn as mock_synthesize, \
             patch_ver as mock_verify, patch_set as mock_settings:

            mock_session_factory.return_value.__aenter__.return_value = db_session
            mock_settings.return_value.enable_replan_loop = True

            mock_classify.return_value = {
                "tier": "moderate",
                "matched_domains": ["seismic"],
                "needs_simulation": False,
            }
            mock_fanout.return_value = [dummy_output]
            mock_synthesize.return_value = synthesis_result
            mock_verify.return_value = [high_flag]

            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)

            initial_state: TaskGraphState = {
                "investigation_id": inv_id,
                "query": "Conflicting seismic query",
                "complexity_tier": None,
                "matched_domains": [],
                "agent_outputs": [],
                "synthesis_output": None,
                "critic_flags": [],
                "needs_simulation": False,
                "final_answer": None,
                "replan_count": 0,
            }

            config: RunnableConfig = {
                "configurable": {
                    "thread_id": str(inv_id),
                }
            }

            final_state = await graph.ainvoke(initial_state, config)
            
            assert final_state["replan_count"] == 2
            assert "Unresolved conflicting evidence." in final_state["final_answer"]

    async def test_graph_replan_loop_one_cycle_resolves(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Replan loop executes 1 targeted cycle and terminates cleanly when resolved."""
        from langgraph.checkpoint.memory import MemorySaver

        inv_id = uuid.uuid4()

        from db.models.investigation import Investigation
        inv = Investigation(
            id=inv_id,
            user_id="test_user",
            query="Air quality query",
            status="in_progress",
        )
        db_session.add(inv)
        await db_session.commit()

        synthesis_result = SynthesisOutput(
            claims=[
                SynthesizedClaim(
                    text="Resolved air quality claim",
                    supporting_evidence=[
                        Evidence(source="OpenAQ", claim="PM2.5 12", confidence=0.9)
                    ],
                    confidence=0.9,
                )
            ]
        )
        high_flag = CriticFlag(
            claim_text="Resolved air quality claim",
            flagged_reason="Initial high uncertainty",
            severity="high",
            flagged_domains=["air_quality"],
        )

        dummy_output = AgentOutput(
            agent_name="air_quality",
            evidence=[Evidence(source="OpenAQ", claim="PM2.5 12", confidence=0.9)],
        )

        patch_sess = patch("orchestrator.graph.builder.db_session.AsyncSessionLocal")
        patch_class = patch("orchestrator.graph.builder.classify_query_complexity")
        patch_aq = patch("orchestrator.graph.builder.run_air_quality")
        patch_fan = patch("orchestrator.graph.builder.FanOutCoordinator.run")
        patch_syn = patch("orchestrator.graph.builder.synthesize")
        patch_ver = patch("orchestrator.graph.builder.verify")
        patch_set = patch("orchestrator.agents.critic.replan.get_settings")

        with patch_sess as mock_session_factory, patch_class as mock_classify, \
             patch_aq as mock_run_aq, patch_fan as mock_fanout, \
             patch_syn as mock_synthesize, patch_ver as mock_verify, \
             patch_set as mock_settings:

            mock_session_factory.return_value.__aenter__.return_value = db_session
            mock_settings.return_value.enable_replan_loop = True

            mock_classify.return_value = {
                "tier": "trivial",
                "matched_domains": ["air_quality"],
                "needs_simulation": False,
            }
            mock_run_aq.return_value = dummy_output
            mock_fanout.return_value = [dummy_output]
            mock_synthesize.return_value = synthesis_result

            # Cycle 1 returns high flag, Cycle 2 returns empty list (resolved)
            mock_verify.side_effect = [[high_flag], []]

            checkpointer = MemorySaver()
            graph = build_graph(checkpointer=checkpointer)

            initial_state: TaskGraphState = {
                "investigation_id": inv_id,
                "query": "Air quality query",
                "complexity_tier": None,
                "matched_domains": [],
                "agent_outputs": [],
                "synthesis_output": None,
                "critic_flags": [],
                "needs_simulation": False,
                "final_answer": None,
                "replan_count": 0,
            }

            config: RunnableConfig = {
               "configurable": {
                  "thread_id": str(inv_id),
                }
            }

            final_state = await graph.ainvoke(initial_state, config)

            assert final_state["replan_count"] == 1
            assert "Unresolved conflicting evidence." not in final_state["final_answer"]
