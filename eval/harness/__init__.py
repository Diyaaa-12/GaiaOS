"""Evaluation harness package.

Contains the benchmark suite runner, scoring logic, and CI regression gate.
"""

from eval.harness.ci_gate import (
    RegressionReport,
    check_for_regression,
    run_ci_gate,
    sync_benchmark_questions,
)
from eval.harness.runner import (
    fetch_latest_baseline_suite_result,
    run_benchmark_suite,
)
from eval.harness.scorer import score_result

__all__ = [
    "RegressionReport",
    "check_for_regression",
    "fetch_latest_baseline_suite_result",
    "run_benchmark_suite",
    "run_ci_gate",
    "score_result",
    "sync_benchmark_questions",
]
