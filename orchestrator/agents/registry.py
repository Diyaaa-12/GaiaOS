"""Agent Registry for mapping domains dynamically to agent runner callables."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from orchestrator.schemas.agent_io import AgentOutput

if TYPE_CHECKING:
    from orchestrator.schemas.plugin_manifest import PluginManifest

AgentRunner = Callable[..., Awaitable[AgentOutput]]


class RegisteredPlugin:
    """Internal container for a registered plugin agent."""

    def __init__(self, manifest: PluginManifest, runner: AgentRunner):
        self.manifest = manifest
        self.runner = runner
        self.status = "active"


class AgentRegistry:
    """Registry holding all active domain agents to enforce the Open/Closed Principle."""

    def __init__(self) -> None:
        self._first_party_registry: dict[str, AgentRunner] = {}
        self._plugin_registry: dict[str, RegisteredPlugin] = {}

    def register(self, name: str, runner: AgentRunner) -> None:
        """Register a first-party domain agent runner."""
        self._first_party_registry[name] = runner

    def register_plugin(self, manifest: PluginManifest, runner: AgentRunner) -> None:
        """Register a dynamic agent plugin.

        Raises DuplicateDomainError if domain collides with a first-party domain
        or an existing plugin domain.
        """
        # Import exception locally to avoid circular imports
        from orchestrator.agents.plugin_loader import DuplicateDomainError

        domain = manifest.domain
        if domain in self._first_party_registry:
            raise DuplicateDomainError(
                f"Plugin '{manifest.name}' attempted to register domain '{domain}', "
                "which collides with a core first-party agent domain."
            )
        if domain in self._plugin_registry:
            existing = self._plugin_registry[domain].manifest.name
            raise DuplicateDomainError(
                f"Plugin '{manifest.name}' attempted to register domain '{domain}', "
                f"which collides with already-registered plugin '{existing}'."
            )

        self._plugin_registry[domain] = RegisteredPlugin(manifest, runner)

    def get(self, name: str) -> AgentRunner:
        """Get the runner for a specific domain. Raises ValueError if not found."""
        if name in self._first_party_registry:
            return self._first_party_registry[name]
        if name in self._plugin_registry:
            return self._plugin_registry[name].runner
        raise ValueError(f"Agent '{name}' is not registered.")

    def list_domains(self) -> list[str]:
        """List all currently registered domain names."""
        first_party = list(self._first_party_registry.keys())
        plugins = list(self._plugin_registry.keys())
        return first_party + plugins

    def get_plugin_manifest(self, domain: str) -> PluginManifest | None:
        """Get the PluginManifest for a plugin domain, or None if first-party."""
        if domain in self._plugin_registry:
            return self._plugin_registry[domain].manifest
        return None


# Singleton instance of the registry
agent_registry = AgentRegistry()


def register_agents() -> None:
    """Import and register active agents lazily to avoid circular dependencies.

    Idempotent: repeated calls skip domains that are already registered,
    so calling this function multiple times is safe.
    """

    def _register(name: str, runner: AgentRunner) -> None:
        if name not in agent_registry._first_party_registry:
            agent_registry.register(name, runner)

    from orchestrator.agents.air_quality.agent import run as run_aq

    _register("air_quality", run_aq)

    from orchestrator.agents.seismic.agent import run as run_seismic

    _register("seismic", run_seismic)

    from orchestrator.agents.ocean.agent import run as run_ocean

    _register("ocean", run_ocean)

    from orchestrator.agents.atmosphere.agent import run as run_atmosphere

    _register("atmosphere", run_atmosphere)

    from orchestrator.agents.wildfire.agent import run as run_wildfire

    _register("wildfire", run_wildfire)

    from orchestrator.agents.literature_rag.agent import run as run_literature

    _register("literature", run_literature)

    from orchestrator.agents.causal_chain.agent import run as run_causal_chain

    _register("causal_chain", run_causal_chain)


# Populating registry
register_agents()
