# Phase 3 Milestone 5 — Evaluation Harness Expansion & CI Regression Gate

## Overview

Milestone 5 expands the GaiaOS evaluation harness from a single initial test question into a 18-question domain-covering benchmark dataset. It establishes `ci_gate.py` as a thin CLI wrapper and regression checker, and integrates a scheduled nightly CI workflow with manual dispatch capabilities.

---

## 1. Benchmark Dataset & Ground Truth Policy

The curated benchmark suite (`eval/benchmarks/questions.json`) contains 18 domain-covering questions spanning all core GaiaOS operational domains:

- **Air Quality**: `air_quality_paris_pm25`, `air_quality_tokyo_aqi`, `air_quality_delhi_no2`
- **Seismic**: `seismic_california_m4`, `seismic_tokyo_hazards`, `seismic_ring_of_fire`
- **Ocean**: `ocean_florida_sst`, `ocean_gulf_stream`
- **Atmosphere**: `atmosphere_london_pressure`, `atmosphere_typhoon_path`
- **Wildfire**: `wildfire_california_hotspots`, `wildfire_amazon_detection`
- **Literature**: `literature_pm25_climate`, `literature_fault_mechanics`
- **Causal Chain**: `causal_smoke_airquality`, `causal_seismic_tsunami`
- **Simulation-Triggering**: `sim_smoke_dispersion_sf`
- **Unanswerable / Evidence Gap**: `unanswerable_gale_crater_nitrogen` (verifies honest refusal / evidence-gap handling)

### Ground Truth Expectations vs. Live Execution

- **Static Reference Expectations**: Each benchmark question defines frozen reference targets (`reference_answer` string and `reference_evidence` telemetry dictionary).
- **Dynamic Live Execution**: Benchmark runs execute live (or stubbed) agent queries against active external integrations or telemetry sources, comparing generated outputs against the static ground-truth references.

### Project-Specific UUID Namespace & Non-Destructive Sync

- **Stable Semantic Identifiers**: Questions use human-understandable keys (`air_quality_paris_pm25`). During synchronization (`sync_benchmark_questions`), these keys are mapped deterministically to UUID primary keys via the project-specific namespace:
  ```python
  GAIAOS_BENCHMARK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "gaiaos.eval.benchmarks")
  ```
- **Non-Destructive Question Sync**: By default (`overwrite=False`), `sync_benchmark_questions()` only inserts missing questions into `eval_benchmark_questions`, leaving existing database records intact. Overwriting requires an explicit `--overwrite-questions` flag.

---

## 2. Architecture & Seam Division

- **`eval/harness/runner.py` (Execution & Repository Layer)**:
  Handles querying `eval_benchmark_questions`, executing suite runs, scoring results via `score_result()`, persisting runs into `eval_benchmark_runs`, and retrieving prior baseline suite results (`fetch_latest_baseline_suite_result`).

- **`eval/harness/ci_gate.py` (Thin CI Regression Wrapper)**:
  Provides `sync_benchmark_questions()`, `check_for_regression()`, and `run_ci_gate()`. Delegates database baseline queries to `runner.py` and returns structured `RegressionReport` results.

---

## 3. Explicit Regression Policy

The regression check (`check_for_regression`) compares candidate run results (`current_run`) against the most recent baseline run (`baseline`) using a configurable threshold (default: `0.05`):

### Added / Removed Question Handling

To prevent benchmark expansion or pruning from corrupting score deltas, `check_for_regression` performs set analysis:
- **Common Questions**: $Q_{\text{common}} = Q_{\text{current}} \cap Q_{\text{baseline}}$
- **Added Questions**: $Q_{\text{added}} = Q_{\text{current}} \setminus Q_{\text{baseline}}$
- **Removed Questions**: $Q_{\text{removed}} = Q_{\text{baseline}} \setminus Q_{\text{current}}$

Overall mean scores and per-question deltas are computed exclusively over $Q_{\text{common}}$:

$$S_{\text{overall\_delta}} = \bar{S}_{\text{baseline}, Q_{\text{common}}} - \bar{S}_{\text{current}, Q_{\text{common}}}$$

$$S_{\text{question\_delta}, i} = s_{\text{baseline}, i} - s_{\text{current}, i} \quad \forall i \in Q_{\text{common}}$$

A suite execution is flagged as **Regressed (`regressed = True`)** if **EITHER**:
1. **Overall Regression**: Mean common score drops by more than the threshold ($S_{\text{overall\_delta}} > \text{threshold}$).
2. **Per-Question Regression**: Any individual common question score drops by more than the threshold ($S_{\text{question\_delta}, i} > \text{threshold}$).

---

## 4. CI Workflow Strategy & Trade-offs

- **Nightly Schedule (`.github/workflows/eval_nightly.yml`)**: Triggered at `02:00 UTC` daily.
- **Manual Dispatch (`workflow_dispatch`)**: Enables on-demand evaluation runs prior to major PR merges.
- **PR Velocity Protection**: Full benchmark suite runs are isolated from per-PR runs to prevent latencies, token costs, and flakiness from blocking normal PR workflow velocity.
