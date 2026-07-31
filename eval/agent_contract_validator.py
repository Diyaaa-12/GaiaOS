"""Agent Contract & Benchmark Coverage Validator for GaiaOS — Phase 4 Milestone 8.

Verifies:
1. All registered domain agents in orchestrator.agents.registry conform to the
   AgentInput -> Awaitable[AgentOutput] callable contract signature.
2. Every registered domain agent has at least one benchmark question covering it in
   eval/benchmarks/questions.json.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

from orchestrator.agents.registry import AgentRegistry, agent_registry, register_agents
from orchestrator.schemas.agent_io import AgentInput, AgentOutput


def validate_runner_contract(runner: Callable[..., Any], domain: str = "plugin") -> list[str]:
    """Validate a single agent runner callable's signature against the AgentInput contract."""
    errors: list[str] = []
    if not (asyncio.iscoroutinefunction(runner) or inspect.iscoroutinefunction(runner)):
        errors.append(
            f"Agent '{domain}' runner callable is not an async coroutine function. "
            "Expected 'async def run(agent_input: AgentInput, bus: CollaborationBus | None = None)'"
        )
        return errors

    sig = inspect.signature(runner)
    params = list(sig.parameters.values())

    if len(params) < 1:
        errors.append(
            f"Agent '{domain}' runner takes {len(params)} parameters. "
            "Expected at least 1 parameter of type AgentInput."
        )
        return errors

    param_0 = params[0]
    type_hints = get_type_hints(runner) if hasattr(runner, "__annotations__") else {}
    param_type = type_hints.get(param_0.name, param_0.annotation)

    if (
        param_type is not inspect.Parameter.empty
        and param_type is not AgentInput
        and not (isinstance(param_type, type) and issubclass(param_type, AgentInput))
    ):
        errors.append(
            f"Agent '{domain}' first parameter '{param_0.name}' has type {param_type!r}. "
            "Expected type AgentInput."
        )

    return_type = type_hints.get("return", sig.return_annotation)
    if (
        return_type is not inspect.Signature.empty
        and return_type is not AgentOutput
        and not (isinstance(return_type, type) and issubclass(return_type, AgentOutput))
    ):
        errors.append(
            f"Agent '{domain}' return annotation is {return_type!r}. "
            "Expected return type AgentOutput."
        )

    return errors


def validate_agent_contracts(
    registry: AgentRegistry | None = None,
    questions_path: Path | None = None,
) -> list[str]:
    """Validate every registered agent's contract signature and benchmark coverage.

    Returns a list of human-readable error messages. An empty list indicates
    all validation checks passed.
    """
    errors: list[str] = []
    target_registry = registry or agent_registry

    # Ensure registry is populated if using default global singleton
    if registry is None:
        register_agents()

    domains = target_registry.list_domains()
    if not domains:
        errors.append("AgentRegistry contains zero registered domain agents.")
        return errors

    # 1. Validate signature contracts
    for domain in domains:
        try:
            runner = target_registry.get(domain)
        except Exception as exc:
            errors.append(f"Failed to retrieve runner for domain '{domain}': {exc}")
            continue

        runner_errors = validate_runner_contract(runner, domain)
        errors.extend(runner_errors)

    # 2. Validate evaluation benchmark dataset coverage
    q_file = questions_path or (Path.cwd() / "eval" / "benchmarks" / "questions.json")
    if not q_file.exists():
        errors.append(f"Evaluation benchmark file not found: {q_file}")
        return errors

    try:
        with open(q_file, encoding="utf-8") as f:
            questions = json.load(f)

        covered_domains: set[str] = set()
        for q in questions:
            for d in q.get("expected_domains", []):
                covered_domains.add(d)

        for domain in domains:
            if domain not in covered_domains:
                errors.append(
                    f"Registered domain agent '{domain}' has no benchmark coverage in "
                    f"{q_file.name}. Add at least one benchmark question with "
                    f"expected_domains containing '{domain}'."
                )
    except Exception as exc:
        errors.append(f"Failed to read evaluation benchmark dataset: {exc}")

    return errors


def main() -> None:
    """CLI entry point for running agent contract validation in CI."""
    errors = validate_agent_contracts()
    if errors:
        print("Agent Contract & Benchmark Validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    print("All registered agent contracts and benchmark coverage validation checks passed.")


if __name__ == "__main__":
    main()
