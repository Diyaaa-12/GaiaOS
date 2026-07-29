"""CI Regression Gate for Evaluation Benchmark Suite.

Executes thin regression checking against baseline benchmark suite runs,
syncs domain benchmark questions non-destructively, and provides a CLI entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import db.session as db_session
from config.settings import get_settings
from db.models.eval_benchmark import EvalBenchmarkQuestion
from db.session import dispose_engine, init_engine
from eval.harness.runner import (
    BenchmarkSuiteResult,
    fetch_latest_baseline_suite_result,
    run_benchmark_suite,
)
from logging_config import get_logger

_log = get_logger(__name__)

# GaiaOS project-specific UUID namespace for stable deterministic benchmark question IDs
GAIAOS_BENCHMARK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "gaiaos.eval.benchmarks")


def get_deterministic_question_id(raw_id: str) -> uuid.UUID:
    """Return a UUID from raw_id, generating a deterministic uuid5 if not a valid UUID string."""
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        return uuid.uuid5(GAIAOS_BENCHMARK_NAMESPACE, raw_id)


async def sync_benchmark_questions(
    session: AsyncSession,
    overwrite: bool = False,
) -> int:
    """Sync questions from eval/benchmarks/questions.json into the database.

    By default (overwrite=False), existing questions are left untouched (non-destructive sync).
    If overwrite=True, existing fields are updated with JSON values.

    Returns the count of new or updated questions processed.
    """
    questions_file = Path(__file__).parent.parent / "benchmarks" / "questions.json"
    if not questions_file.exists():
        _log.warning("eval.ci_gate.questions_file_missing", path=str(questions_file))
        return 0

    with open(questions_file, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)

    synced_count = 0
    for item in data:
        raw_id = item.get("id", str(uuid.uuid4()))
        q_uuid = get_deterministic_question_id(raw_id)
        question_text = item.get("question_text", "")
        expected_domains = item.get("expected_domains", [])
        expected_complexity = item.get("expected_complexity", "trivial")
        reference_answer = item.get("reference_answer", "")
        reference_evidence = item.get("reference_evidence", {})

        stmt = select(EvalBenchmarkQuestion).where(EvalBenchmarkQuestion.id == q_uuid)
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            if overwrite:
                existing.question_text = question_text
                existing.expected_domains = expected_domains
                existing.expected_complexity = expected_complexity
                existing.reference_answer = reference_answer
                existing.reference_evidence = reference_evidence
                synced_count += 1
        else:
            new_q = EvalBenchmarkQuestion(
                id=q_uuid,
                question_text=question_text,
                expected_domains=expected_domains,
                expected_complexity=expected_complexity,
                reference_answer=reference_answer,
                reference_evidence=reference_evidence,
            )
            session.add(new_q)
            synced_count += 1

    await session.commit()
    _log.info("eval.ci_gate.questions_synced", count=synced_count, overwrite=overwrite)
    return synced_count


class QuestionDelta(BaseModel):
    """Score comparison delta for an individual benchmark question."""

    question_id: uuid.UUID
    baseline_score: float | None = None
    current_score: float | None = None
    delta: float | None = None
    regressed: bool = False


class RegressionReport(BaseModel):
    """Detailed evaluation suite regression report.

    Regression Policy:
    A suite run is flagged as regressed if EITHER:
    1. Overall mean score (common questions) drops by > threshold (overall_regressed = True), OR
    2. Any individual common question score drops by > threshold (per-question delta > threshold).
    """

    regressed: bool
    threshold: float
    average_baseline_score: float | None = None
    average_current_score: float | None = None
    overall_delta: float | None = None
    overall_regressed: bool = False
    added_questions_count: int = 0
    removed_questions_count: int = 0
    per_question_deltas: list[QuestionDelta] = Field(default_factory=list)
    summary: str


def check_for_regression(
    current_run: BenchmarkSuiteResult,
    baseline: BenchmarkSuiteResult | None,
    threshold: float = 0.05,
) -> RegressionReport:
    """Check for evaluation regression between current_run and baseline.

    Gracefully handles added and removed benchmark questions by computing deltas
    over the common question set and tracking set differences explicitly.
    """
    if baseline is None or not baseline.results:
        return RegressionReport(
            regressed=False,
            threshold=threshold,
            summary=(
                "No prior baseline run available for comparison. "
                "Regression check passed trivially (first run)."
            ),
        )

    current_map = {r.question_id: r.score for r in current_run.results}
    baseline_map = {r.question_id: r.score for r in baseline.results}

    current_ids = set(current_map.keys())
    baseline_ids = set(baseline_map.keys())

    common_ids = current_ids & baseline_ids
    added_ids = current_ids - baseline_ids
    removed_ids = baseline_ids - current_ids

    # Compute baseline and current average scores over common scored questions
    common_baseline_scores = [
        cast(float, baseline_map[q_id]) for q_id in common_ids if baseline_map[q_id] is not None
    ]

    common_current_scores = [
        cast(float, current_map[q_id]) for q_id in common_ids if current_map[q_id] is not None
    ]

    avg_baseline = (
        sum(common_baseline_scores) / len(common_baseline_scores)
        if common_baseline_scores
        else None
    )
    avg_current = (
        sum(common_current_scores) / len(common_current_scores) if common_current_scores else None
    )

    overall_delta: float | None = None
    overall_regressed = False
    if avg_baseline is not None and avg_current is not None:
        overall_delta = avg_baseline - avg_current
        if overall_delta > threshold:
            overall_regressed = True

    # Compute per-question deltas for common questions
    per_question_deltas: list[QuestionDelta] = []
    regressed_questions_count = 0

    for q_id in sorted(common_ids, key=lambda u: str(u)):
        curr_score = current_map[q_id]
        base_score = baseline_map[q_id]

        q_delta: float | None = None
        q_regressed = False

        if base_score is not None and curr_score is not None:
            q_delta = base_score - curr_score
            if q_delta > threshold:
                q_regressed = True
                regressed_questions_count += 1

        per_question_deltas.append(
            QuestionDelta(
                question_id=q_id,
                baseline_score=base_score,
                current_score=curr_score,
                delta=q_delta,
                regressed=q_regressed,
            )
        )

    regressed = overall_regressed or (regressed_questions_count > 0)

    base_str = f"{avg_baseline:.4f}" if avg_baseline is not None else "N/A"
    curr_str = f"{avg_current:.4f}" if avg_current is not None else "N/A"

    summary_lines = [
        f"Regression Gate Result: {'FAILED (Regressed)' if regressed else 'PASSED'}",
        f"Threshold: {threshold:.2f}",
        f"Common Questions Score - Baseline: {base_str}, Current: {curr_str}",
    ]
    if overall_delta is not None:
        summary_lines.append(f"Overall Delta (Baseline - Current): {overall_delta:+.4f}")
    count_str = f"{regressed_questions_count}/{len(per_question_deltas)}"
    summary_lines.append(f"Regressed Common Questions: {count_str}")
    if added_ids:
        summary_lines.append(f"Added Questions (Not in baseline): {len(added_ids)}")
    if removed_ids:
        summary_lines.append(f"Removed Questions (Missing in current): {len(removed_ids)}")

    summary_text = "\n".join(summary_lines)

    return RegressionReport(
        regressed=regressed,
        threshold=threshold,
        average_baseline_score=avg_baseline,
        average_current_score=avg_current,
        overall_delta=overall_delta,
        overall_regressed=overall_regressed,
        added_questions_count=len(added_ids),
        removed_questions_count=len(removed_ids),
        per_question_deltas=per_question_deltas,
        summary=summary_text,
    )


async def run_ci_gate(
    orchestrator_version: str | None = None,
    threshold: float = 0.05,
    session: AsyncSession | None = None,
    overwrite_questions: bool = False,
) -> RegressionReport:
    """Run the CI regression gate pipeline.

    1. Syncs benchmark questions from JSON.
    2. Fetches prior baseline run using runner repository layer.
    3. Executes benchmark suite for current version.
    4. Evaluates regression policy via check_for_regression.
    """
    version = orchestrator_version or get_settings().orchestrator_version

    async def _execute(sess: AsyncSession) -> RegressionReport:
        # Step 1: Sync questions from questions.json (non-destructive by default)
        await sync_benchmark_questions(sess, overwrite=overwrite_questions)

        # Step 2: Fetch baseline using runner layer BEFORE running current suite
        baseline = await fetch_latest_baseline_suite_result(sess, current_version=version)

        # Step 3: Run benchmark suite for current version
        current_run = await run_benchmark_suite(version, session=sess)

        # Step 4: Check for regression
        report = check_for_regression(current_run, baseline, threshold=threshold)
        return report

    if session is None:
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")
        async with db_session.AsyncSessionLocal() as sess:
            return await _execute(sess)
    else:
        return await _execute(session)


def main() -> None:
    """CLI entrypoint for running the CI evaluation regression gate."""
    parser = argparse.ArgumentParser(description="GaiaOS CI Evaluation Regression Gate")
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Orchestrator version identifier (defaults to ORCHESTRATOR_VERSION env var).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Regression threshold float (default 0.05).",
    )
    parser.add_argument(
        "--overwrite-questions",
        action="store_true",
        help="Force overwrite existing DB question fields with questions.json content.",
    )

    args = parser.parse_args()

    import asyncio

    async def _run() -> None:
        try:
            init_engine()
            report = await run_ci_gate(
                orchestrator_version=args.version,
                threshold=args.threshold,
                overwrite_questions=args.overwrite_questions,
            )
            print("=" * 60)
            print(report.summary)
            print("=" * 60)

            if report.regressed:
                _log.error("eval.ci_gate.failed_regression_detected", threshold=report.threshold)
                sys.exit(1)
            else:
                _log.info("eval.ci_gate.passed")
                sys.exit(0)
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        _log.error("eval.ci_gate.execution_error", error=str(exc))
        print(f"CI Gate execution error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
