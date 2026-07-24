# Phase 3 Milestone 6 — Bounded Critic Replan Loop

## Overview

Milestone 6 implements the capped (maximum 2 cycles) Critic Replan Loop specified in Architecture v1.0 §3.10. When the Critic agent identifies high-severity verification flags (such as logical fallacies, over-generalizations, or unsupported claims), the graph conditionally loops back to re-query only the specific flagged domain agents, re-synthesize claims with updated evidence, and re-verify.

---

## 1. Feature Flag Control (`ENABLE_REPLAN_LOOP`)

To support controlled A/B evaluation against the Milestone 5 benchmark suite before enabling the loop permanently in production environments, the replan loop is governed by application settings in `config/settings.py`:

```env
ENABLE_REPLAN_LOOP=false # Default: false (passthrough mode)
```

When `ENABLE_REPLAN_LOOP` is `False`, `should_replan()` always evaluates to `False`, allowing the graph to bypass replan cycles and finalize immediately. When set to `True`, high-severity flags trigger targeted replan loops up to the configured cycle limit.

---

## 2. Architecture & Data Flow

```
   +-------------+
   | Supervisor  |
   +------+------+
          |
   +------v------+
   | Domain Exec | (air_quality / fan_out / simulation)
   +------+------+
          |
   +------v------+
   |  Synthesis  |<-------------------+
   +------+------+                    |
          |                           |
   +------v------+                    |
   |   Critic    |                    |
   +------+------+                    |
          |                           |
   [should_replan?] --- (Yes) ---> [ Replan Node ]
          |                        (Targeted re-query)
        (No)
          |
   +------v------+
   |  Finalize   | (Appends "Unresolved conflicting evidence." if cap reached)
   +------+------+
          |
   +------v------+
   |     END     |
   +-------------+
```

---

## 3. Targeted Domain Target Resolution

Rather than repeating a full fan-out of all query domains, `build_replan_targets()` targets only the specific domain agents relevant to the flagged claim:

1. **Structured Metadata (Priority 1)**: Inspects the `flagged_domains` metadata array optionally provided by the Critic LLM response schema. Validates each tag against registered domain names in `AgentRegistry`.
2. **Keyword Extraction (Priority 2 Fallback)**: If `flagged_domains` is absent, matches keywords in `claim_text` and `flagged_reason` against registered domain definitions (`air_quality`, `seismic`, `ocean`, `atmosphere`, `wildfire`, `literature`, `causal_chain`, `simulation`).
3. **Matched Domains Fallback (Priority 3 Fallback)**: Uses query-matched domains or defaults to `["air_quality"]`.

---

## 4. SSE Stream Observability (`ReplanningEvent`)

Each executed replan cycle logs telemetry and emits an SSE stream event to notify client applications:

```json
{
  "event": "replanning",
  "data": {
    "cycle_number": 1,
    "targeted_domains": ["seismic"],
    "trigger_reason": "Seismic magnitude claim contradicts cited telemetry"
  }
}
```

---

## 5. Bounded Cycle Cap & Unresolved Conflict Fallback

- **Cap Limit**: `max_replans = 2` (maximum 2 replan cycles per investigation).
- **Unresolved Conflict Fallback**: If the replan cap is reached (`replan_count >= 2`) and high-severity flags remain unresolved, `finalize_node` appends the explicit note:
  ```
  Unresolved conflicting evidence.
  ```
  This ensures GaiaOS remains honest regarding unresolved conflicting evidence rather than silently favoring one claim.
