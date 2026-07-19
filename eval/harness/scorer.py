"""Evaluation scoring pipeline logic.

Evaluates response outputs against ground-truth reference values.
"""

from __future__ import annotations

from typing import Any

from db.models.eval_benchmark import EvalBenchmarkQuestion


async def score_result(
    question: EvalBenchmarkQuestion,
    run_result: dict[str, Any],
) -> tuple[float | None, dict[str, Any]]:
    """Score the result of a benchmark run against reference targets.

    In Milestone 1, this functions as a stub scoring pipeline. It returns None for
    the score and logs placeholder metrics.
    """
    metrics = {
        "status": "stub_scored",
        "reason": "Real scoring pipeline not implemented. Gated in Milestone 1.",
        "input_question": question.question_text,
        "run_result": run_result,
    }
    return None, metrics
