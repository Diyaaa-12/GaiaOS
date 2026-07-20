"""Integration tests for parallel FanOutCoordinator execution."""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from orchestrator.agents.registry import agent_registry
from orchestrator.graph.fan_out_coordinator import FanOutCoordinator
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence


# Define dummy agent runners for testing
async def runner_fast(agent_input: AgentInput) -> AgentOutput:
    await asyncio.sleep(0.1)
    return AgentOutput(
        agent_name="fast",
        evidence=[Evidence(source="fast", claim="fast claim", confidence=0.95)],
    )


async def runner_slow(agent_input: AgentInput) -> AgentOutput:
    await asyncio.sleep(0.3)
    return AgentOutput(
        agent_name="slow",
        evidence=[Evidence(source="slow", claim="slow claim", confidence=0.85)],
    )


async def runner_fail(agent_input: AgentInput) -> AgentOutput:
    raise RuntimeError("Intentional runner failure")


async def runner_timeout(agent_input: AgentInput) -> AgentOutput:
    await asyncio.sleep(1.0)
    return AgentOutput(agent_name="timeout", evidence=[])


class TestFanOutCoordinator:
    """Verifies concurrency, timeout handling, and partial failure isolation."""

    @pytest.fixture(autouse=True)
    def setup_registry(self) -> None:
        # Register mock agents for testing
        agent_registry.register("test_fast", runner_fast)
        agent_registry.register("test_slow", runner_slow)
        agent_registry.register("test_fail", runner_fail)
        agent_registry.register("test_timeout", runner_timeout)

    async def test_parallel_execution_concurrency(self) -> None:
        investigation_id = uuid.uuid4()

        start_time = time.perf_counter()
        results = await FanOutCoordinator.run(
            domains=["test_fast", "test_slow"],
            investigation_id=investigation_id,
            query="Tokyo environmental events",
        )
        duration = time.perf_counter() - start_time

        assert len(results) == 2
        # Wall-clock execution time should be approx max(0.1, 0.3) = 0.3s, not sum (0.4s)
        # We assert duration is strictly below the sum (0.4s) to prove concurrency.
        assert duration < 0.39
        assert duration >= 0.29

        names = {res.agent_name for res in results}
        assert names == {"fast", "slow"}

        fast_res = next(r for r in results if r.agent_name == "fast")
        assert len(fast_res.evidence) == 1
        assert fast_res.evidence[0].claim == "fast claim"

    async def test_partial_failures(self) -> None:
        investigation_id = uuid.uuid4()
        results = await FanOutCoordinator.run(
            domains=["test_fast", "test_fail"],
            investigation_id=investigation_id,
            query="Tokyo environmental events",
        )
        assert len(results) == 2

        fast_res = next(r for r in results if r.agent_name == "fast")
        fail_res = next(r for r in results if r.agent_name == "test_fail")

        assert len(fast_res.evidence) == 1
        assert len(fast_res.errors) == 0

        assert len(fail_res.evidence) == 0
        assert len(fail_res.errors) == 1
        assert "Agent execution failed" in fail_res.errors[0]

    async def test_timeout_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Override the agent timeout in settings to 0.2s
        from config.settings import get_settings

        monkeypatch.setattr(get_settings(), "agent_timeout", 0.2)

        investigation_id = uuid.uuid4()
        results = await FanOutCoordinator.run(
            domains=["test_fast", "test_timeout"],
            investigation_id=investigation_id,
            query="Tokyo environmental events",
        )
        assert len(results) == 2

        fast_res = next(r for r in results if r.agent_name == "fast")
        timeout_res = next(r for r in results if r.agent_name == "test_timeout")

        # Fast finishes within 0.1s (< 0.2s timeout)
        assert len(fast_res.evidence) == 1
        assert len(fast_res.errors) == 0

        # Timeout finishes after 1.0s (> 0.2s timeout) -> gets wrapped in error
        assert len(timeout_res.evidence) == 0
        assert len(timeout_res.errors) == 1
        assert "timed out after 0.2 seconds" in timeout_res.errors[0]

    async def test_all_agents_failing(self) -> None:
        investigation_id = uuid.uuid4()
        results = await FanOutCoordinator.run(
            domains=["test_fail", "non_existent"],
            investigation_id=investigation_id,
            query="Tokyo environmental events",
        )
        assert len(results) == 2

        for res in results:
            assert len(res.evidence) == 0
            assert len(res.errors) == 1
