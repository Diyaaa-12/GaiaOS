"""In-memory CollaborationBus for Phase 5 Milestone 4 Multi-Agent Collaboration Protocol.

ADR-502: In-Memory, Non-Persistent Collaboration Bus (Not Redis-Backed).
Scoped to a single fan-out call per investigation. Deliberately passive:
stores and returns CollaborationMessage objects, with zero orchestration or routing logic.
"""

from __future__ import annotations

import asyncio

from logging_config import get_logger
from orchestrator.schemas.collaboration import CollaborationMessage

_log = get_logger(__name__)


class CollaborationBus:
    """In-memory, passive message transport for per-investigation agent collaboration.

    Strictly passive:
    - Stores broadcast messages
    - Returns peer messages matching criteria
    - Performs NO routing, execution, agent calls, or orchestration

    asyncio.Lock protects concurrent access to the internal message list only.
    It does not provide message ordering guarantees or synchronization between agent execution.
    """

    def __init__(self, investigation_id: str, max_rounds: int = 2) -> None:
        self.investigation_id: str = str(investigation_id)
        self.max_rounds: int = max_rounds
        self._messages: list[CollaborationMessage] = []
        self._lock: asyncio.Lock = asyncio.Lock()

    async def broadcast(self, message: CollaborationMessage) -> None:
        """Broadcast a collaboration message to the in-memory bus.

        Thread/task safe via asyncio.Lock.
        """
        async with self._lock:
            self._messages.append(message)

        _log.info(
            "collaboration.bus.broadcast",
            investigation_id=self.investigation_id,
            from_agent=message.from_agent,
            finding_summary=message.finding_summary,
            round=message.round,
        )

    async def peer_findings(
        self, requesting_agent: str, since_round: int = 0
    ) -> list[CollaborationMessage]:
        """Retrieve peer collaboration messages sent by other agents since a given round.

        Args:
            requesting_agent: Agent name requesting peer findings (excluded from results).
            since_round: Minimum round index to include (inclusive).

        Returns:
            List of matching CollaborationMessage objects from peer agents.
        """
        async with self._lock:
            findings = [
                msg
                for msg in self._messages
                if msg.from_agent != requesting_agent and msg.round >= since_round
            ]

        _log.debug(
            "collaboration.bus.peer_findings",
            investigation_id=self.investigation_id,
            requesting_agent=requesting_agent,
            since_round=since_round,
            count=len(findings),
        )
        return findings

    async def snapshot(self) -> list[CollaborationMessage]:
        """Return a snapshot copy of all broadcast messages recorded on this bus."""
        async with self._lock:
            return list(self._messages)
