# Service Level Objectives (SLOs) & Error Budgets

## Overview

GaiaOS formalizes explicit Service Level Objectives (SLOs) covering both **operational** (latency, availability) and **reasoning-quality** (calibration, citation fallback) dimensions.

Rather than relying purely on static, ad-hoc metric threshold alerts, alerting in Phase 5 Milestone 8 is driven by **error-budget burn-rate evaluation**. This pattern alerts operators when an error budget is being consumed too quickly, providing lead time *before* the total budget is exhausted.

---

## SLO Definitions & Target Rationale

Versioned SLO definitions are maintained in [`config/slo_definitions.yaml`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/config/slo_definitions.yaml).

### 1. Investigation p95 Latency (`investigation_p95_latency`)

- **Domain**: Operational
- **Metric**: `investigation.p95_latency_ms`
- **Target**: 95.0% (`0.95`)
- **Threshold**: `<= 10,000 ms`
- **Window**: 30 days (`30d`)
- **Error Budget Burn Threshold**: `10.0x`
- **Rationale**: 10 seconds (10,000ms) represents the maximum tolerable latency threshold for synchronous and near-real-time complex multi-step reasoning workflows before client timeouts or degraded user experience occur. A 95% target accommodates heavy multi-domain graph processing queries while ensuring consistent p95 performance.

### 2. Job Success Rate (`job_success_rate`)

- **Domain**: Operational
- **Metric**: `investigation.job_success_rate`
- **Target**: 99.0% (`0.99`)
- **Threshold**: `>= 0.99`
- **Window**: 30 days (`30d`)
- **Error Budget Burn Threshold**: `10.0x`
- **Rationale**: Background worker jobs power ingestion, graph reasoning, backup routines, and evaluation tasks. A 99.0% success target allows a 1.0% failure budget for transient external API outages or infrastructure blips while preserving job pipeline reliability.

### 3. Calibration ECE (`calibration_ece`)

- **Domain**: Reasoning Quality
- **Metric**: `calibration_ece`
- **Target**: 95.0% (`0.95`)
- **Threshold**: `<= 0.05`
- **Window**: 30 days (`30d`)
- **Error Budget Burn Threshold**: `10.0x`
- **Rationale**: Expected Calibration Error (ECE) measures how well predicted confidence scores align with empirical accuracy (introduced in Phase 5 Milestone 1). An ECE <= 0.05 guarantees that confidence estimates are trustworthy and calibrated across 95% of benchmark evaluation runs.

### 4. Citation Fallback Rate (`citation_fallback_rate`)

- **Domain**: Reasoning Quality
- **Metric**: `citation_fallback_rate`
- **Target**: 95.0% (`0.95`)
- **Threshold**: `<= 0.05`
- **Window**: 30 days (`30d`)
- **Error Budget Burn Threshold**: `10.0x`
- **Rationale**: Citation fallback occurs when evidence sources cannot be mapped cleanly to primary document chunks. Keeping fallback rates under 5.0% across 95% of evaluations ensures that research outputs are grounded in explicit citations rather than fallback statements.

---

## Burn-Rate Alerting Logic

For each SLO:
1. **Allowed Error Rate**: $1.0 - \text{target}$ (e.g., target 0.99 $\rightarrow$ 0.01 allowed error rate).
2. **Observed Error Rate**: $\frac{\text{bad events}}{\text{total events}}$.
3. **Burn Rate**: $\frac{\text{Observed Error Rate}}{\text{Allowed Error Rate}}$.
4. **Budget Remaining %**: $\max(0.0, (1.0 - \text{Burn Rate}) \times 100.0)$.

An incident is created (tagged with `slo_name`) when $\text{Burn Rate} \ge \text{error\_budget\_burn\_alert\_threshold}$.

### Insufficient Data Handling

When a time window contains 0 data points (e.g. newly registered SLO or cold-start system), the evaluator returns `insufficient_data = True`. No false-positive firing or false-negative resolution is triggered during an insufficient data state.
