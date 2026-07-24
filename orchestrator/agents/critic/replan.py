"""Bounded Critic Replan Loop logic and domain target builder."""

from __future__ import annotations

from config.settings import get_settings
from logging_config import get_logger
from orchestrator.agents.registry import agent_registry
from orchestrator.schemas.synthesis import CriticFlag

_log = get_logger(__name__)

# Keyword map for domain target resolution fallback
DOMAIN_KEYWORD_MAP: dict[str, list[str]] = {
    "air_quality": ["air_quality", "air quality", "pm2.5", "pm10", "aqi", "no2", "openaq"],
    "seismic": ["seismic", "earthquake", "fault", "magnitude", "usgs", "epicenter", "tremor"],
    "ocean": ["ocean", "sea surface", "temperature", "tide", "noaa", "sst", "gulf stream"],
    "atmosphere": ["atmosphere", "weather", "pressure", "wind", "meteo", "humidity", "trough"],
    "wildfire": ["wildfire", "fire", "thermal", "firms", "hotspot", "smoke", "plume"],
    "literature": ["literature", "paper", "study", "research", "citation"],
    "causal_chain": ["causal_chain", "causal", "chain", "causality"],
    "simulation": ["simulation", "dispersion", "forecast", "model"],
}


def should_replan(
    critic_flags: list[CriticFlag],
    replan_count: int,
    max_replans: int = 2,
    enabled: bool | None = None,
) -> bool:
    """Determine if a critic verification pass should trigger a replan cycle.

    Args:
        critic_flags: List of CriticFlag items annotated during verification.
        replan_count: Current number of replan cycles executed so far.
        max_replans: Maximum allowed replan cycles (default 2).
        enabled: Feature flag override. Defaults to Settings.enable_replan_loop.

    Returns:
        True if feature is enabled, replan_count < max_replans, and at least one
        high-severity flag exists; False otherwise.
    """
    is_enabled = enabled if enabled is not None else get_settings().enable_replan_loop
    if not is_enabled:
        _log.debug("critic.replan.disabled_by_feature_flag")
        return False

    if replan_count >= max_replans:
        _log.info(
            "critic.replan.max_replans_reached",
            replan_count=replan_count,
            max_replans=max_replans,
        )
        return False

    has_high_severity = any(f.severity == "high" for f in critic_flags)
    if has_high_severity:
        _log.info(
            "critic.replan.triggered",
            replan_count=replan_count,
            max_replans=max_replans,
            high_severity_count=sum(1 for f in critic_flags if f.severity == "high"),
        )
        return True

    return False


def build_replan_targets(
    critic_flags: list[CriticFlag],
    fallback_domains: list[str] | None = None,
) -> list[str]:
    """Identify targeted domain names to re-query for high-severity critic flags.

    Prioritizes structured `flagged_domains` metadata on high-severity flags.
    Falls back to keyword matching over claim text and reasons against registered domains.

    Args:
        critic_flags: List of CriticFlag items.
        fallback_domains: Optional list of fallback domains if no target matched.

    Returns:
        Deduplicated list of valid target domain names.
    """
    valid_domains = set(agent_registry.list_domains()) | {"simulation"}
    high_flags = [f for f in critic_flags if f.severity == "high"]
    target_flags = high_flags if high_flags else critic_flags

    targets: list[str] = []

    # Strategy 1: Use structured flagged_domains metadata where available
    for flag in target_flags:
        if flag.flagged_domains:
            for domain in flag.flagged_domains:
                domain_clean = domain.strip().lower()
                if domain_clean in valid_domains and domain_clean not in targets:
                    targets.append(domain_clean)

    if targets:
        _log.info("critic.replan.targets_from_structured_metadata", targets=targets)
        return targets

    # Strategy 2: Keyword mapping fallback over claim text and flagged reason
    for flag in target_flags:
        combined_text = f"{flag.claim_text} {flag.flagged_reason}".lower()
        for domain_name, keywords in DOMAIN_KEYWORD_MAP.items():
            if domain_name in valid_domains:
                if any(kw in combined_text for kw in keywords):
                    if domain_name not in targets:
                        targets.append(domain_name)

    if targets:
        _log.info("critic.replan.targets_from_keyword_mapping", targets=targets)
        return targets

    # Strategy 3: Fallback to passed fallback_domains or default
    if fallback_domains:
        valid_fallbacks = [d for d in fallback_domains if d in valid_domains]
        if valid_fallbacks:
            _log.info("critic.replan.targets_from_fallback", targets=valid_fallbacks)
            return valid_fallbacks

    default_target = ["air_quality"]
    _log.info("critic.replan.targets_default_fallback", targets=default_target)
    return default_target
