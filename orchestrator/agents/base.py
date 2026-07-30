"""Base domain agent class and contract for Phase 5 Collaboration Protocol."""

from __future__ import annotations

from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput
from orchestrator.schemas.collaboration import CollaborationMessage


class BaseDomainAgent:
    """Base class for domain agents participating in fan-out execution.

    Provides a default no-op implementation of `on_peer_finding`.
    """

    def on_peer_finding(self, message: CollaborationMessage) -> AgentInput | None:
        """Hook invoked when a peer collaboration message is received.

        Default implementation is a no-op returning None. Domain agents override
        this method when they support query parameter refinement based on peer findings.

        Args:
            message: Immutable CollaborationMessage from a peer agent.

        Returns:
            Refined AgentInput if the agent wishes to re-run, or None to ignore.
        """
        return None

    async def run(
        self, agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        """Execute domain agent logic. Subclasses must implement."""
        raise NotImplementedError
