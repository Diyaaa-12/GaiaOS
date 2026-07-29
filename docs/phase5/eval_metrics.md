# Evaluation Metrics — Phase 5 Reference

**Milestone:** M1 — Real Confidence Calibration & Retrieval Precision  
**Status:** Implemented  
**Files:** `eval/metrics/calibration.py`, `eval/metrics/retrieval_precision.py`,
`eval/metrics/relevance_judgments.py`

---

## Expected Calibration Error (ECE)

### Formula

```
ECE = Σ_b (|B_b| / n) × |accuracy(B_b) − confidence(B_b)|
```

- **B_b** — set of predictions whose stated confidence falls in bin *b*
- **accuracy(B_b)** — fraction of correct predictions in bin *b*
- **confidence(B_b)** — mean stated confidence in bin *b*
- **n** — total number of predictions in the suite run
- **bins** — 10 equal-width bins over [0.0, 1.0] (ADR-501)

### Why ECE, not Brier Score or log-loss

See **ADR-501** in `docs/Roadmap_Phase5.md`. Short version: ECE is directly
interpretable ("our stated confidence is off by X on average") and bin-visualisable
without transformation, which matters for M8's future dashboard work.

### What ECE measures

A low ECE means the system's stated confidence tracks real accuracy: when the
system says "70 % confident," it is correct roughly 70 % of the time.  ECE = 0.0
is perfect calibration; ECE = 1.0 is maximal miscalibration.

### Important: ECE is a population statistic

`calculate_calibration(predictions, n_bins=10)` must be called **once per suite
run** with all `(confidence, is_correct)` pairs collected across all questions —
not once per question.  Calling it per-question and averaging the results is
**not** equivalent to population ECE.

The runner handles this via `score_suite()` in `scorer.py`, which accumulates
pairs from all per-question metrics and computes ECE at suite-completion time.

### Return value and caller contract

`calculate_calibration` always returns a `float` and raises `ValueError` if
called with an empty list.  The empty-input decision ("no scorable predictions
→ ECE is undefined") is the **caller's responsibility**, not the metric
function's.  In `scorer.score_suite`:

```python
if calibration_pairs:
    ece = calculate_calibration(calibration_pairs)
    calibration_status = "computed"
else:
    ece = None
    calibration_status = "insufficient_data"
```

This keeps `eval/metrics/` as pure math and `eval/harness/scorer.py` as the
home for business-logic decisions about missing data.

---

## Retrieval Precision

### Formula

```
precision = |retrieved ∩ relevant| / |retrieved|
```

### What it measures

The fraction of evidence chunks returned by the literature agent that were judged
relevant to the question.  A precision of 1.0 means every retrieved chunk was
relevant; 0.0 means nothing returned was relevant.

### Chunk IDs vs Evidence IDs

Retrieval precision uses **`Evidence.chunk_id`** — the stable literature database
identifier — **not** `Evidence.id` (a per-run `uuid4()` that changes every time
the same chunk is retrieved).  Only `chunk_id` is stable across runs and therefore
usable in hand-curated relevance judgments.

### Return value

Returns `float` in `[0.0, 1.0]`.

- Empty `retrieved_chunk_ids` → `0.0` (early exit; scorer marks
  `"no_evidence_retrieved"`, does not call this function).
- Empty `relevant_chunk_ids` → `0.0` (intersection always empty).

---

## Relevance Judgments

### Location

`eval/metrics/relevance_judgments.py` — `RELEVANCE_JUDGMENTS: dict[UUID, RelevanceJudgment]`

### Current coverage

`RELEVANCE_JUDGMENTS` starts **empty**.  No entries are committed until real
`chunk_id` values have been retrieved from the live `literature_chunks` table
and verified against a reference answer.  Fabricated chunk IDs are not
acceptable — they produce misleading precision scores.

The two literature-domain benchmark questions (`literature_pm25_climate`,
`literature_fault_mechanics`) are the natural first candidates once the
literature database is populated.

### Curation process

When a new benchmark question is added to `eval/benchmarks/questions.json`:

1. Run a retrieval query against the live literature database for the question text.
2. Inspect the returned `Evidence.chunk_id` values from the literature agent.
3. Identify which chunk IDs genuinely support the reference answer
   (not just topically adjacent).
4. Add those IDs to `RELEVANCE_JUDGMENTS` in `relevance_judgments.py`:

```python
_my_id = _question_id("my_new_question_id")
RELEVANCE_JUDGMENTS[_my_id] = RelevanceJudgment(
    question_id=_my_id,
    relevant_chunk_ids=frozenset({
        "chunk_id_1",
        "chunk_id_2",
    }),
)
```

5. Record the curation date and any caveats in a comment.
6. Add at least one unit test in `tests/test_eval_metrics.py` exercising the new judgment.

> **Content burden acknowledged:** Relevance judgment curation is an ongoing
> responsibility — not a one-time task.  When new literature is ingested and chunk
> IDs change, existing judgments must be reviewed and updated.  This is named as
> accepted technical debt in the Milestone 1 design (§32–33).

---

## Where metrics are stored

No schema change was made.  All metrics live in the existing `EvalBenchmarkRun.metrics`
JSONB column, structured as:

```json
{
  "status": "scored",
  "confidence": null,
  "is_correct": null,
  "retrieval_precision": null,
  "retrieval_precision_status": "no_evidence_retrieved",
  "suite": {
    "ece": null,
    "ece_n_predictions": 0,
    "calibration_status": "insufficient_data",
    "mean_retrieval_precision": null,
    "precision_n_questions": 0,
    "precision_status": "insufficient_data"
  }
}
```

`null` values in `confidence`, `is_correct`, and `retrieval_precision` reflect the
stub runner still being in use.  They will be replaced with real values when the
orchestrator is wired into the eval runner in a later milestone.

---

## Future wiring (later milestones)

| Milestone | What changes |
|---|---|
| Real runner integration | `run_stub_benchmark` replaced; `run_result` carries `"confidence"` and `"evidence"` with real `chunk_id` values |
| Correctness methodology | `run_result["is_correct"]` populated; calibration pairs become non-empty; ECE becomes non-null |
| M8 SLO layer | `eval.calibration.ece` and `eval.retrieval.precision` wired into dashboard trend metrics |
| Full judgment coverage | All 18 benchmark questions gain relevance judgments |
