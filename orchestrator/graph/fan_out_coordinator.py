"""Coordinator for parallel fan-out/fan-in agent execution with timeouts and monitoring."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from orchestrator.agents.registry import agent_registry
from orchestrator.schemas.agent_io import AgentInput, AgentOutput

_log = get_logger(__name__)


def _make_failed_runner(domain: str) -> Any:
    async def failed_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(
            agent_name=domain,
            evidence=[],
            errors=[f"Agent implementation not found for domain: {domain}"],
        )

    return failed_runner


class FanOutCoordinator:
    """Async coordinator that executes multiple domain agents in parallel.

    Adheres to the Open/Closed Principle by depending on the dynamic AgentRegistry.
    """

    @staticmethod
    async def run(
        domains: list[str],
        investigation_id: Any,
        query: str,
        region_hint: str | None = None,
    ) -> list[AgentOutput]:
        """Run all matching domain agents in parallel and return their results."""
        settings = get_settings()
        timeout = settings.agent_timeout

        tasks = []
        for domain in domains:
            try:
                agent_runner = agent_registry.get(domain)
            except ValueError as e:
                _log.error("fan_out.registry.missing_agent", domain=domain, error=str(e))
                agent_runner = _make_failed_runner(domain)

            agent_input = AgentInput(
                investigation_id=investigation_id,
                query=query,
                region_hint=region_hint,
            )

            # Wrap the agent execution with timeout, logging, and error boundaries
            tasks.append(
                asyncio.create_task(
                    FanOutCoordinator._run_agent_with_monitoring(
                        domain, agent_runner, agent_input, timeout
                    )
                )
            )

        if not tasks:
            return []

        # Gather results concurrently. One failure must never cancel siblings.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: list[AgentOutput] = []
        for idx, res in enumerate(results):
            domain = domains[idx] if idx < len(domains) else "unknown"
            if isinstance(res, Exception):
                _log.error(
                    "fan_out.agent.unhandled_exception",
                    investigation_id=str(investigation_id),
                    agent_name=domain,
                    error=str(res),
                )
                processed_results.append(
                    AgentOutput(
                        agent_name=domain,
                        evidence=[],
                        errors=[f"Unhandled exception during agent run: {str(res)}"],
                    )
                )
            elif isinstance(res, AgentOutput):
                processed_results.append(res)
            else:
                processed_results.append(
                    AgentOutput(
                        agent_name=domain,
                        evidence=[],
                        errors=[f"Unexpected output type from runner: {type(res)}"],
                    )
                )

        return processed_results

    @staticmethod
    async def _run_agent_with_monitoring(
        domain: str,
        runner: Any,
        agent_input: AgentInput,
        timeout: float,
    ) -> AgentOutput:
        investigation_id_str = str(agent_input.investigation_id)
        start_time = time.perf_counter()

        _log.info(
            "fan_out.agent.started",
            investigation_id=investigation_id_str,
            agent_name=domain,
            outcome="started",
        )

        try:
            # Wrap the entire agent execution with timeout
            output = await asyncio.wait_for(runner(agent_input), timeout=timeout)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            _log.info(
                "fan_out.agent.completed",
                investigation_id=investigation_id_str,
                agent_name=domain,
                duration_ms=duration_ms,
                outcome="completed",
            )
            return output

        except TimeoutError:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            _log.error(
                "fan_out.agent.timeout",
                investigation_id=investigation_id_str,
                agent_name=domain,
                duration_ms=duration_ms,
                outcome="timeout",
            )
            return AgentOutput(
                agent_name=domain,
                evidence=[],
                errors=[f"Agent execution timed out after {timeout} seconds"],
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            _log.error(
                "fan_out.agent.failed",
                investigation_id=investigation_id_str,
                agent_name=domain,
                duration_ms=duration_ms,
                outcome="failed",
                error=str(e),
            )
            return AgentOutput(
                agent_name=domain,
                evidence=[],
                errors=[f"Agent execution failed: {str(e)}"],
            )
