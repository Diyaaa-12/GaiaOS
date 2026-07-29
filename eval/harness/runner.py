"""Evaluation suite runner.

Fetches benchmark questions, runs each through the orchestrator/agent stubs,
evaluates outcomes via the scoring pipeline, and logs historical runs.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import db.session as db_session
from db.models.eval_benchmark import EvalBenchmarkQuestion, EvalBenchmarkRun
from eval.harness.scorer import score_result, score_suite
from logging_config import get_logger

_log = get_logger(__name__)

type CollectedRow = tuple[EvalBenchmarkQuestion, float | None, dict[str, Any]]


class BenchmarkQuestionResult(BaseModel):
    """Execution output and score for an individual benchmark question."""

    question_id: uuid.UUID
    orchestrator_version: str
    score: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class BenchmarkSuiteResult(BaseModel):
    """Summary of the execution of the entire benchmark suite."""

    orchestrator_version: str
    results: list[BenchmarkQuestionResult] = Field(default_factory=list)
    total_questions: int = 0
    successful_runs: int = 0


async def run_stub_benchmark(question: EvalBenchmarkQuestion) -> dict[str, Any]:
    """Execute a benchmark question against a stub benchmark runner.

    In Milestone 1, this runner is a foundation and does not execute real
    LLM/orchestrator logic. Returns a stub dictionary.
    """
    _log.info("eval.runner.executing_stub", question_id=str(question.id))
    return {
        "status": "not_yet_implemented",
        "answer": "Stub answer generated. Orchestrator and agents not implemented.",
        "evidence": [],
    }


async def run_benchmark_suite(
    orchestrator_version: str,
    session: AsyncSession | None = None,
) -> BenchmarkSuiteResult:
    """Execute the curated benchmark suite against the current version.

    Reads questions from the database, runs them, scores results, and records
    outcomes in `eval_benchmark_runs`. Returns a summary suite result.
    """
    if session is None:
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")
        async with db_session.AsyncSessionLocal() as sess:
            return await _run_suite(orchestrator_version, sess)
    else:
        return await _run_suite(orchestrator_version, session)


async def _run_suite(
    orchestrator_version: str,
    session: AsyncSession,
) -> BenchmarkSuiteResult:
    stmt = select(EvalBenchmarkQuestion)
    result = await session.execute(stmt)
    questions = result.scalars().all()

    _log.info(
        "eval.runner.suite_started",
        version=orchestrator_version,
        total_questions=len(questions),
    )

    # ------------------------------------------------------------------
    # Phase 1 — Execute and per-question score.
    # DB records are not created yet; we collect everything in memory so
    # that suite-level metrics can be computed before any row is written.
    # ------------------------------------------------------------------
    collected: list[CollectedRow] = []
    successful_runs = 0

    for q in questions:
        try:
            stub_result = await run_stub_benchmark(q)
            score, metrics = await score_result(q, stub_result)
            successful_runs += 1
            _log.info(
                "eval.runner.question_run.success",
                question_id=str(q.id),
                score=score,
            )
        except Exception as e:
            score = None
            metrics = {
                "error": str(e),
                "status": "failed",
                "reason": "Exception raised during run/score execution step.",
            }
            _log.error(
                "eval.runner.question_run.failed",
                question_id=str(q.id),
                error=str(e),
            )

        collected.append((q, score, metrics))

    # ------------------------------------------------------------------
    # Phase 2 — Suite-level metrics.
    # score_suite lives in scorer.py to maintain scoring responsibility
    # there.  runner.py only calls it and passes the results through.
    # ------------------------------------------------------------------
    per_question_metrics = [metrics for _, _, metrics in collected]
    suite_metrics = score_suite(per_question_metrics)

    _log.info(
        "eval.runner.suite_metrics",
        ece=suite_metrics.get("ece"),
        calibration_status=suite_metrics.get("calibration_status"),
        mean_retrieval_precision=suite_metrics.get("mean_retrieval_precision"),
        precision_status=suite_metrics.get("precision_status"),
    )

    # ------------------------------------------------------------------
    # Phase 3 — Persist.
    # Suite metrics are merged under the "suite" key in each row's metrics
    # JSONB.  No schema change: the existing metrics column absorbs them.
    # In-memory BenchmarkQuestionResult objects carry identical full metrics
    # for consistency between callers and DB reads.
    # ------------------------------------------------------------------
    question_results: list[BenchmarkQuestionResult] = []

    for q, score, metrics in collected:
        full_metrics = {**metrics, "suite": suite_metrics}

        run_record = EvalBenchmarkRun(
            benchmark_question_id=q.id,
            orchestrator_version=orchestrator_version,
            score=score,
            metrics=full_metrics,
        )
        session.add(run_record)

        question_results.append(
            BenchmarkQuestionResult(
                question_id=q.id,
                orchestrator_version=orchestrator_version,
                score=score,
                metrics=full_metrics,
            )
        )

    # Only commit if there are records to write.
    if questions:
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            _log.error("eval.runner.commit_failed", error=str(exc))
            raise exc

    suite_result = BenchmarkSuiteResult(
        orchestrator_version=orchestrator_version,
        results=question_results,
        total_questions=len(questions),
        successful_runs=successful_runs,
    )

    _log.info(
        "eval.runner.suite_completed",
        version=orchestrator_version,
        total_questions=len(questions),
        successful_runs=successful_runs,
    )

    return suite_result


async def fetch_latest_baseline_suite_result(
    session: AsyncSession,
    current_version: str | None = None,
) -> BenchmarkSuiteResult | None:
    """Fetch the most recent prior benchmark suite run from DB for baseline comparison.

    If current_version is provided, attempts to find the latest run with a version
    distinct from current_version. Falls back to the latest recorded run if no
    distinct version exists.
    """
    stmt_versions = select(EvalBenchmarkRun.orchestrator_version).order_by(
        EvalBenchmarkRun.run_at.desc()
    )
    if current_version:
        stmt_versions = stmt_versions.where(
            EvalBenchmarkRun.orchestrator_version != current_version
        )

    versions_res = (await session.execute(stmt_versions)).scalars().all()

    target_version: str | None = None
    if versions_res:
        target_version = versions_res[0]
    else:
        stmt_all = select(EvalBenchmarkRun).order_by(EvalBenchmarkRun.run_at.desc())
        all_runs = (await session.execute(stmt_all)).scalars().all()
        if not all_runs:
            return None
        target_version = all_runs[0].orchestrator_version

    stmt_runs = select(EvalBenchmarkRun).where(
        EvalBenchmarkRun.orchestrator_version == target_version
    )
    runs = (await session.execute(stmt_runs)).scalars().all()
    if not runs:
        return None

    results = [
        BenchmarkQuestionResult(
            question_id=r.benchmark_question_id,
            orchestrator_version=r.orchestrator_version,
            score=float(r.score) if r.score is not None else None,
            metrics=r.metrics or {},
        )
        for r in runs
    ]

    return BenchmarkSuiteResult(
        orchestrator_version=target_version,
        results=results,
        total_questions=len(results),
        successful_runs=len([r for r in results if r.score is not None]),
    )
