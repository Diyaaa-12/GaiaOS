"""Unit tests for eval/metrics — ECE and retrieval precision.

These tests use textbook examples with known correct answers, not just
"runs without error."  Each test documents the expected mathematical result
alongside the assertion so that a failing test is self-explanatory.

Empty-input behavior is tested explicitly for both functions as required by
the Milestone 1 design specification.
"""

from __future__ import annotations

import pytest

from eval.metrics.calibration import calculate_calibration
from eval.metrics.retrieval_precision import calculate_retrieval_precision

# ===========================================================================
# calculate_calibration (ECE)
# ===========================================================================


class TestCalculateCalibration:
    """Unit tests for Expected Calibration Error."""

    # --- Empty-input behaviour (explicitly required by M1 spec) ----------

    def test_empty_predictions_raises_value_error(self) -> None:
        """Empty prediction list raises ValueError.

        calculate_calibration is a pure math function. Empty input is a
        precondition violation — the caller (scorer.score_suite) is responsible
        for guarding with 'if calibration_pairs' before calling.
        """
        with pytest.raises(ValueError, match="at least one prediction"):
            calculate_calibration([])

    # --- Textbook examples with known correct results --------------------

    def test_perfectly_miscalibrated_returns_1_0(self) -> None:
        """All predictions at maximum confidence and all wrong → ECE = 1.0.

        Calculation:
            All 4 predictions in bin [0.9, 1.0].
            avg_conf = 1.0,  avg_acc = 0.0
            ECE = (4/4) × |1.0 − 0.0| = 1.0
        """
        predictions = [(1.0, False), (1.0, False), (1.0, False), (1.0, False)]
        result = calculate_calibration(predictions)
        assert result == pytest.approx(1.0)

    def test_perfectly_calibrated_at_mid_confidence(self) -> None:
        """50 % correct at 0.5 confidence → ECE = 0.0 (perfectly calibrated).

        Calculation:
            Both predictions in bin [0.5, 0.6).
            avg_conf = 0.5,  avg_acc = 0.5
            ECE = (2/2) × |0.5 − 0.5| = 0.0
        """
        predictions = [(0.5, True), (0.5, False)]
        result = calculate_calibration(predictions)
        assert result == pytest.approx(0.0)

    def test_high_confidence_all_correct(self) -> None:
        """High confidence all correct: calibration error equals gap from 1.0.

        Calculation:
            3 predictions in bin [0.8, 0.9): avg_conf=0.8, avg_acc=1.0
            ECE = (3/3) × |0.8 − 1.0| = 0.2
        """
        predictions = [(0.8, True), (0.8, True), (0.8, True)]
        result = calculate_calibration(predictions)
        assert result == pytest.approx(0.2)

    def test_two_bins_symmetric_miscalibration(self) -> None:
        """Two equally-sized, symmetrically overconfident and underconfident bins.

        Calculation:
            5 predictions in bin [0.9, 1.0): avg_conf=0.9, avg_acc=0.0
              contribution = (5/10) × |0.9 − 0.0| = 0.45
            5 predictions in bin [0.1, 0.2): avg_conf=0.1, avg_acc=1.0
              contribution = (5/10) × |0.1 − 1.0| = 0.45
            ECE = 0.90
        """
        predictions = [(0.9, False)] * 5 + [(0.1, True)] * 5
        result = calculate_calibration(predictions)
        assert result == pytest.approx(0.90)

    def test_single_prediction(self) -> None:
        """Single prediction is a valid (if weak) ECE input.

        Calculation:
            1 prediction in bin [0.7, 0.8): avg_conf=0.7, avg_acc=0.0 (wrong)
            ECE = (1/1) × |0.7 − 0.0| = 0.7
        """
        predictions = [(0.7, False)]
        result = calculate_calibration(predictions)
        assert result == pytest.approx(0.7)

    def test_confidence_exactly_1_included_in_final_bin(self) -> None:
        """confidence == 1.0 must land in the final bin, not fall off the edge.

        Calculation:
            1 prediction at 1.0, correct → bin [0.9, 1.0] (closed right).
            avg_conf=1.0, avg_acc=1.0
            ECE = (1/1) × |1.0 − 1.0| = 0.0
        """
        predictions = [(1.0, True)]
        result = calculate_calibration(predictions)
        assert result == pytest.approx(0.0)

    def test_n_bins_parameter_respected(self) -> None:
        """Using n_bins=5 changes bin boundaries but the formula stays correct.

        With n_bins=5, bin size = 0.2.
        Prediction (0.8, False) falls in bin [0.8, 1.0) (bin index 4).
        avg_conf=0.8, avg_acc=0.0
        ECE = 1.0 × |0.8 − 0.0| = 0.8
        """
        predictions = [(0.8, False)]
        result = calculate_calibration(predictions, n_bins=5)
        assert result == pytest.approx(0.8)

    def test_returns_float_not_none_for_nonempty_input(self) -> None:
        """Non-empty input always produces a float, never None."""
        predictions = [(0.6, True), (0.4, False)]
        result = calculate_calibration(predictions)
        assert isinstance(result, float)

    def test_ece_bounded_between_zero_and_one(self) -> None:
        """ECE must lie in [0.0, 1.0] for any valid prediction list."""
        predictions = [
            (0.9, False),
            (0.1, True),
            (0.5, True),
            (0.5, False),
            (0.8, True),
        ]
        result = calculate_calibration(predictions)
        assert 0.0 <= result <= 1.0


