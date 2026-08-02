"""Background worker job for alert rule & SLO evaluation — Phase 4 M3 & Phase 5 M8."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from alerting.channels.webhook import WebhookNotificationChannel
from alerting.evaluator import evaluate_rules, evaluate_slos
from alerting.rules import DEFAULT_ALERT_RULES, AlertResolution
from alerting.slo import load_slo_definitions
from config.settings import get_settings
from db.repository import AlertRepository
from db.session import AsyncSessionLocal, init_engine
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


async def _async_run_alert_evaluation() -> None:
    """Asynchronous alert evaluation workflow.

    1. Idempotent default rule seeding on first run if table is empty.
    2. Query active AlertRules from database & load SLO definitions from YAML.
    3. Evaluate rules and SLO burn rates against metrics rollups & eval benchmark data.
    4. Reconcile firings/resolutions against open AlertIncidents (tagged with slo_name).
    5. Dispatch Webhook notifications and emit telemetry metrics.
    """
    settings = get_settings()
    configure_logging(settings)

    if not settings.alerting_enabled:
        _log.info("alerting.job.disabled_by_feature_flag")
        return

    if settings.database_url and AsyncSessionLocal is None:
        init_engine()

    from db.session import AsyncSessionLocal as session_factory

    if session_factory is None:
        _log.error("alerting.job.no_database_session")
        return

    start_time = time.monotonic()
    notifications_sent = 0
    notification_failures = 0

    async with session_factory() as session:
        # 1. Idempotent default rule seeding on first run if alert_rules is empty
        all_rules = await AlertRepository.list_alert_rules(session)
        if not all_rules:
            _log.info("alerting.job.seeding_default_rules")
            for rule_def in DEFAULT_ALERT_RULES:
                await AlertRepository.upsert_alert_rule(
                    session=session,
                    name=str(rule_def["name"]),
                    metric=str(rule_def["metric"]),
                    threshold=float(rule_def["threshold"]),
                    comparison=str(rule_def["comparison"]),
                    window=str(rule_def["window"]),
                    severity=str(rule_def["severity"]),
                    consecutive_cycles=int(rule_def["consecutive_cycles"]),
                    is_enabled=bool(rule_def["is_enabled"]),
                )
            all_rules = await AlertRepository.list_alert_rules(session)

        active_rules = [r for r in all_rules if r.is_enabled]
        slos = load_slo_definitions()
        _log.info("alerting.job.evaluating", rules_count=len(active_rules), slos_count=len(slos))

        # 2. Evaluate active rules and SLO burn rates
        rule_firings = await evaluate_rules(session, active_rules)
        slo_firings, slo_burn_results = await evaluate_slos(session, slos)

        # Emit telemetry metrics for SLOs
        for slo_name, result in slo_burn_results.items():
            _log.info(
                "metrics.slo_status",
                slo_name=slo_name,
                slo_burn_rate=result.current_burn_rate,
                slo_budget_remaining_pct=result.budget_remaining_pct,
                insufficient_data=result.insufficient_data,
            )

        rule_firing_names = {f.rule_name: f for f in rule_firings}
        all_firing_names = {f.rule_name: f for f in (rule_firings + slo_firings)}

        notifier = WebhookNotificationChannel(webhook_url=settings.alert_webhook_url)

        # 3a. Process threshold-based AlertRule firings (preserving Phase 4 flapping suppression)
        for rule in active_rules:
            if rule.name in rule_firing_names:
                firing = rule_firing_names[rule.name]
                open_incident = await AlertRepository.get_open_incident_by_rule_name(
                    session, rule.name
                )

                if not open_incident:
                    inc = await AlertRepository.create_incident(
                        session=session,
                        rule_id=rule.id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        last_value=firing.current_value,
                        threshold=rule.threshold,
                        consecutive_violations=1,
                    )
                    if inc.consecutive_violations >= rule.consecutive_cycles:
                        success = await notifier.notify(firing)
                        if success:
                            notifications_sent += 1
                        else:
                            notification_failures += 1
                else:
                    new_violations = open_incident.consecutive_violations + 1
                    await AlertRepository.update_incident_last_value(
                        session=session,
                        incident_id=open_incident.id,
                        last_value=firing.current_value,
                        consecutive_violations=new_violations,
                    )
                    if new_violations == rule.consecutive_cycles:
                        success = await notifier.notify(firing)
                        if success:
                            notifications_sent += 1
                        else:
                            notification_failures += 1

        # 3b. Process SLO burn rate firings (additive)
        for firing in slo_firings:
            open_incident = await AlertRepository.get_open_incident_by_rule_name(
                session, firing.rule_name
            )

            if not open_incident:
                await AlertRepository.create_incident(
                    session=session,
                    rule_id=None,
                    rule_name=firing.rule_name,
                    severity=firing.severity,
                    last_value=firing.current_value,
                    threshold=firing.threshold,
                    consecutive_violations=1,
                    slo_name=firing.slo_name,
                )
                success = await notifier.notify(firing)
                if success:
                    notifications_sent += 1
                else:
                    notification_failures += 1
            else:
                new_violations = open_incident.consecutive_violations + 1
                await AlertRepository.update_incident_last_value(
                    session=session,
                    incident_id=open_incident.id,
                    last_value=firing.current_value,
                    consecutive_violations=new_violations,
                )

        # 4. Resolve cleared incidents
        open_incidents = await AlertRepository.list_incidents(session, status="firing")
        for incident in open_incidents:
            if incident.rule_name not in all_firing_names:
                resolved_inc = await AlertRepository.resolve_incident(session, incident.id)
                if resolved_inc:
                    resolution = AlertResolution(
                        rule_name=incident.rule_name,
                        metric=incident.rule_name,
                        severity=incident.severity,
                    )
                    success = await notifier.notify(resolution)
                    if success:
                        notifications_sent += 1
                    else:
                        notification_failures += 1

    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    _log.info(
        "alerting.job.completed",
        duration_ms=duration_ms,
        firings_count=len(all_firing_names),
        notifications_sent=notifications_sent,
        notification_failures=notification_failures,
    )


def run_alert_evaluation_job(*args: Any, **kwargs: Any) -> None:
    """RQ synchronous worker entry point."""
    asyncio.run(_async_run_alert_evaluation())


__all__ = ["run_alert_evaluation_job"]
