# Simulation Parameter Calibration Methodology

This document outlines the offline, versioned calibration architecture and fitting math implemented in Phase 6 Milestone 5 to align statistical simulation models against real historical hazard and atmospheric reanalysis outcomes.

## 1. Parameters Config Files Schema

Calibrated parameters are stored in `config/simulation_parameters/` as YAML files:
- Versioned files (immutable): `{model_name}_v{N}.yaml`
- Active pointer file: `{model_name}_latest.yaml`

### File structure:
```yaml
model_name: wildfire_spread
version: 1
fitted_at: "2026-08-05T12:00:00Z"
validation_report:
  sample_count: 10
  baseline_score: 5.4321
  promoted_score: 3.2104
parameters:
  wind_coefficient: 0.3845
  temp_coefficient: 0.0912
  low_bound_factor: 0.6214
  high_bound_factor: 1.2541
```

---

## 2. Fitting Mathematics

### A. Wildfire Spread Model
Equation: $\text{spread\_rate} = \text{wind\_speed} \times w + \text{temperature} \times t$.
We fit $w$ and $t$ using standard closed-form least-squares linear regression:
$$\beta = (X^T X)^{-1} X^T y$$
Where $X$ is the matrix containing paired wind speed and temperature samples from matching ERA5 baselines, and $y$ is the observed spread rate target derived from Copernicus wildfire sentinel products.

### B. Flood Extent Model
Equation: $\text{flooded\_area} = \text{rainfall} \times \beta$.
We fit single-coefficient linear regression (without intercept):
$$\beta = \frac{\sum x_i y_i}{\sum x_i^2}$$
Where $x_i$ is rainfall (precipitation) from ERA5 reanalysis and $y_i$ is observed flooded area.

### C. Plume Dispersion Model
Equation: $\text{dispersion\_distance} = \text{wind\_speed} \times \beta$.
We fit single-coefficient linear regression:
$$\beta = \frac{\sum x_i y_i}{\sum x_i^2}$$
Where $x_i$ is ERA5 wind speed and $y_i$ is observed plume dispersion distance.

### D. ENSO Forecast Model
Anomaly boundaries are fit by sorting the anomalies in the training set:
- $\text{el\_nino\_threshold}$ = 90th percentile of anomalies.
- $\text{la\_nina\_threshold}$ = 10th percentile of anomalies.
- $\text{low\_bound\_offset}$ and $\text{high\_bound\_offset}$ are scaled based on the standard deviation of historical NOAA ocean temperature anomalies.

---

## 3. Promotion Gate Logic

1. Query all matching historical hazard and atmospheric reanalysis records from PostgreSQL.
2. Shuffle and split records into **80% training** and **20% validation** (held-out) sets.
3. If total matched samples $< 5$, skip calibration for this model and preserve existing parameters.
4. Calculate new candidate parameters on the training set.
5. Compute validation scores (RMSE or error rate) on the validation set for both the **current active parameters** (baseline) and **candidate parameters** (new fit).
6. **Gate check**: Promote and write version `{N+1}` to the config directory only if `candidate_score <= baseline_score`. Otherwise, keep the current parameter files active.
