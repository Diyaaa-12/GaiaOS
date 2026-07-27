"""Unit and integration tests for AgentContractValidator (Phase 4 Milestone 8)."""

from __future__ import annotations

import json
from pathlib import Path

from eval.agent_contract_validator import validate_agent_contracts
from orchestrator.agents.registry import AgentRegistry
from orchestrator.schemas.agent_io import AgentInput, AgentOutput


def test_registered_agent_contracts_pass_validation() -> None:
    """Verify all production registered agents pass contract validation with 0 errors."""
    errors = validate_agent_contracts()
    assert errors == [], f"Expected 0 validation errors, got: {errors}"


def test_non_conforming_agent_signature_failure() -> None:
    """Verify validator catches non-async or non-conforming runner signatures."""

    # Non-async function (sync)
    def sync_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name="dummy", evidence=[], errors=[])

    mock_registry = AgentRegistry()
    mock_registry.register("air_quality", sync_runner)  # type: ignore[arg-type]

    errors = validate_agent_contracts(registry=mock_registry)
    assert any("not an async coroutine" in err for err in errors)


def test_invalid_parameter_type_annotation_failure() -> None:
    """Verify validator catches runner signatures with non-AgentInput parameter types."""

    async def invalid_param_runner(agent_input: str) -> AgentOutput:  # type: ignore[override]
        return AgentOutput(agent_name="dummy", evidence=[], errors=[])

    mock_registry = AgentRegistry()
    mock_registry.register("air_quality", invalid_param_runner)  # type: ignore[arg-type]

    errors = validate_agent_contracts(registry=mock_registry)
    assert any("Expected type AgentInput" in err for err in errors)


def test_missing_benchmark_coverage_failure_path(tmp_path: Path) -> None:
    """Verify validator fails when a registered agent has no benchmark coverage."""

    async def dummy_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name="volcano", evidence=[], errors=[])

    mock_registry = AgentRegistry()
    mock_registry.register("volcano", dummy_runner)

    # Create dummy questions.json omitting 'volcano'
    dummy_questions = [
        {"id": "q1", "expected_domains": ["air_quality"]},
    ]
    q_file = tmp_path / "questions.json"
    q_file.write_text(json.dumps(dummy_questions), encoding="utf-8")

    errors = validate_agent_contracts(registry=mock_registry, questions_path=q_file)
    assert len(errors) == 1
    assert "volcano" in errors[0]
    assert "has no benchmark coverage" in errors[0]
