"""ORM Database models package.

Exposes ORM mapped classes:
- EvalBenchmarkQuestion: Table representing curated benchmark questions.
- EvalBenchmarkRun: Table representing the outcome scores and metrics of runs.
"""

from db.models.eval_benchmark import EvalBenchmarkQuestion, EvalBenchmarkRun
from db.models.investigation import Investigation

__all__ = [
    "EvalBenchmarkQuestion",
    "EvalBenchmarkRun",
    "Investigation",
]
