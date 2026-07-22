"""Integration tests for the evaluation harness runner, scorer, and persistence layers."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.eval_benchmark import EvalBenchmarkQuestion, EvalBenchmarkRun
from eval.harness.runner import run_benchmark_suite


class TestEvaluationHarness:
    """Integration tests for the evaluation harness."""

    async def test_empty_benchmark_table_runs_fine(self, db_session: AsyncSession) -> None:
        """Suite executes successfully and returns empty result if no questions exist."""
        # 1. Clean the table temporarily
        await db_session.execute(delete(EvalBenchmarkRun))
        await db_session.execute(delete(EvalBenchmarkQuestion))
        await db_session.commit()

        # 2. Run the suite
        result = await run_benchmark_suite(
            orchestrator_version="test-version-empty",
            session=db_session,
        )

        assert result.total_questions == 0
        assert result.successful_runs == 0
        assert len(result.results) == 0

        # Check DB has no new run entries
        stmt = select(EvalBenchmarkRun)
        db_runs = (await db_session.execute(stmt)).scalars().all()
        assert len(db_runs) == 0

    async def test_stub_benchmark_execution_and_persistence(self, db_session: AsyncSession) -> None:
        """Suite executes correctly against questions and persists scores to database."""
        # 1. Clean database
        await db_session.execute(delete(EvalBenchmarkRun))
        await db_session.execute(delete(EvalBenchmarkQuestion))
        await db_session.commit()

        # 2. Insert two test questions
        q1 = EvalBenchmarkQuestion(
            question_text="Paris PM2.5 levels?",
            expected_domains=["air_quality"],
            expected_complexity="trivial",
            reference_answer="Paris has good air quality",
            reference_evidence={"source": "test_env"},
        )
        q2 = EvalBenchmarkQuestion(
            question_text="Beijing PM2.5 levels?",
            expected_domains=["air_quality"],
            expected_complexity="trivial",
            reference_answer="Beijing has high pollution",
            reference_evidence={"source": "test_env"},
        )
        db_session.add_all([q1, q2])
        await db_session.commit()

        # Refresh to get IDs
        await db_session.refresh(q1)
        await db_session.refresh(q2)

        # 3. Run the benchmark suite
        orchestrator_ver = "test-version-v1.0-alpha"
        result = await run_benchmark_suite(
            orchestrator_version=orchestrator_ver,
            session=db_session,
        )

        # 4. Verify in-memory result model
        assert result.total_questions == 2
        assert result.successful_runs == 2
        assert len(result.results) == 2

        # Verify items
        res_map = {res.question_id: res for res in result.results}
        assert q1.id in res_map
        assert q2.id in res_map

        assert res_map[q1.id].orchestrator_version == orchestrator_ver
        assert res_map[q1.id].score is None  # stub returns None
        m1 = res_map[q1.id].metrics
        assert m1 is not None
        assert m1["status"] == "stub_scored"

        # 5. Verify database persistence
        db_runs = (await db_session.execute(select(EvalBenchmarkRun))).scalars().all()
        assert len(db_runs) == 2

        run_map = {run.benchmark_question_id: run for run in db_runs}
        assert q1.id in run_map
        assert q2.id in run_map

        assert run_map[q1.id].orchestrator_version == orchestrator_ver
        m2 = run_map[q1.id].metrics
        assert m2 is not None
        assert m2["status"] == "stub_scored"
