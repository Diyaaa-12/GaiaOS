"""Classifier implementation for evaluating query complexity and domain matching."""

from __future__ import annotations

import re
from typing import Any

from logging_config import get_logger
from orchestrator.schemas.complexity import ComplexityTier

_log = get_logger(__name__)

# Specific complexity and hazard keywords (no generic English words like 'and' or 'multiple')
COMPLEX_KEYWORDS = [
    r"\bpredict\b",
    r"\bforecast\b",
    r"\bsimulat(e|ion)\b",
    r"\bcausal\b",
    r"\btrigger\b",
    r"\baffect\b",
    r"\btsunamis?\b",
    r"\bhistorical\s+modeling\b",
]

MODERATE_KEYWORDS = [
    r"\bseismic\b",
    r"\bocean\b",
    r"\batmosphere\b",
    r"\bwildfires?\b",
    r"\bearthquakes?\b",
    r"\bfloods?\b",
    r"\bhurricanes?\b",
]

# Explicit regex match patterns for target domains to prevent substring false positives
DOMAIN_PATTERNS = {
    "air_quality": [r"\bair\s+quality\b", r"\bpm2\.5\b", r"\bpm10\b", r"\baqi\b"],
    "seismic": [r"\bseismic\b", r"\bearthquakes?\b"],
    "ocean": [r"\boceans?\b", r"\bsea\b", r"\btsunamis?\b", r"\btidal\s+waves?\b"],
    "atmosphere": [
        r"\batmosphere\b",
        r"\bwinds?\b",
        r"\bweather\b",
        r"\bair\s+temperature\b",
    ],
    "wildfire": [r"\bwildfires?\b", r"\bfires?\b"],
    "literature": [
        r"\bliterature\b",
        r"\bpapers?\b",
        r"\breports?\b",
        r"\bstudies\b",
        r"\bstudy\b",
        r"\bresearch\b",
        r"\barticles?\b",
    ],
}


async def classify_query_complexity(query: str) -> dict[str, Any]:
    """Classify the complexity of a user query and identify target domains.

    Simulates query classification based on explicit environmental keywords.
    """
    query_lower = query.lower()

    # Priority routing: check complex keywords first, then moderate.
    is_complex = any(re.search(pat, query_lower) for pat in COMPLEX_KEYWORDS)
    is_moderate = any(re.search(pat, query_lower) for pat in MODERATE_KEYWORDS)

    # Resolve matched domains using boundary-guarded regexes
    matched_domains = []
    for domain, patterns in DOMAIN_PATTERNS.items():
        if any(re.search(pat, query_lower) for pat in patterns):
            matched_domains.append(domain)

    # Complexity classification priority
    if is_complex:
        tier = ComplexityTier.COMPLEX
        rationale = "Query requires prediction, causal tracking, or historical forecasting."
    elif is_moderate or len(matched_domains) > 1:
        tier = ComplexityTier.MODERATE
        rationale = "Query spans multiple domain variables or moderate hazards."
    else:
        tier = ComplexityTier.TRIVIAL
        rationale = "Query is a simple, single-variable factual retrieval request."

    # Agnostic metadata naming for explainability tracing
    classification_metadata = {
        "predicted_tier": tier.value,
        "matched_domains": matched_domains,
        "classification_method": "heuristic",
        "rationale": rationale,
    }

    _log.info(
        "supervisor.classifier.success",
        query=query,
        tier=tier.value,
        matched_domains=matched_domains,
        rationale=rationale,
    )

    return {
        "tier": tier,
        "matched_domains": matched_domains,
        "classification_metadata": classification_metadata,
    }
