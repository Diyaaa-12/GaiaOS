"""Calibration metric: Expected Calibration Error (ECE).

Formula: ECE = Σ_b (|B_b| / n) × |accuracy(B_b) − confidence(B_b)|

See docs/phase5/eval_metrics.md for derivation and usage guide.
"""

from __future__ import annotations


def calculate_calibration(
    predictions: list[tuple[float, bool]],
    n_bins: int = 10,
) -> float:
    """Return the Expected Calibration Error over a set of predictions.

    Args:
        predictions: Non-empty list of ``(confidence, is_correct)`` pairs.
            Confidence values must be in ``[0.0, 1.0]``.
            Callers are responsible for ensuring the list is non-empty before
            calling; this function raises ``ValueError`` on empty input.
            ECE is a population statistic — pass all pairs from a full suite
            run, not one pair per question.
        n_bins: Equal-width bins over ``[0.0, 1.0]``. Default: 10 (ADR-501).

    Returns:
        ECE as a ``float`` in ``[0.0, 1.0]``.

    Raises:
        ValueError: If ``predictions`` is empty.
    """
    if not predictions:
        raise ValueError(
            "calculate_calibration requires at least one prediction. "
            "Guard with 'if predictions' in the caller before invoking."
        )

    n = len(predictions)
    bin_size = 1.0 / n_bins
    ece = 0.0

    for i in range(n_bins):
        lower = i * bin_size
        upper = lower + bin_size
        # Final bin is closed on the right to include confidence == 1.0.
        if i == n_bins - 1:
            in_bin = [(c, a) for c, a in predictions if lower <= c <= upper]
        else:
            in_bin = [(c, a) for c, a in predictions if lower <= c < upper]

        if not in_bin:
            continue

        avg_conf = sum(c for c, _ in in_bin) / len(in_bin)
        avg_acc = sum(1 for _, a in in_bin if a) / len(in_bin)
        ece += (len(in_bin) / n) * abs(avg_conf - avg_acc)

    return ece