# ===========================================================================
# calculate_retrieval_precision
# ===========================================================================


class TestCalculateRetrievalPrecision:
    """Unit tests for retrieval precision using chunk_id strings."""

    # --- Empty-input behaviour (explicitly required by M1 spec) ----------

    def test_empty_retrieved_returns_zero(self) -> None:
        """No chunks retrieved → precision = 0.0.

        Nothing was retrieved, so nothing relevant was retrieved.
        The function does not raise; it returns 0.0.
        """
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=[],
            relevant_chunk_ids={"chunk_a", "chunk_b"},
        )
        assert result == pytest.approx(0.0)

    def test_empty_relevant_set_returns_zero(self) -> None:
        """No relevant chunks defined → precision = 0.0.

        The intersection is always empty; no retrieved chunk can be relevant.
        Formula: 0 / len(retrieved) = 0.0
        """
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["chunk_x", "chunk_y"],
            relevant_chunk_ids=set(),
        )
        assert result == pytest.approx(0.0)

    def test_both_empty_returns_zero(self) -> None:
        """Both retrieved and relevant empty → 0.0 (early-exit path)."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=[],
            relevant_chunk_ids=set(),
        )
        assert result == pytest.approx(0.0)

    # --- Textbook examples -----------------------------------------------

    def test_all_retrieved_relevant(self) -> None:
        """Every retrieved chunk is relevant → precision = 1.0."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["a", "b", "c"],
            relevant_chunk_ids={"a", "b", "c", "d"},
        )
        assert result == pytest.approx(1.0)

    def test_no_retrieved_relevant(self) -> None:
        """No retrieved chunk is relevant → precision = 0.0."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["x", "y", "z"],
            relevant_chunk_ids={"a", "b", "c"},
        )
        assert result == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        """2 of 4 retrieved chunks are relevant → precision = 0.5."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["a", "b", "c", "d"],
            relevant_chunk_ids={"a", "b"},
        )
        assert result == pytest.approx(0.5)

    def test_one_of_three_relevant(self) -> None:
        """1 of 3 retrieved chunks is relevant → precision = 1/3."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["a", "b", "c"],
            relevant_chunk_ids={"b"},
        )
        assert result == pytest.approx(1 / 3)

    def test_single_retrieved_relevant(self) -> None:
        """Exactly one chunk retrieved and it is relevant → 1.0."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["chunk_a"],
            relevant_chunk_ids={"chunk_a"},
        )
        assert result == pytest.approx(1.0)

    def test_single_retrieved_not_relevant(self) -> None:
        """Exactly one chunk retrieved and it is NOT relevant → 0.0."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["chunk_a"],
            relevant_chunk_ids={"chunk_b"},
        )
        assert result == pytest.approx(0.0)

    def test_result_bounded_between_zero_and_one(self) -> None:
        """Precision must lie in [0.0, 1.0] for any valid input."""
        result = calculate_retrieval_precision(
            retrieved_chunk_ids=["a", "b", "c", "d", "e"],
            relevant_chunk_ids={"b", "d"},
        )
        assert 0.0 <= result <= 1.0
