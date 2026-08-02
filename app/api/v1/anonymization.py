"""Single explicit anonymization policy engine — Phase 5 Milestone 9.

Defines exact rules for stripping PII, user identifiers, and raw query text
for non-consented investigations per ADR-504.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from db.models.investigation import Investigation

# Set of internal/PII keys that must never appear in public research responses
EXCLUDED_TRACE_KEYS: set[str] = {
    "user_id",
    "ip_address",
    "user_agent",
    "client_ip",
    "authorization",
    "token",
    "email",
    "password",
    "secret",
    "api_key",
    "credentials",
    "cookie",
    "session_id",
}


class AnonymizationPolicy:
    """Policy engine enforcing anonymization rules for public research data."""

    @staticmethod
    def derive_query_category(query: str, complexity_tier: str | None = None) -> str:
        """Derive a generalized, non-identifying query category using domain regex rules."""
        words = set(re.findall(r"\w+", query.lower()))
        if words & {"earthquake", "seismic", "fault", "tremor", "magnitude"}:
            return "seismic_research"
        if words & {"wildfire", "fire", "burn", "smoke", "firms"}:
            return "wildfire_research"
        if words & {"ocean", "sst", "marine", "sea", "wave"}:
            return "oceanographic_research"
        if words & {"air", "atmosphere", "co2", "emissions", "pm25", "ozone"}:
            return "atmospheric_research"

        if complexity_tier:
            return f"{complexity_tier}_environmental_research"
        return "general_environmental_research"

    @staticmethod
    def extract_domains_involved(execution_trace: dict[str, Any] | None) -> list[str]:
        """Extract list of active domains involved in investigation execution trace."""
        if not execution_trace:
            return []
        domains = execution_trace.get("domains") or execution_trace.get("active_agents") or []
        if isinstance(domains, list):
            return [str(d) for d in domains]
        return [str(domains)]

    @classmethod
    def sanitize_execution_trace(cls, trace: Any) -> Any:
        """Recursively strip internal and PII-adjacent fields from execution trace structures."""
        if isinstance(trace, dict):
            sanitized: dict[str, Any] = {}
            for key, value in trace.items():
                key_str = str(key).lower()
                if key_str in EXCLUDED_TRACE_KEYS or any(
                    s in key_str
                    for s in (
                        "token",
                        "secret",
                        "password",
                        "authorization",
                        "api_key",
                        "credentials",
                        "user_id",
                        "client_ip",
                        "user_agent",
                        "cookie",
                        "session_id",
                    )
                ):
                    continue
                sanitized[key] = cls.sanitize_execution_trace(value)
            return sanitized
        if isinstance(trace, list):
            return [cls.sanitize_execution_trace(item) for item in trace]
        return trace

    @classmethod
    def apply(cls, investigation: Investigation) -> dict[str, Any]:
        """Apply anonymization rules to an Investigation row based on consent_public_research.

        Privacy Rules (ADR-504)
        -----------------------
        1. ``user_id`` is ALWAYS omitted / set to None (disassociated from user).
        2. If ``consent_public_research == False``:
           - ``query_text`` is stripped and replaced with generalized ``query_category``.
        3. If ``consent_public_research == True``:
           - ``query_text`` is included in anonymized research output.
        4. ``execution_trace`` is recursively sanitized to remove all internal/PII keys.
        """
        category = cls.derive_query_category(
            investigation.query_text, investigation.complexity_tier
        )
        domains = cls.extract_domains_involved(investigation.execution_trace)
        sanitized_trace = cls.sanitize_execution_trace(investigation.execution_trace)

        # Raw query text is included ONLY if consent_public_research is explicitly True
        consented_query_text = (
            investigation.query_text if investigation.consent_public_research else None
        )

        return {
            "investigation_id": str(investigation.id),
            "query_category": category,
            "domains_involved": domains,
            "complexity_tier": investigation.complexity_tier,
            "confidence_summary": (
                float(investigation.confidence) if investigation.confidence is not None else None
            ),
            "consent_public_research": investigation.consent_public_research,
            "query_text": consented_query_text,
            "execution_trace": sanitized_trace,
            "created_at": investigation.created_at.isoformat(),
            "completed_at": (
                investigation.completed_at.isoformat() if investigation.completed_at else None
            ),
        }


__all__ = ["AnonymizationPolicy"]
