"""Evaluation harness package.

Contains the benchmark suite runner and scoring logic.
"""

from eval.harness.runner import run_benchmark_suite
from eval.harness.scorer import score_result

__all__ = [
    "run_benchmark_suite",
    "score_result",
]
