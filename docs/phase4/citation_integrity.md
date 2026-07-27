# GaiaOS Phase 4 — Citation Integrity Upgrade (Evidence IDs)

## 1. Overview & Rationale
Prior to Phase 4 Milestone 4, `CitationMapper` validated synthesized citations using exact normalized text matching (`_normalize_text(source)` and `_normalize_text(claim)`). While functional in initial phases, text-matching suffered from key architectural limitations:
- **Disambiguation failure**: Multiple evidence items sharing identical claim text across different sources or confidence scores could not be uniquely identified.
- **LLM whitespace sensitivity**: Minor formatting or text alterations by LLMs risked false citation rejections.
- **Algorithmic inefficiency**: Text lookup required $O(N \cdot M)$ string comparisons.

Milestone 4 introduces a stable, immutable `id: UUID` to `Evidence` objects and upgrades `CitationMapper` to an ID-first matching architecture with $O(1)$ index lookups.

---

## 2. Evidence ID Lifecycle & Architectural Boundary Separation

### 2.1 Creation & Immutability
- **Creation**: An `Evidence` object's `id: UUID` is generated exactly once when instantiated by a domain agent (`Field(default_factory=uuid.uuid4)`).
- **Immutability**: `Evidence.id` is strictly non-nullable and immutable for the lifetime of an investigation.
- **Preservation**: Downstream components (`Synthesis`, `CitationMapper`, `Critic`, `execution_trace` JSONB, API endpoints) preserve existing IDs and must never overwrite or regenerate them.

### 2.2 Boundary Separation (`RawCitedEvidence` vs `Evidence`)
- **Internal Entity (`Evidence`)**: Internal domain entity representing verified evidence gathered from domain agents. `Evidence.id` is typed as strictly non-null `uuid.UUID`.
- **Boundary DTO (`RawCitedEvidence`)**: Raw citation payload parsed directly from LLM completion responses. `RawCitedEvidence.evidence_id` is typed as `uuid.UUID | None` to represent optional/nullable model citation inputs.
- **Response Schema Alignment**: In Synthesis Agent response schemas, `evidence_id` is defined as nullable (`{"type": ["string", "null"]}`), allowing LLM outputs omitting `evidence_id` to degrade gracefully through text fallback rather than failing JSON schema validation.
- **Validation Flow**:
  ```
  LLM JSON Payload -> RawCitedEvidence (evidence_id: UUID | None) -> CitationMapper -> Verified Evidence (id: UUID)
  ```
  Incoming `evidence_id` strings from `RawCitedEvidence` are validated via `uuid.UUID(str_val)`. If parsing fails or `evidence_id` is null/absent, the ID is treated as missing, triggering telemetry (`citation_missing_id`) and proceeding to text fallback.

---

## 3. Citation Mapping Algorithm & Fallback Strategy

`CitationMapper` operates an $O(1)$ dual-index architecture initialized once per synthesis validation cycle:

```
                  ┌────────────────────────┐
                  │   RawCitedEvidence     │
                  └───────────┬────────────┘
                              │
                    Valid UUID in id_index?
                   ┌──────────┴──────────┐
                   │                     │
                  YES                    NO
                   │                     │
        ┌──────────▼──────────┐ ┌────────▼─────────┐
        │   matched_by_id     │ │  citation_missing│
        │   (Claim Accepted)  │ │      _id         │
        └─────────────────────┘ └────────┬─────────┘
                                         │
                             Unique match in text_index?
                            ┌────────────┴───────────┐
                            │                        │
                           YES                       NO
                            │                        │
                 ┌──────────▼──────────┐    ┌────────▼────────┐
                 │matched_by_text_     │    │  len(matches)?  │
                 │      fallback       │    └────┬────────┬───┘
                 │  (Claim Accepted)   │         │        │
                 └─────────────────────┘        >1        0
                                                 │        │
                                      ┌──────────▼───┐ ┌──▼───────────┐
                                      │ citation_    │ │ citation_    │
                                      │ ambiguous_   │ │ fabrication_ │
                                      │ fallback     │ │   detected   │
                                      │ (Claim Rej.) │ │(Claim Rej.)  │
                                      └──────────────┘ └──────────────┘
```

1. **Primary Path (ID Match)**: Canonical UUID lookup in `id_index`. On hit, accepts claim and logs `synthesis.citation_mapper.matched_by_id`.
2. **Fallback Path (Text Match)**: Look up `(norm_source, norm_claim)` in `text_index`:
   - **Unique match (`len == 1`)**: Accepts claim and logs `synthesis.citation_mapper.matched_by_text_fallback`.
   - **Ambiguous match (`len > 1`)**: Rejects claim and logs `synthesis.citation_mapper.citation_ambiguous_fallback`.
   - **No match (`len == 0`)**: Rejects claim and logs `synthesis.citation_mapper.fabrication_detected`.

---

## 4. Telemetry & Observability

`CitationMapper` exposes key operational metrics:
- **`total_citations`**: Total cited evidence references processed.
- **`matched_by_id_count`**: Count of citations resolved via UUID.
- **`matched_by_text_fallback_count`**: Count of citations resolved via text matching.
- **`citation_missing_id_count`**: Count of citations where the LLM omitted a valid UUID.
- **`citation_ambiguous_fallback_count`**: Count of fallback attempts rejected due to multiple matching text candidates.
- **`citation_fallback_rate`**: $\frac{\text{matched\_by\_text\_fallback\_count}}{\text{total\_citations}}$

---

## 5. Backward Compatibility & Future Removal Criteria

- **Additive & Non-Breaking**: Older traces, legacy API clients, or model responses omitting `evidence_id` continue to function seamlessly via the text-fallback path.
- **Future Removal Criteria**: The text-matching fallback path is retained until operational telemetry confirms `citation_fallback_rate` remains consistently near zero over extensive production usage.
