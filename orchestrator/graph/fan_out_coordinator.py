"""Coordinator for parallel fan-out/fan-in agent execution with timeouts and monitoring."""

from __future__ import annotations

import asyncio
import inspect
import time
from datetime import UTC
from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from orchestrator.agents.registry import agent_registry
from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput

_log = get_logger(__name__)


def _make_failed_runner(domain: str) -> Any:
    async def failed_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
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

        # Construct one bus per investigation if collaboration feature flag is enabled
        bus: CollaborationBus | None = None
        if settings.enable_agent_collaboration:
            from orchestrator.graph.collaboration_bus import CollaborationBus

            bus = CollaborationBus(investigation_id=str(investigation_id))
            _log.info(
                "collaboration.bus.created",
                investigation_id=str(investigation_id),
            )

        domain_inputs: dict[str, AgentInput] = {}
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
            domain_inputs[domain] = agent_input

            # Wrap the agent execution with timeout, logging, and error boundaries
            tasks.append(
                asyncio.create_task(
                    FanOutCoordinator._run_agent_with_monitoring(
                        domain, agent_runner, agent_input, timeout, bus=bus
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
        # Stage B: Collaboration Refinement Check (Round 1)
        # Policy: Evaluate all peer messages for each agent, then deterministically
        # apply the latest applicable peer refinement (chronologically last broadcast).
        if bus is not None:
            snapshot = await bus.snapshot()
            if snapshot:
                for idx, domain in enumerate(domains):
                    try:
                        agent_runner = agent_registry.get(domain)
                    except ValueError:
                        continue

                    peer_hook = getattr(agent_runner, "on_peer_finding", None)
                    if callable(peer_hook):
                        initial_input = domain_inputs.get(domain)
                        if initial_input is None:
                            continue

                        peer_msgs = await bus.peer_findings(requesting_agent=domain, since_round=0)

                        # Evaluate all peer messages first to avoid iteration order ambiguity
                        candidates: list[tuple[Any, AgentInput]] = []
                        for peer_msg in peer_msgs:
                            # Peer hooks are optional extension points; exceptions are intentionally
                            # isolated so one faulty collaboration hook cannot interrupt fan-out
                            # execution.
                            try:
                                candidate_input = peer_hook(peer_msg, initial_input)
                                if candidate_input is not None:
                                    candidates.append((peer_msg, candidate_input))
                            except Exception as exc:
                                _log.error(
                                    "collaboration.peer_hook.error",
                                    investigation_id=str(investigation_id),
                                    agent_name=domain,
                                    from_agent=peer_msg.from_agent,
                                    error=str(exc),
                                )

                        # Deterministic Policy: Select the latest applicable peer refinement
                        if candidates:
                            last_peer_msg, selected_refined_input = candidates[-1]
                            _log.info(
                                "collaboration.refinement.triggered",
                                investigation_id=str(investigation_id),
                                agent_name=domain,
                                from_agent=last_peer_msg.from_agent,
                                round=1,
                            )
                            refined_output = await FanOutCoordinator._run_agent_with_monitoring(
                                domain,
                                agent_runner,
                                selected_refined_input,
                                timeout,
                                bus=bus,
                            )
                            processed_results[idx] = refined_output

        return processed_results

    @staticmethod
    async def _run_agent_with_monitoring(
        domain: str,
        runner: Any,
        agent_input: AgentInput,
        timeout: float,
        bus: CollaborationBus | None = None,
    ) -> AgentOutput:
        from datetime import datetime

        from cache.client import publish_event
        from orchestrator.schemas.events import (
            AgentCompletedData,
            AgentCompletedEvent,
            AgentStartedData,
            AgentStartedEvent,
        )

        async def _safe_publish(event):
            try:
                await publish_event(agent_input.investigation_id, event)
            except Exception as exc:
                _log.error("fan_out.event_publish_failed", error=str(exc))

        investigation_id_str = str(agent_input.investigation_id)
        start_time = time.perf_counter()

        _log.info(
            "fan_out.agent.started",
            investigation_id=investigation_id_str,
            agent_name=domain,
            outcome="started",
        )

        # Emit agent_started event
        start_evt = AgentStartedEvent(
            data=AgentStartedData(
                agent=domain,
                at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        )
        await _safe_publish(start_evt)

        try:
            # Dynamic execution supporting both (agent_input) and (agent_input, bus=None)
            try:
                sig = inspect.signature(runner)
                accepts_bus = "bus" in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                )
            except (ValueError, TypeError):
                accepts_bus = True

            coro = runner(agent_input, bus=bus) if accepts_bus else runner(agent_input)
            output = await asyncio.wait_for(coro, timeout=timeout)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            _log.info(
                "fan_out.agent.completed",
                investigation_id=investigation_id_str,
                agent_name=domain,
                duration_ms=duration_ms,
                outcome="completed",
            )

            # Emit agent_completed event
            complete_evt = AgentCompletedEvent(
                data=AgentCompletedData(
                    agent=domain,
                    evidence_count=len(output.evidence) if output and output.evidence else 0,
                )
            )
            await _safe_publish(complete_evt)

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

            # Emit agent_completed event with 0 evidence
            complete_evt = AgentCompletedEvent(
                data=AgentCompletedData(
                    agent=domain,
                    evidence_count=0,
                )
            )
            await _safe_publish(complete_evt)

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

            # Emit agent_completed event with 0 evidence
            complete_evt = AgentCompletedEvent(
                data=AgentCompletedData(
                    agent=domain,
                    evidence_count=0,
                )
            )
            await _safe_publish(complete_evt)

            return AgentOutput(
                agent_name=domain,
                evidence=[],
                errors=[f"Agent execution failed: {str(e)}"],
            )
