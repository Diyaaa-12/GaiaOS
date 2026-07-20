"""Specialized database module for historical hazard causal-chain recursive traversal."""

from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger
from orchestrator.schemas.agent_io import Evidence

_log = get_logger(__name__)


def calculate_chain_confidence(edge_confidences: list[float]) -> float:
    """Calculate the overall confidence of a causal chain.

    Defaults to the minimum edge confidence along the chain, but can evolve
    into a richer scoring model without changing calling conventions.
    """
    if not edge_confidences:
        return 1.0
    return min(edge_confidences)


class CausalChainRepository:
    """Isolates specialized database logic for causal chain WITH RECURSIVE queries."""

    @staticmethod
    async def find_causal_chain(
        session: AsyncSession,
        event_type: str,
        region: str,
        max_depth: int = 4,
        statement_timeout_ms: int = 2000,
    ) -> list[Evidence]:
        """Perform recursive WITH RECURSIVE CTE query to traverse hazard relationships.

        Bounded by max_depth and protected by a session-level statement timeout.
        """
        start_time = time.perf_counter()

        try:
            # 1. Protect query with a transaction-local statement timeout
            timeout_val = int(statement_timeout_ms)
            await session.execute(text(f"SET LOCAL statement_timeout = {timeout_val};"))

            # 2. Bounded recursive CTE query with cycle protection
            stmt = text("""
                WITH RECURSIVE causal_path AS (
                    -- Anchor member: Select start event
                    SELECT
                        he.id AS event_id,
                        he.event_type,
                        he.region,
                        he.details,
                        ARRAY[he.id] AS path_ids,
                        ARRAY[he.event_type] AS path_types,
                        1 AS depth,
                        ARRAY[]::numeric[] AS edge_confidences
                    FROM hazard_events he
                    WHERE he.event_type = :event_type AND he.region = :region

                    UNION ALL

                    -- Recursive member: Traverse relations
                    SELECT
                        child.id AS event_id,
                        child.event_type,
                        child.region,
                        child.details,
                        cp.path_ids || child.id AS path_ids,
                        cp.path_types || child.event_type AS path_types,
                        cp.depth + 1 AS depth,
                        cp.edge_confidences || hr.confidence AS edge_confidences
                    FROM causal_path cp
                    JOIN hazard_relationships hr ON cp.event_id = hr.parent_id
                    JOIN hazard_events child ON hr.child_id = child.id
                    WHERE cp.depth < :max_depth
                      AND NOT (child.id = ANY(cp.path_ids)) -- Cycle prevention guard
                )
                SELECT event_id, event_type, region, details,
                       path_ids, path_types, depth, edge_confidences
                FROM causal_path
                ORDER BY depth ASC;
            """)

            result = await session.execute(
                stmt,
                {"event_type": event_type, "region": region, "max_depth": max_depth},
            )
            rows = result.fetchall()

        except Exception as e:
            query_duration_ms = int((time.perf_counter() - start_time) * 1000)
            err_msg = str(e).lower()
            if "57014" in err_msg or "query canceled" in err_msg or "statement timeout" in err_msg:
                _log.error(
                    "db.causal_chain.timeout",
                    event_type=event_type,
                    region=region,
                    max_depth=max_depth,
                    duration_ms=query_duration_ms,
                    error=str(e),
                )
                raise TimeoutError("causal chain query exceeded time budget") from e
            raise e

        # 3. Process paths and map to Evidence models
        evidence_list = []
        for row in rows:
            # Map row elements (event_id, event_type, region, details,
            # path_ids, path_types, depth, edge_confidences)
            event_id = row[0]
            row_region = row[2]
            details = row[3]
            path_ids = row[4]
            path_types = row[5]
            depth = row[6]
            edge_confidences = [float(c) for c in row[7]] if row[7] is not None else []

            # Minimum 2 nodes needed to form a causal relationship path
            if depth < 2:
                continue

            # Compute path confidence using helper function
            confidence = calculate_chain_confidence(edge_confidences)

            chain_str = " -> ".join(path_types)
            claim = (
                f"Historical causal chain in {row_region}: {chain_str}. "
                f"Initial trigger details: {details or 'N/A'}"
            )

            # Preserve traversed path (event IDs and chain types) in extra_metadata
            extra_metadata = {
                "visited_event_ids": [str(eid) for eid in path_ids],
                "event_chain_path": path_types,
                "depth": depth,
                "edge_confidences": edge_confidences,
            }

            evidence_list.append(
                Evidence(
                    source="Causal Chain Traversal",
                    claim=claim,
                    confidence=confidence,
                    document_id="causal_chain",
                    chunk_id=str(event_id),
                    title=f"Causal Path: {chain_str}",
                    source_url="http://db.planetaryrisk.org/causal_chains",
                    extra_metadata=extra_metadata,
                )
            )

        query_duration_ms = int((time.perf_counter() - start_time) * 1000)
        _log.info(
            "db.causal_chain.completed",
            event_type=event_type,
            region=region,
            max_depth=max_depth,
            chain_count=len(evidence_list),
            query_duration_ms=query_duration_ms,
        )

        return evidence_list
