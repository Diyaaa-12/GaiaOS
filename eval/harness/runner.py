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

from db.models.eval_benchmark import EvalBenchmarkQuestion, EvalBenchmarkRun
from db.session import AsyncSessionLocal
from eval.harness.scorer import score_result
from logging_config import get_logger

_log = get_logger(__name__)


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
        if AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")
        async with AsyncSessionLocal() as sess:
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

    question_results: list[BenchmarkQuestionResult] = []
    successful_runs = 0

    _log.info(
        "eval.runner.suite_started",
        version=orchestrator_version,
        total_questions=len(questions),
    )

    for q in questions:
        try:
            # 1. Stub execution
            stub_result = await run_stub_benchmark(q)
            # 2. Stub scoring
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

        # 3. Persist run results
        run_record = EvalBenchmarkRun(
            benchmark_question_id=q.id,
            orchestrator_version=orchestrator_version,
            score=score,
            metrics=metrics,
        )
        session.add(run_record)

        question_results.append(
            BenchmarkQuestionResult(
                question_id=q.id,
                orchestrator_version=orchestrator_version,
                score=score,
                metrics=metrics,
            )
        )

    # Only commit if we have runs to persist
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
