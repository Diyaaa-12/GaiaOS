"""Unit and integration tests for Phase 5 Milestone 6 — Agent Plugin Architecture."""

from __future__ import annotations

import uuid

import pytest
from packaging.version import Version

from orchestrator.__version__ import GAIAOS_VERSION, __version__
from orchestrator.agents.plugin_loader import (
    DuplicateDomainError,
    IncompatibleVersionError,
    PluginValidationError,
    load_and_validate_plugin,
    validate_plugin_compatibility,
    validate_required_settings,
)
from orchestrator.agents.registry import AgentRegistry
from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.plugin_manifest import PluginManifest
from orchestrator.schemas.uncertainty import UncertaintyEstimate


def test_canonical_version_truth() -> None:
    """Verifies that GAIAOS_VERSION is a valid semantic version string."""
    parsed = Version(GAIAOS_VERSION)
    assert parsed.major == 0
    assert GAIAOS_VERSION == __version__


def test_plugin_manifest_creation() -> None:
    """Verifies PluginManifest schema instantiation."""
    manifest = PluginManifest(
        name="gaiaos-test-plugin",
        version="1.0.0",
        domain="volcanic_activity",
        entry_point="dummy.module:run",
        gaiaos_version_range=">=0.5.0",
        required_settings=["TEST_API_KEY"],
        eval_benchmark_question_ids=["eval_q_001"],
    )
    assert manifest.name == "gaiaos-test-plugin"
    assert manifest.domain == "volcanic_activity"
    assert manifest.required_settings == ["TEST_API_KEY"]


def test_validate_plugin_compatibility_success() -> None:
    """Verifies compatible version ranges pass validation."""
    manifest = PluginManifest(
        name="test-plugin",
        version="1.0.0",
        domain="space_weather",
        entry_point="dummy:run",
        gaiaos_version_range=">=0.5.0,<1.0.0",
    )
    # Should not raise
    validate_plugin_compatibility(manifest)


def test_validate_plugin_compatibility_failure() -> None:
    """Verifies incompatible version ranges raise IncompatibleVersionError."""
    manifest = PluginManifest(
        name="test-plugin",
        version="1.0.0",
        domain="space_weather",
        entry_point="dummy:run",
        gaiaos_version_range=">=1.0.0",
    )
    with pytest.raises(IncompatibleVersionError) as exc_info:
        validate_plugin_compatibility(manifest)
    assert "requires GaiaOS version '>=1.0.0'" in str(exc_info.value)


def test_validate_required_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies required_settings check succeeds when present and fails when missing."""
    manifest = PluginManifest(
        name="test-plugin",
        version="1.0.0",
        domain="solar",
        entry_point="dummy:run",
        required_settings=["REQUIRED_DUMMY_KEY"],
    )

    # Missing setting -> raises PluginValidationError
    monkeypatch.delenv("REQUIRED_DUMMY_KEY", raising=False)
    with pytest.raises(PluginValidationError) as excinfo:
        validate_required_settings(manifest)
    assert "missing required setting" in str(excinfo.value)

    # Present setting -> passes
    monkeypatch.setenv("REQUIRED_DUMMY_KEY", "secret_value")
    validate_required_settings(manifest)


@pytest.mark.asyncio
async def test_load_and_validate_valid_plugin() -> None:
    """Verifies loading and contract validating a well-formed async runner."""

    async def valid_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        return AgentOutput(
            agent_name="volcanic_activity",
            evidence=[
                Evidence(
                    source="Volcano Test API",
                    claim="Eruption detected",
                    uncertainty=UncertaintyEstimate(
                        point_estimate=0.9,
                        lower_bound=0.8,
                        upper_bound=1.0,
                        source="model_uncertainty",
                    ),
                )
            ],
        )

    manifest = PluginManifest(
        name="gaiaos-volcano-plugin",
        version="1.0.0",
        domain="volcanic_activity",
        entry_point="dummy.module:run",
        gaiaos_version_range=">=0.5.0",
        eval_benchmark_question_ids=["q1"],
    )

    runner = load_and_validate_plugin(manifest, valid_runner)
    assert callable(runner)

    inp = AgentInput(investigation_id=uuid.uuid4(), query="Check volcanoes")
    res = await runner(inp)
    assert res.agent_name == "volcanic_activity"
    assert len(res.evidence) == 1


def test_duplicate_domain_protection() -> None:
    """Verifies DuplicateDomainError when plugin domain collides with agent domain."""
    registry = AgentRegistry()

    async def dummy_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name="seismic", evidence=[])

    registry.register("seismic", dummy_runner)

    manifest_colliding_first_party = PluginManifest(
        name="rogue-plugin",
        version="1.0.0",
        domain="seismic",
        entry_point="dummy:run",
    )

    with pytest.raises(DuplicateDomainError) as exc_info:
        registry.register_plugin(manifest_colliding_first_party, dummy_runner)
    assert "collides with a core first-party agent domain" in str(exc_info.value)

    manifest_valid_plugin = PluginManifest(
        name="volcano-plugin",
        version="1.0.0",
        domain="volcanic_activity",
        entry_point="dummy:run",
    )
    registry.register_plugin(manifest_valid_plugin, dummy_runner)

    manifest_colliding_plugin = PluginManifest(
        name="another-volcano-plugin",
        version="1.0.0",
        domain="volcanic_activity",
        entry_point="dummy:run",
    )
    with pytest.raises(DuplicateDomainError) as exc_info2:
        registry.register_plugin(manifest_colliding_plugin, dummy_runner)
    assert "collides with already-registered plugin" in str(exc_info2.value)


def test_registry_lookup_isolation() -> None:
    """Verifies AgentRegistry maintains separation while unified get() and list_domains() work."""
    registry = AgentRegistry()

    async def fp_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name="ocean", evidence=[])

    async def plug_runner(agent_input: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name="volcano", evidence=[])

    registry.register("ocean", fp_runner)

    manifest = PluginManifest(
        name="volcano-plugin",
        version="1.0.0",
        domain="volcano",
        entry_point="dummy:run",
    )
    registry.register_plugin(manifest, plug_runner)

    assert registry.get("ocean") == fp_runner
    assert registry.get("volcano") == plug_runner
    assert "ocean" in registry.list_domains()
    assert "volcano" in registry.list_domains()
    assert registry.get_plugin_manifest("volcano") == manifest
    assert registry.get_plugin_manifest("ocean") is None
