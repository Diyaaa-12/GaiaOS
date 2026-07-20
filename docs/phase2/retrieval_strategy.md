# Literature Agent — Hybrid Retrieval Strategy

This document describes the architectural retrieval strategy implemented in Phase 2, Milestone 5 for the `LiteratureAgent`.

## 1. Database Indexing Scheme

Retrieval is backed by the `literature_chunks` table in PostgreSQL, utilizing two distinct index types for hybrid search:

### 1.1 Vector Similarity Index (HNSW)
We use a Hierarchical Navigable Small World (HNSW) index for vector distance queries.
- **Index Definition:**
  ```sql
  CREATE INDEX ix_literature_chunks_embedding ON literature_chunks
      USING hnsw (embedding vector_cosine_ops);
  ```
- **Rationale:** Compared to `IVFFlat`, HNSW does not require a representative training corpus before index construction. It builds incrementally and dynamically without accuracy degradation, which is essential for a planetary risk corpus that grows over time.
- **Distance Metric:** Cosine distance (`vector_cosine_ops`), which evaluates the angle between vectors rather than magnitude, matching standard embedding model behaviors.

### 1.2 Full-Text Keyword Index (GIN)
We use a Generalized Inverted Index (GIN) on a computed `tsvector` column representing the chunk text contents.
- **Index Definition:**
  ```sql
  CREATE INDEX ix_literature_chunks_fts ON literature_chunks USING GIN (ts_content);
  ```
- **Rationale:** Provides high-throughput, classical keyword matching (BM25 equivalents) to catch exact terminology, hazard names, and specific numeric metrics that dense vectors might hallucinate or smooth over.

---

## 2. Reciprocal Rank Fusion (RRF) Algorithm

To merge dense vector ANN results and sparse keyword FTS results, the system employs **Reciprocal Rank Fusion** (Cormack et al., 2009).

### 2.1 The Formula
For each document $d$ in the union of vector search results $V$ and full-text search results $F$:

$$RRF\_Score(d) = \sum_{m \in \{V, F\}} \frac{1}{k_{rrf} + r_m(d)}$$

Where:
- $r_m(d)$ is the rank (1-indexed position) of document $d$ in system $m$. If the document is not returned by a system, its term evaluates to $0$.
- $k_{rrf}$ is the rank constant, set to **`60`** (the standard baseline established by IR literature).

This deterministic combination ensures that documents appearing near the top of both lists receive highly boosted ranks, while avoiding undocumented heuristic weights or magic weights.

---

## 3. Confidence Normalization

Confidence values exposed as `Evidence.confidence` are strictly normalized to a `[0, 1]` range to maintain consistency across all domain agents.

### 3.1 Normalization Formula
The maximum possible RRF score occurs when a document is ranked #1 in both retrieval systems (rank $1$ in vector, rank $1$ in FTS):

$$Score_{max} = \frac{1}{60 + 1} + \frac{1}{60 + 1} = \frac{2}{61} \approx 0.0327868$$

Each document's normalized confidence score is:

$$Confidence(d) = \frac{RRF\_Score(d)}{Score_{max}} = \frac{RRF\_Score(d)}{\frac{2}{61}}$$

This yields a confidence of $1.0$ for the highest-ranking intersection, $0.5$ for rank #1 in only one list, and scales down smoothly to $0.0$ for low-ranked single-list matches.

---

## 4. Preservation of Citation Metadata

Each `Evidence` object produced by the Literature Agent retains its source traceability through four explicit metadata attributes:
- `document_id`: The database identifier for the document source.
- `chunk_id`: The index of the specific text chunk within the document.
- `title`: The title of the paper or report.
- `source_url`: The URL to access the source paper.
