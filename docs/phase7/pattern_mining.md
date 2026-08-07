# Longitudinal Pattern Mining & Research Insights

Phase 7 Milestone 2 introduces automated **longitudinal pattern mining** over historical multi-source hazard data in GaiaOS.

---

## 1. Overview & Purpose

Every single-investigation query in GaiaOS analyzes hazard events within a bounded temporal/spatial window. With multi-source historical ingestion (USGS, NOAA, Copernicus, ERA5, NASA FIRMS, GDELT), GaiaOS now maintains a rich longitudinal record of global events.

The longitudinal pattern mining pipeline periodically scans historical hazard events to identify **statistically significant recurring co-occurrence patterns** across event types (e.g. "seismic activity in region X is followed by sea surface temperature anomalies within N days at a rate meaningfully above baseline").

Findings are computed by background RQ jobs, stored in a versioned `pattern_findings` table, and exposed via the read-only Public Research API (`GET /api/v1/research/patterns`) and the Admin UI.

---

## 2. Statistical Co-Occurrence Methodology

Pattern mining relies on **deterministic statistical computation**, deliberately avoiding LLM-based pattern guessing or prompt-driven pattern extraction.

### A. Conditional Rate & Baseline Rate
Given a source event type $E_{\text{src}}$, a target event type $E_{\text{tgt}}$, a geographic region $R$, and a time window $\Delta t \in \{7, 14, 30\}$ days over an observation lookback period $T$:

- **Support Count ($k$)**: Number of distinct source events $e_{\text{src}} \in E_{\text{src}}$ that are followed by at least one target event $e_{\text{tgt}} \in E_{\text{tgt}}$ within $0 < t(e_{\text{tgt}}) - t(e_{\text{src}}) \le \Delta t$.
- **Observed Conditional Rate ($\hat{p}$)**:
  $$\hat{p} = P(E_{\text{tgt}} \mid E_{\text{src}}) = \frac{k}{N_{\text{src}}}$$
  where $N_{\text{src}}$ is the total count of source events in region $R$ during lookback $T$.
- **Baseline Background Rate ($p_0$)**:
  $$p_0 = P(E_{\text{tgt}}) = \frac{N_{\text{tgt}}}{N_{\text{total\_events}}}$$
- **Statistical Lift ($L$)**:
  $$\text{Lift} = \frac{\hat{p}}{p_0}$$
  A pattern is considered candidate-valid only if $\text{Lift} > 1.0$ (indicating positive statistical association beyond random expectation).

### B. Wilson Score Interval (Confidence Lower Bound)
To prevent small-sample overestimation (e.g., 2 co-occurrences out of 2 events yielding $\hat{p}=1.0$), statistical confidence is defined as the **lower bound of the 95% Wilson score interval** for a binomial proportion:

$$p_{\text{lower}} = \frac{\hat{p} + \frac{z^2}{2N_{\text{src}}} - z \sqrt{\frac{\hat{p}(1-\hat{p})}{N_{\text{src}}} + \frac{z^2}{4N_{\text{src}}^2}}}{1 + \frac{z^2}{N_{\text{src}}}}$$

where $z = 1.96$ corresponds to standard 95% confidence ($\alpha \le 0.05$). A pattern candidate is accepted only if $p_{\text{lower}} \ge \text{PATTERN\_MIN\_CONFIDENCE}$.

---

## 3. Configuration & Parameter Thresholds

All thresholds are exposed as environment settings in `config/settings.py`:

| Parameter | Default | Description |
|---|---|---|
| `PATTERN_MIN_SUPPORT` | `3` | Minimum co-occurring event pairs required. |
| `PATTERN_MIN_CONFIDENCE` | `0.70` | Minimum Wilson lower-bound statistical confidence. |
| `PATTERN_SIGNIFICANCE_LEVEL` | `0.05` | Maximum $p$-value significance threshold ($\alpha$). |
| `PATTERN_LOOKBACK_DAYS` | `90` | Historical observation window in days. |
| `PATTERN_MINING_INTERVAL_HOURS` | `24` | Interval between background mining job runs. |

---

## 4. Association vs. Causation

> [!IMPORTANT]
> Longitudinal pattern mining detects **historical statistical association** ($P(E_{\text{tgt}} \mid E_{\text{src}}) > P(E_{\text{tgt}})$), **not direct physical causation**.
> 
> A high statistical lift score indicates that target events recur after source events with high probability in historical data. Physical causal verification is performed separately by Causal Chain agents during active investigations.

---

## 5. Storage, Idempotency & Versioning

- **Stable Pattern Hash**: Every pattern finding is uniquely identified by a SHA-256 hash:
  $$\text{pattern\_hash} = \text{SHA256}(\text{algorithm\_version} : \text{source\_type} : \text{target\_type} : \text{region} : \text{time\_window})$$
- **Versioning**: When a background run re-evaluates an existing `pattern_hash`, `PatternFindingRepository.save_pattern_version()` marks prior entries `is_active=False` and inserts a new active row with `version = previous_version + 1`. This preserves historical confidence trajectories over time.
- **Shared Uncertainty Schema**: Integrates `UncertaintyEstimate` from `orchestrator/schemas/uncertainty.py` (`point_estimate`, `lower_bound`, `upper_bound`, `source`).

---

## 6. Read-Only Public Research API

`GET /api/v1/research/patterns` provides paginated access to active pattern findings:

```json
[
  {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "pattern_hash": "a1f9e...",
    "algorithm_version": "1.0",
    "version": 1,
    "source_event_type": "earthquake",
    "target_event_type": "ocean_temperature_anomaly",
    "region_label": "Pacific Rim",
    "time_window_days": 14,
    "support_count": 5,
    "total_source_events": 6,
    "total_target_events": 12,
    "observed_rate": 0.8333,
    "baseline_rate": 0.15,
    "lift": 5.5556,
    "statistical_confidence": 0.7241,
    "uncertainty": {
      "point_estimate": 0.7241,
      "lower_bound": 0.6441,
      "upper_bound": 0.8041,
      "source": "model_uncertainty"
    },
    "supporting_event_ids": ["uuid-1", "uuid-2"],
    "description": "Longitudinal pattern: Earthquake is followed by Ocean_Temperature_Anomaly in Pacific Rim within 14 days...",
    "mined_at": "2026-08-07T00:00:00Z",
    "created_at": "2026-08-07T00:00:00Z"
  }
]
```

Query Parameters: `event_type`, `region`, `time_window_days`, `min_confidence`, `sort_by`, `order`, `limit`, `offset`.

---

## 7. Limitations

1. **Correlation Bias**: Does not account for unobserved confounding variables.
2. **Coarse Spatial Resolution**: Relies on `region_label` string matching rather than continuous spatial density estimation.

---

## 8. Future Extensions

- **Bayesian Prior Updating**: Incorporating domain literature priors into Wilson interval bounds.
- **Spatiotemporal Graph Clustering**: Replacing discrete `time_window_days` with continuous kernel density estimations.
- **Seasonal Decomposition**: Removing annual seasonal baseline noise prior to lift calculation.
