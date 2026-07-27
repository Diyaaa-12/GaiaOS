"""Unit and integration tests for agent scaffolding CLI tool (Phase 4 Milestone 8)."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from orchestrator.schemas.agent_io import AgentInput, AgentOutput
from scripts.scaffold_new_agent import scaffold_agent, validate_domain_name


def test_validate_domain_name_valid() -> None:
    """Verify valid domain names are accepted and normalized."""
    assert validate_domain_name("hydrology") == "hydrology"
    assert validate_domain_name("space_weather_2") == "space_weather_2"


def test_validate_domain_name_invalid_characters() -> None:
    """Verify invalid domain names with special characters raise ValueError."""
    with pytest.raises(ValueError, match="Invalid domain name"):
        validate_domain_name("hydro-logy!")

    with pytest.raises(ValueError, match="Invalid domain name"):
        validate_domain_name("space weather")


def test_validate_domain_name_path_traversal() -> None:
    """Verify path traversal attempts are detected and rejected."""
    with pytest.raises(ValueError, match="Path traversal"):
        validate_domain_name("../hydrology")

    with pytest.raises(ValueError, match="Path traversal"):
        validate_domain_name("hydrology/sub")


def test_validate_domain_name_reserved() -> None:
    """Verify reserved names are rejected."""
    with pytest.raises(ValueError, match="reserved"):
        validate_domain_name("registry")


def test_scaffold_agent_integration(tmp_path: Path) -> None:
    """Verify scaffold_agent generates valid agent code matching the I/O contract."""
    import ast

    # Setup scripts/new_agent_template in tmp_path
    template_src = Path.cwd() / "scripts" / "new_agent_template"
    template_dst = tmp_path / "scripts" / "new_agent_template"
    template_dst.mkdir(parents=True, exist_ok=True)

    for item in template_src.iterdir():
        if item.is_file():
            content = item.read_text(encoding="utf-8")
            (template_dst / item.name).write_text(content, encoding="utf-8")

    domain = "glaciology"
    paths = scaffold_agent(domain, root_dir=tmp_path)

    assert paths["init"].exists()
    assert paths["agent"].exists()
    assert paths["test"].exists()

    # --- Verify all three generated files are syntactically valid ---

    # __init__.py
    init_src = paths["init"].read_text(encoding="utf-8")
    try:
        ast.parse(init_src)
    except SyntaxError as exc:
        pytest.fail(f"Generated __init__.py has a syntax error: {exc}")

    # agent.py — also verify the AgentInput -> AgentOutput contract via dynamic import
    agent_src = paths["agent"].read_text(encoding="utf-8")
    try:
        ast.parse(agent_src)
    except SyntaxError as exc:
        pytest.fail(f"Generated agent.py has a syntax error: {exc}")

    spec = importlib.util.spec_from_file_location("glaciology_agent", str(paths["agent"]))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "run")
    assert inspect.iscoroutinefunction(mod.run)

    # Resolve annotations: `from __future__ import annotations` defers evaluation,
    # so raw .annotation returns a string. Use get_type_hints() to get actual types.
    import typing

    hints = typing.get_type_hints(mod.run)
    params = list(inspect.signature(mod.run).parameters.values())
    assert len(params) == 1
    assert hints.get(params[0].name) is AgentInput
    assert hints.get("return") is AgentOutput

    # test_agent.py
    test_src = paths["test"].read_text(encoding="utf-8")
    try:
        ast.parse(test_src)
    except SyntaxError as exc:
        pytest.fail(f"Generated test_agent.py has a syntax error: {exc}")
