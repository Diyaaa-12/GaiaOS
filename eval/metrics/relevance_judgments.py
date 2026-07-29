"""Relevance judgments registry for retrieval precision evaluation.

``RELEVANCE_JUDGMENTS`` maps a benchmark question UUID to the set of
``Evidence.chunk_id`` strings that are considered relevant to that question.
It starts empty and must be populated from verified live-database chunk IDs
before retrieval precision can be computed for any question.

Curation process: docs/phase5/eval_metrics.md#curation-process
Namespace note: ``_BENCHMARK_NAMESPACE`` replicates the constant from
``eval/harness/ci_gate.py`` to avoid a downward cross-layer import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

_BENCHMARK_NAMESPACE: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "gaiaos.eval.benchmarks")


def _question_id(raw_id: str) -> uuid.UUID:
    """Return the deterministic benchmark question UUID for ``raw_id``."""
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        return uuid.uuid5(_BENCHMARK_NAMESPACE, raw_id)


@dataclass(frozen=True)
class RelevanceJudgment:
    """Hand-curated relevance judgment for one benchmark question.

    Attributes:
        question_id: Deterministic UUID matching ``EvalBenchmarkQuestion.id``.
        relevant_chunk_ids: Frozen set of ``Evidence.chunk_id`` strings judged
            relevant. Must be verified against the live ``literature_chunks``
            table before committing.
    """

    question_id: uuid.UUID
    relevant_chunk_ids: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Registry — empty until real chunk IDs are verified from the live database.
# Follow docs/phase5/eval_metrics.md#curation-process to add entries.
# ---------------------------------------------------------------------------
RELEVANCE_JUDGMENTS: dict[uuid.UUID, RelevanceJudgment] = {}
