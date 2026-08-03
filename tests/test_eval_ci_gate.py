"""Unit and integration tests for CI evaluation regression gate and benchmark sync."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.eval_benchmark import EvalBenchmarkQuestion, EvalBenchmarkRun
from eval.harness import (
    check_for_regression,
    run_ci_gate,
    sync_benchmark_questions,
)
from eval.harness.ci_gate import GAIAOS_BENCHMARK_NAMESPACE, get_deterministic_question_id
from eval.harness.runner import BenchmarkQuestionResult, BenchmarkSuiteResult


class TestCheckForRegressionUnit:
    """Unit tests for check_for_regression logic."""

    def test_first_run_no_baseline_passes_trivially(self) -> None:
        """First run without baseline returns regressed=False."""
        q_id = uuid.uuid4()
        current_run = BenchmarkSuiteResult(
            orchestrator_version="v1.0.0",
            results=[
                BenchmarkQuestionResult(
                    question_id=q_id,
                    orchestrator_version="v1.0.0",
                    score=0.8,
                )
            ],
            total_questions=1,
            successful_runs=1,
        )

        report = check_for_regression(current_run, baseline=None, threshold=0.05)

        assert report.regressed is False
        assert "first run" in report.summary.lower()
        assert report.overall_regressed is False
        assert len(report.per_question_deltas) == 0

    def test_no_regression_when_scores_equal_or_better(self) -> None:
        """Scores equal or higher than baseline pass regression check."""
        q1 = uuid.uuid4()
        q2 = uuid.uuid4()

        baseline = BenchmarkSuiteResult(
            orchestrator_version="v1.0.0",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.0", score=0.8),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.0", score=0.7),
            ],
            total_questions=2,
            successful_runs=2,
        )

        current = BenchmarkSuiteResult(
            orchestrator_version="v1.0.1",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.1", score=0.85),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.1", score=0.70),
            ],
            total_questions=2,
            successful_runs=2,
        )

        report = check_for_regression(current, baseline=baseline, threshold=0.05)

        assert report.regressed is False
        assert report.overall_regressed is False
        assert len(report.per_question_deltas) == 2

    def test_overall_score_drop_triggers_regression(self) -> None:
        """Overall mean score drop exceeding threshold sets regressed=True."""
        q1 = uuid.uuid4()
        q2 = uuid.uuid4()

        baseline = BenchmarkSuiteResult(
            orchestrator_version="v1.0.0",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.0", score=0.90),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.0", score=0.90),
            ],
            total_questions=2,
            successful_runs=2,
        )

        current = BenchmarkSuiteResult(
            orchestrator_version="v1.0.1",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.1", score=0.80),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.1", score=0.80),
            ],
            total_questions=2,
            successful_runs=2,
        )

        report = check_for_regression(current, baseline=baseline, threshold=0.05)

        assert report.regressed is True
        assert report.overall_regressed is True
        assert report.overall_delta == pytest.approx(0.10)

    def test_per_question_drop_triggers_regression(self) -> None:
        """Single question drop > threshold triggers regression even if overall drop is small."""
        q1 = uuid.uuid4()
        q2 = uuid.uuid4()

        baseline = BenchmarkSuiteResult(
            orchestrator_version="v1.0.0",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.0", score=0.80),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.0", score=0.80),
            ],
            total_questions=2,
            successful_runs=2,
        )

        current = BenchmarkSuiteResult(
            orchestrator_version="v1.0.1",
            results=[
                BenchmarkQuestionResult(question_id=q1, orchestrator_version="v1.0.1", score=0.60),
                BenchmarkQuestionResult(question_id=q2, orchestrator_version="v1.0.1", score=0.95),
            ],
            total_questions=2,
            successful_runs=2,
        )

        report = check_for_regression(current, baseline=baseline, threshold=0.05)

        assert report.regressed is True
        assert report.overall_regressed is False
        q1_delta = next(d for d in report.per_question_deltas if d.question_id == q1)
        assert q1_delta.regressed is True
        assert q1_delta.delta == pytest.approx(0.20)

    def test_handles_added_and_removed_questions_gracefully(self) -> None:
        """Added and removed questions between runs do not crash or skew common set deltas."""
        q_common = uuid.uuid4()
        q_removed = uuid.uuid4()
        q_added = uuid.uuid4()

        baseline = BenchmarkSuiteResult(
            orchestrator_version="v1.0.0",
            results=[
                BenchmarkQuestionResult(
                    question_id=q_common, orchestrator_version="v1.0.0", score=0.80
                ),
                BenchmarkQuestionResult(
                    question_id=q_removed, orchestrator_version="v1.0.0", score=0.20
                ),
            ],
            total_questions=2,
            successful_runs=2,
        )

        current = BenchmarkSuiteResult(
            orchestrator_version="v1.0.1",
            results=[
                BenchmarkQuestionResult(
                    question_id=q_common, orchestrator_version="v1.0.1", score=0.82
                ),
                BenchmarkQuestionResult(
                    question_id=q_added, orchestrator_version="v1.0.1", score=0.90
                ),
            ],
            total_questions=2,
            successful_runs=2,
        )

        report = check_for_regression(current, baseline=baseline, threshold=0.05)

        assert report.regressed is False
        assert report.added_questions_count == 1
        assert report.removed_questions_count == 1
        assert len(report.per_question_deltas) == 1
        assert report.per_question_deltas[0].question_id == q_common


@pytest.mark.asyncio
class TestCIGateIntegration:
    """Integration tests for question syncing and CI gate pipeline."""

    async def test_sync_benchmark_questions_database(self, db_session: AsyncSession) -> None:
        """sync_benchmark_questions populates 18 domain questions non-destructively."""
        await db_session.execute(delete(EvalBenchmarkRun))
        await db_session.commit()
        await db_session.execute(delete(EvalBenchmarkQuestion))
        await db_session.commit()

        synced_count = await sync_benchmark_questions(db_session, overwrite=False)
        assert synced_count == 22

        stmt = select(EvalBenchmarkQuestion)
        questions = (await db_session.execute(stmt)).scalars().all()
        assert len(questions) == 22

        # Verify project-specific namespace
        paris_id = get_deterministic_question_id("air_quality_paris_pm25")
        expected_id = uuid.uuid5(GAIAOS_BENCHMARK_NAMESPACE, "air_quality_paris_pm25")
        assert paris_id == expected_id

        # Second sync with overwrite=False should modify 0 rows
        second_sync_count = await sync_benchmark_questions(db_session, overwrite=False)
        assert second_sync_count == 0

    async def test_run_ci_gate_flow(self, db_session: AsyncSession) -> None:
        """run_ci_gate syncs questions, runs suite, and checks regression against baseline."""
        await db_session.execute(delete(EvalBenchmarkRun))
        await db_session.commit()
        await db_session.execute(delete(EvalBenchmarkQuestion))
        await db_session.commit()

        report1 = await run_ci_gate(
            orchestrator_version="v1.0.0-baseline",
            threshold=0.05,
            session=db_session,
        )

        assert report1.regressed is False
        assert "first run" in report1.summary.lower()

        db_runs = (await db_session.execute(select(EvalBenchmarkRun))).scalars().all()
        assert len(db_runs) == 22
