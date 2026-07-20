# Synthesis + Critic Architecture — Single-Pass Pipeline

This document outlines the architectural decisions and flow for the Synthesis and Critic agents in GaiaOS.

## 1. Pipeline Overview

Milestone 7 implements the convergence stage of the GaiaOS agent orchestration pipeline:

```
[ Domain Agents (M4-M6) ]
          │
          ▼  (AgentOutput[])
 [ Synthesis Agent ] ◄─────── [ CitationMapper (Integrity Guard) ]
          │
          ▼  (SynthesisOutput)
  [ Critic Agent ] ◄───────── [ Non-blocking verification pass ]
          │
          ▼  (CriticFlag[])
[ Investigation Complete ] ──► Update database status & trace
```

---

## 2. Synthesis and Citation Integrity

### 2.1 The Synthesis Stage
The Synthesis Agent compiles claims from all executed domain agents. It:
1. Merges domain findings.
2. Identifies and surfaces evidence gaps (domains that returned no evidence or errors) explicitly, rather than masking them.
3. Calculates confidence for each claim as the average of the cited evidence confidences.
4. Structurally rejects any hallucinated claims by validating citations.

### 2.2 CitationMapper Constraint
The `CitationMapper` is an in-memory structural filter. It does not rely on LLM prompts to prevent hallucination; instead, it compares the LLM's cited `supporting_evidence` list against the actual pool of evidence returned by the domain agents:
- If a cited evidence item matches a gathered evidence entry, the mapper swaps in the exact gathered `Evidence` object, preserving all rich metadata (`document_id`, `chunk_id`, `title`, `source_url`, `extra_metadata`).
- If any citation is fabricated, the mapper flags the claim as invalid, and the Synthesis Agent **completely discards** that claim from the final report.

### 2.3 Zero-Evidence Safeguard
If the domain agents gathered zero evidence (due to external API failures or an empty corpus), the Synthesis Agent returns a hardcoded claim: `"Unable to gather sufficient evidence to answer the query."` with `confidence = 0.0`.

---

## 3. Critic Pass: "Single-Pass, No Replan" Scope Boundary

### 3.1 Non-Blocking Verification
The Critic Agent runs exactly once over the synthesized answer. It:
- Annotates claims with warnings or observations (`CriticFlag`).
- Does not trigger another LLM planning cycle or loop.
- Never block completing the investigation.

### 3.2 Fails-Open Design Choice
If the Critic Agent fails (e.g. LLM rate limits, network timeout), the pipeline logs a warning, sets `critic_flags = []`, and completes the investigation normally. 

This design choice differs from the fail-closed choice made for database checkpointers, as verification degrades confidence reporting but does not prevent the delivery of gathered facts.

### 3.3 Neo4j and Future Extensibility (v1.1 / Phase 3)
As per Section 3.10 of the Frozen Architecture:
- Recursive replanning loops are deferred to Phase 3 (v1.1+).
- The `CriticFlag` structure is designed to support wrapping this exact `synthesize -> verify` pass in an outer replan loop when scale demands it, without altering public interfaces.
