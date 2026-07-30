# Uncertainty Estimation Framework — Phase 5 Reference

**Schema Definition:** [`orchestrator/schemas/uncertainty.py`](../../orchestrator/schemas/uncertainty.py)  
**Propagation Engine:** [`orchestrator/agents/synthesis/uncertainty_propagation.py`](../../orchestrator/agents/synthesis/uncertainty_propagation.py)  
**Test Suite:** [`tests/test_uncertainty_propagation.py`](../../tests/test_uncertainty_propagation.py)

## Overview

GaiaOS replaces ad-hoc per-agent `confidence: float` numbers with a principled, consistent `UncertaintyEstimate` schema:

```python
class UncertaintyEstimate(BaseModel):
    point_estimate: float           # Value in [0.0, 1.0]
    lower_bound: float              # Lower bound in [0.0, 1.0]
    upper_bound: float              # Upper bound in [0.0, 1.0]
    source: Literal[
        "data_sparsity",
        "model_uncertainty",
        "evidence_conflict",
        "well_supported"
    ]
```

---

## Constants & Thresholds

| Constant | Value | Purpose | Rationale |
| :--- | :--- | :--- | :--- |
| `DEFAULT_LEGACY_FALLBACK_MARGIN` | `0.10` | Half-width for legacy float conversion | Conservative compatibility fallback only; not statistically derived. |
| `DEFAULT_POINT_ESTIMATE_INTERVAL_MARGIN` | `0.08` | Half-width for `from_point_estimate` | Standard symmetric interval around domain observations. |
| `CONFLICT_SPREAD_THRESHOLD` | `0.15` | Minimum point estimate spread for conflict | Intentionally conservative and deterministic to surface disagreement. |
| `MIN_CONFLICT_PADDING` | `0.05` | Minimum conflict interval expansion | Guarantees interval widens under conflict to avoid overconfidence. |

---

## Construction Helpers

### 1. `UncertaintyEstimate.from_point_estimate(point_estimate, margin=0.08, source="well_supported")`
Recommended constructor for domain agents. Generates a symmetric uncertainty interval around a central point estimate clamped to $[0.0, 1.0]$.

### 2. `UncertaintyEstimate.from_legacy_confidence(confidence)`
Backward-compatibility constructor. Automatically invoked when legacy payloads supply `confidence: float` without `uncertainty`.

---

## Combination Rules & Conflict Detection (`propagate_uncertainty`)

The `propagate_uncertainty` function aggregates uncertainty estimates across supporting evidence items according to strict mathematical invariants:

1. **Ordering Invariant & Range Constraints**:
   Field constraints (`ge=0.0, le=1.0`) enforce the valid numeric range $[0.0, 1.0]$. The model validator strictly enforces the ordering invariant $\text{lower\_bound} \le \text{point\_estimate} \le \text{upper\_bound}$ and raises a `ValidationError` if violated.

2. **Automatic Conflict Detection**:
   An `evidence_conflict` tag (`source = "evidence_conflict"`) is derived automatically during aggregation if ANY of the following hold:
   - **Spread threshold:** $\max(\text{point\_estimate}) - \min(\text{point\_estimate}) \ge \text{CONFLICT\_SPREAD\_THRESHOLD}\ (0.15)$.
   - **Disjoint intervals:** Pairwise evaluation (`itertools.combinations`) reveals non-overlapping bounds ($e_1.\text{upper\_bound} < e_2.\text{lower\_bound}$ or $e_2.\text{upper\_bound} < e_1.\text{lower\_bound}$).
   - **Propagated conflict:** Any input evidence item already has `source == "evidence_conflict"`.

3. **Never Narrows Invariant**:
   When combining conflicting evidence, the resulting uncertainty interval **never narrows** relative to any input evidence:
   $$\text{combined\_lower} \le \min_i (\text{lower}_i), \quad \text{combined\_upper} \ge \max_i (\text{upper}_i)$$

---

## Migration & Backward Compatibility Guidelines

> [!IMPORTANT]
> - `confidence` is **deprecated as a stored field** in `Evidence` and `SynthesizedClaim`.
> - `confidence` remains available as a **read-only compatibility property** returning `uncertainty.point_estimate`.
> - All new code and new domain agents **must use `uncertainty`**.
> - Existing plugins and legacy callers providing `confidence: float` remain fully compatible via automatic schema conversion.

Existing consumers should migrate to `uncertainty`; the backward-compatible `confidence` property will remain during the Phase 5 migration period.
