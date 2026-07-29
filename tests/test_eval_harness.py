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

    async def test_benchmark_execution_and_persistence(self, db_session: AsyncSession) -> None:
        """Suite executes correctly against questions and persists scored results to database.

        The stub runner returns no evidence and no confidence value, so:
        - per-question score remains None (correctness methodology deferred).
        - retrieval_precision_status is "no_evidence_retrieved".
        - suite calibration_status is "insufficient_data".
        - suite precision_status is "insufficient_data".

        These are the correct, explicitly-marked outcomes for a stub runner —
        not silently-zero placeholders.
        """
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

        res_map = {res.question_id: res for res in result.results}
        assert q1.id in res_map
        assert q2.id in res_map

        assert res_map[q1.id].orchestrator_version == orchestrator_ver

        # Per-question score is None — correctness methodology not yet defined.
        assert res_map[q1.id].score is None

        # Per-question metrics reflect the real scorer (not the old stub).
        m1 = res_map[q1.id].metrics
        assert m1 is not None
        assert m1["status"] == "scored"
        assert m1["confidence"] is None  # stub runner: no confidence signal
        assert m1["is_correct"] is None  # correctness methodology deferred
        assert m1["retrieval_precision"] is None  # no evidence retrieved from stub
        assert m1["retrieval_precision_status"] == "no_evidence_retrieved"

        # Suite-level metrics are merged into each per-question result.
        suite = m1["suite"]
        assert suite is not None
        assert suite["calibration_status"] == "insufficient_data"  # no pairs available
        assert suite["ece"] is None
        assert suite["ece_n_predictions"] == 0
        assert suite["precision_status"] == "insufficient_data"
        assert suite["mean_retrieval_precision"] is None
        assert suite["precision_n_questions"] == 0

        # 5. Verify database persistence
        db_runs = (await db_session.execute(select(EvalBenchmarkRun))).scalars().all()
        assert len(db_runs) == 2

        run_map = {run.benchmark_question_id: run for run in db_runs}
        assert q1.id in run_map
        assert q2.id in run_map

        assert run_map[q1.id].orchestrator_version == orchestrator_ver

        m2 = run_map[q1.id].metrics
        assert m2 is not None
        assert m2["status"] == "scored"
        assert m2["retrieval_precision_status"] == "no_evidence_retrieved"

        # Suite key is present in every persisted row.
        assert "suite" in m2
        assert m2["suite"]["calibration_status"] == "insufficient_data"
