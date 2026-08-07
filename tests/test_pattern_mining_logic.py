"""Unit tests for pattern mining statistical logic and hash generation (Phase 7 Milestone 2)."""

from __future__ import annotations

from workers.jobs.pattern_mining_job import (
    calculate_wilson_lower_bound,
    generate_pattern_hash,
)


class TestPatternMiningLogic:
    """Test suite for Wilson score bounds and deterministic hash generation."""

    def test_calculate_wilson_lower_bound_basic(self) -> None:
        """Wilson lower bound returns realistic conservative confidence values."""
        # 8 co-occurrences out of 10 events => observed ~0.80, Wilson lower ~0.49
        bound = calculate_wilson_lower_bound(successes=8, trials=10)
        assert 0.40 <= bound <= 0.80

        # 80 co-occurrences out of 100 events => observed ~0.80, Wilson lower ~0.71
        bound_large = calculate_wilson_lower_bound(successes=80, trials=100)
        assert 0.70 <= bound_large <= 0.80
        assert bound_large > bound  # Larger sample size yields higher confidence lower bound

    def test_calculate_wilson_lower_bound_edge_cases(self) -> None:
        """Zero trials or zero successes return 0.0 without division by zero."""
        assert calculate_wilson_lower_bound(successes=0, trials=10) == 0.0
        assert calculate_wilson_lower_bound(successes=5, trials=0) == 0.0
        assert calculate_wilson_lower_bound(successes=-1, trials=10) == 0.0

    def test_generate_pattern_hash_deterministic(self) -> None:
        """Pattern hash is deterministic across identical inputs and sensitive to changes."""
        h1 = generate_pattern_hash("earthquake", "tsunami", "Pacific", 14)
        h2 = generate_pattern_hash("Earthquake ", "TSUNAMI", " pacific ", 14)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex string

        # Different window yields different hash
        h3 = generate_pattern_hash("earthquake", "tsunami", "Pacific", 30)
        assert h1 != h3

        # Different algorithm version yields different hash
        h4 = generate_pattern_hash("earthquake", "tsunami", "Pacific", 14, algorithm_version="2.0")
        assert h1 != h4
