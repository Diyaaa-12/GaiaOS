"""Evaluation scoring pipeline.

``score_result`` — per-question scoring; calls retrieval precision where a
judgment exists.
``score_suite``  — suite-level scoring; guards the empty-predictions case and
calls ``calculate_calibration`` only when pairs are available.

Separation of concerns: this module invokes eval.metrics functions.
It does not orchestrate execution (runner.py) or implement statistics
(eval/metrics/).
"""

from __future__ import annotations

from typing import Any

from db.models.eval_benchmark import EvalBenchmarkQuestion
from eval.metrics.calibration import calculate_calibration
from eval.metrics.relevance_judgments import RELEVANCE_JUDGMENTS
from eval.metrics.retrieval_precision import calculate_retrieval_precision
from logging_config import get_logger

_log = get_logger(__name__)

_STATUS_SCORED = "scored"
_PRECISION_COMPUTED = "computed"
_PRECISION_NO_EVIDENCE = "no_evidence_retrieved"
_PRECISION_NO_JUDGMENT = "no_relevance_judgment"
_CALIBRATION_COMPUTED = "computed"
_CALIBRATION_INSUFFICIENT = "insufficient_data"
_PRECISION_INSUFFICIENT = "insufficient_data"


async def score_result(
    question: EvalBenchmarkQuestion,
    run_result: dict[str, Any],
) -> tuple[float | None, dict[str, Any]]:
    """Score one benchmark question result.

    Extracts signals from ``run_result`` and computes retrieval precision where
    a relevance judgment exists. The per-question ``score`` float remains
    ``None`` until a correctness methodology is defined in a later milestone.

    Args:
        question: The benchmark question being evaluated.
        run_result: Runner output dict. Recognised keys (all optional):
            ``"confidence"`` (float), ``"is_correct"`` (bool),
            ``"evidence"`` (list[dict] with optional ``"chunk_id"`` strings).

    Returns:
        ``(score, metrics)`` where ``score`` is ``None`` and ``metrics``
        contains ``status``, ``confidence``, ``is_correct``,
        ``retrieval_precision``, and ``retrieval_precision_status``.
    """
    confidence: float | None = run_result.get("confidence")
    is_correct: bool | None = run_result.get("is_correct")
    evidence_items: list[dict[str, Any]] = run_result.get("evidence") or []

    retrieved_chunk_ids: list[str] = [
        str(item["chunk_id"]) for item in evidence_items if item.get("chunk_id") is not None
    ]

    retrieval_precision: float | None = None
    precision_status: str

    if not evidence_items:
        precision_status = _PRECISION_NO_EVIDENCE
    elif question.id not in RELEVANCE_JUDGMENTS:
        precision_status = _PRECISION_NO_JUDGMENT
    elif not retrieved_chunk_ids:
        precision_status = _PRECISION_NO_EVIDENCE
    else:
        judgment = RELEVANCE_JUDGMENTS[question.id]
        retrieval_precision = calculate_retrieval_precision(
            retrieved_chunk_ids=retrieved_chunk_ids,
            relevant_chunk_ids=set(judgment.relevant_chunk_ids),
        )
        precision_status = _PRECISION_COMPUTED
        _log.info(
            "eval.scorer.retrieval_precision",
            question_id=str(question.id),
            precision=retrieval_precision,
            retrieved_count=len(retrieved_chunk_ids),
        )

    metrics: dict[str, Any] = {
        "status": _STATUS_SCORED,
        "confidence": confidence,
        "is_correct": is_correct,
        "retrieval_precision": retrieval_precision,
        "retrieval_precision_status": precision_status,
    }

    return None, metrics


def score_suite(per_question_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute suite-level metrics from all per-question scoring outputs.

    Called once per suite run by ``runner.py`` after all ``score_result``
    calls complete. Guards the empty-predictions case before calling
    ``calculate_calibration``, which requires a non-empty list.

    Args:
        per_question_metrics: ``metrics`` dicts from each ``score_result`` call.

    Returns:
        Suite-level dict stored under the ``"suite"`` key in each
        ``EvalBenchmarkRun.metrics`` JSONB column. Keys: ``ece``,
        ``ece_n_predictions``, ``calibration_status``,
        ``mean_retrieval_precision``, ``precision_n_questions``,
        ``precision_status``.
    """
    calibration_pairs: list[tuple[float, bool]] = [
        (m["confidence"], m["is_correct"])
        for m in per_question_metrics
        if m.get("confidence") is not None and m.get("is_correct") is not None
    ]

    # Guard: calculate_calibration requires a non-empty list (pure math function).
    # Responsibility for the "no data" decision lives here, not in the metric layer.
    if calibration_pairs:
        ece: float | None = calculate_calibration(calibration_pairs)
        calibration_status = _CALIBRATION_COMPUTED
        _log.info(
            "eval.scorer.suite_calibration",
            ece=ece,
            n_predictions=len(calibration_pairs),
        )
    else:
        ece = None
        calibration_status = _CALIBRATION_INSUFFICIENT

    precision_values: list[float] = [
        m["retrieval_precision"]
        for m in per_question_metrics
        if isinstance(m.get("retrieval_precision"), float)
    ]

    mean_precision = sum(precision_values) / len(precision_values) if precision_values else None
    precision_status = (
        _PRECISION_COMPUTED if mean_precision is not None else _PRECISION_INSUFFICIENT
    )

    return {
        "ece": ece,
        "ece_n_predictions": len(calibration_pairs),
        "calibration_status": calibration_status,
        "mean_retrieval_precision": mean_precision,
        "precision_n_questions": len(precision_values),
        "precision_status": precision_status,
    }
