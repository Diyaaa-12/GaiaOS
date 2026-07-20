"""Agent Registry for mapping domains dynamically to agent runner callables."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from orchestrator.schemas.agent_io import AgentInput, AgentOutput

AgentRunner = Callable[[AgentInput], Awaitable[AgentOutput]]


class AgentRegistry:
    """Registry holding all active domain agents to enforce the Open/Closed Principle."""

    def __init__(self) -> None:
        self._registry: dict[str, AgentRunner] = {}

    def register(self, name: str, runner: AgentRunner) -> None:
        """Register a domain agent runner."""
        self._registry[name] = runner

    def get(self, name: str) -> AgentRunner:
        """Get the runner for a specific domain. Raises ValueError if not found."""
        if name not in self._registry:
            raise ValueError(f"Agent '{name}' is not registered.")
        return self._registry[name]

    def list_domains(self) -> list[str]:
        """List all currently registered domain names."""
        return list(self._registry.keys())


# Singleton instance of the registry
agent_registry = AgentRegistry()


def register_agents() -> None:
    """Import and register active agents lazily to avoid circular dependencies."""
    from orchestrator.agents.air_quality.agent import run as run_aq

    agent_registry.register("air_quality", run_aq)

    from orchestrator.agents.seismic.agent import run as run_seismic

    agent_registry.register("seismic", run_seismic)

    from orchestrator.agents.ocean.agent import run as run_ocean

    agent_registry.register("ocean", run_ocean)

    from orchestrator.agents.atmosphere.agent import run as run_atmosphere

    agent_registry.register("atmosphere", run_atmosphere)

    from orchestrator.agents.wildfire.agent import run as run_wildfire

    agent_registry.register("wildfire", run_wildfire)


# Populating registry
register_agents()
