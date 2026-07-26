"""Unit tests for AlertRule schema validation and threshold comparison logic (Milestone 3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alerting.evaluator import _is_threshold_violated
from alerting.rules import DEFAULT_ALERT_RULES, AlertRuleSchema


class TestAlertRules:
    """Unit tests for alert rule schemas and comparison operators."""

    def test_default_alert_rules_valid(self) -> None:
        """Default system rules parse successfully into AlertRuleSchema."""
        for rule_dict in DEFAULT_ALERT_RULES:
            schema = AlertRuleSchema.model_validate(rule_dict)
            assert schema.name
            assert schema.threshold > 0

    def test_threshold_comparison_logic(self) -> None:
        """Verify greater-than (gt) and less-than (lt) comparison logic."""
        # GT checks
        assert _is_threshold_violated(10500.0, 10000.0, "gt")
        assert not _is_threshold_violated(9500.0, 10000.0, "gt")
        assert not _is_threshold_violated(10000.0, 10000.0, "gt")

        # LT checks
        assert _is_threshold_violated(0.85, 0.90, "lt")
        assert not _is_threshold_violated(0.95, 0.90, "lt")
        assert not _is_threshold_violated(0.90, 0.90, "lt")

    def test_invalid_comparison_rejected(self) -> None:
        """Schema rejects unsupported comparison operators."""
        with pytest.raises(ValidationError):
            AlertRuleSchema(
                name="test_rule",
                metric="p95_latency",
                threshold=100.0,
                comparison="invalid_op",  # type: ignore[arg-type]
            )

    def test_invalid_window_rejected(self) -> None:
        """Schema rejects unsupported window literals."""
        with pytest.raises(ValidationError):
            AlertRuleSchema(
                name="test_rule",
                metric="p95_latency",
                threshold=100.0,
                window="2h",  # type: ignore[arg-type]
            )
