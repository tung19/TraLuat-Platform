# legalbenchrag — Deep Read (retrieval-eval harness + chunking architecture)

Source: `refs/legalbenchrag/` (ZeroEntropy, arXiv:2408.10343). Read-only extraction.
Purpose for TraLuat: reference for **L4 (chunking/indexing)**, **L5 (retrieval)**, **L13 (benchmark-as-CI-gate)**.

**Verdict up front:** This repo is small (~2,500 LOC Python), contract/English-centric, and effectively
dormant, but its *core idea is exactly what TraLuat needs*: ground truth expressed as **exact character
spans** in source documents, and **character-level precision/recall** computed deterministically from
overlap of retrieved spans vs. ground-truth spans. The span-preserving chunker and the metric code are
directly portable. The chunkers themselves (blind character splitting) are what we must replace with
clause-aware boundaries.

---

## 1. Directory map + benchmark data model

### Directory map
```
refs/legalbenchrag/
  README.md                         # usage, data download link, citation
  requirements.txt / .in            # deps: langchain-text-splitters, sqlite-vec, openai, cohere, voyageai, anthropic, pydantic, pandas, tqdm, diskcache, tiktoken
  credentials/credentials.example.toml   # [ai] openai/anthropic/cohere/voyageai keys
  legalbenchrag/
    benchmark.py                    # ENTRY: load benchmarks, build corpus, loop strategies, write CSV
    benchmark_types.py              # DATA MODEL: Snippet, QAGroundTruth, Benchmark, RetrievalMethod ABC, span merge
    run_benchmark.py                # harness: ingest -> sync -> query all -> QAResult; precision/recall computed here
    methods/
      baseline.py                   # CHUNKERS (naive, rcts) + sqlite-vec vector store + query/rerank pipeline
      retrieval_strategies.py       # SWEEP: cartesian product chunk x size x rerank x top_k
    utils/
      ai.py                         # embedding/rerank/LLM wrappers, rate-limit, diskcache (619 LOC)
      credentials.py                # tomllib -> pydantic SecretStr
    generate/                       # ground-truth GENERATION from source datasets (CUAD, MAUD, ContractNLI, PrivacyQA)
      generate_cuad.py, generate_maud.py, generate_contractnli.py, generate_privacy_qa.py
      utils.py                      # download_zip + LLM create_title
      __main__.py                   # `python ./legalbenchrag/generate`
  # (data/ is NOT in repo; downloaded separately: data/corpus/*.txt, data/benchmarks/*.json, data/cache/)
```

Runtime layout expected (not committed):
- `./data/corpus/<path>.txt` — raw plain-text source documents.
- `./data/benchmarks/{privacy_qa,contractnli,maud,cuad}.json` — serialized `Benchmark`.
- `./data/cache/ai_cache.db` (diskcache), `./data/cache/baseline.db` (sqlite-vec), `./benchmark_results/<ts>/`.

### Ground-truth data model — character spans
File: `refs/legalbenchrag/legalbenchrag/benchmark_types.py`

A ground-truth unit is a **query + list of exact character spans into named corpus files**:

```python
class Snippet(BaseModel):
    file_path: str
    span: tuple[int, int]          # (start_char, end_char) half-open into the file's text

    @computed_field
    @property
    def answer(self) -> str:
        with open(f"./data/corpus/{self.file_path}") as f:
            return f.read()[self.span[0] : self.span[1]]   # span resolves to exact substring

class QAGroundTruth(BaseModel):
    query: str
    snippets: list[Snippet]
    tags: list[str] = []           # e.g. ["cuad"]; used for per-benchmark breakdown
    # validator ensures snippets within one file are DISJOINT (non-overlapping)

class Benchmark(BaseModel):
    tests: list[QAGroundTruth]
```

Key invariant (`validate_snippet_list`, lines 35-49): within a file, ground-truth spans must be
**sorted and strictly disjoint** — `snippets[i-1].span[1] >= snippets[i].span[0]` raises
`"Spans are not disjoint!"`. This is what makes character-level recall/precision well-defined (no
double-counting overlap).

Span-merge helper (lines 9-21), used during generation to coalesce nearby quote spans:
```python
def sort_and_merge_spans(spans, *, max_bridge_gap_len=0):
    # sorts by start; merges span B into A if B.start <= A.end + max_bridge_gap_len
```

Retrieval-side mirror types:
```python
class Document(BaseModel):   file_path: str; content: str
class RetrievedSnippet(Snippet):  score: float          # Snippet + relevance score
class QueryResponse(BaseModel):   retrieved_snippets: list[RetrievedSnippet]
```

The retrieval contract is a 4-method ABC (`RetrievalMethod`, lines 88-107):
`ingest_document(doc)`, `sync_all_documents()`, `query(str) -> QueryResponse`, `cleanup()`.
**This ABC is the pluggability seam** — any retriever implementing it can be benchmarked.

### How ground truth is generated (span anchoring)
File: `refs/legalbenchrag/legalbenchrag/generate/generate_cuad.py` (representative)

The generators take human-annotated *verbatim quotes* from the source datasets and locate them in the
corpus text by exact string search — `extract_quote_span` (lines 34-45):
```python
def extract_quote_span(text, quote):
    start_idx = text.find(quote)
    if start_idx == -1:            return None   # quote not found -> drop
    if text.find(quote, start_idx+len(quote)) != -1: return None  # ambiguous (>1 match) -> drop
    return start_idx, start_idx + len(quote)
```
So a GT span is only kept when the quote appears **exactly once**. Multiple quotes per query are merged
via `sort_and_merge_spans(spans, max_bridge_gap_len=1)` (line 169). A query string is synthesized
(`f"Consider the {generated_title}; {column_query}"`) and the LLM-generated contract title comes from
`generate/utils.py::create_title` (gpt-4o-mini). This "find exact substring, require uniqueness, merge"
pattern is the blueprint for building a Vietnamese GT set from quoted article text.

---

## 2. The chunkers — span-preserving reconstruction (CRITICAL for TraLuat)

File: `refs/legalbenchrag/legalbenchrag/methods/baseline.py`, method `sync_all_documents` (lines 80-191).

Two strategies, selected by `ChunkingStrategy.strategy_name` ∈ `{"naive","rcts"}` (lines 34-37):

**naive** (lines 92-95) — fixed-width character windows:
```python
for i in range(0, len(document.content), chunk_size):
    text_splits.append(document.content[i : i + chunk_size])
```

**rcts** — LangChain `RecursiveCharacterTextSplitter` with legal-ish separator ladder (lines 96-116):
```python
RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", "!", "?", ".", ":", ";", ",", " ", ""],
    chunk_size=chunk_size, chunk_overlap=0,
    length_function=len, is_separator_regex=False,
    strip_whitespace=False,      # <-- crucial: do NOT strip, so concatenation is lossless
)
```

### The span-preservation mechanism (the part TraLuat should copy)
Two assertions guarantee **lossless, gap-free, overlap-free** coverage of the document (lines 117-120):
```python
assert sum(len(ts) for ts in text_splits) == len(document.content)
assert "".join(text_splits) == document.content     # exact reconstruction
```
Then spans are assigned by **walking a running offset** — each chunk's span starts where the previous
ended (lines 122-134):
```python
prev_span = None
for text_split in text_splits:
    prev_index = prev_span[1] if prev_span is not None else 0
    span = (prev_index, prev_index + len(text_split))
    chunks.append(Chunk(document_id=document_id, span=span, content=text_split))
    prev_span = span
```
Because splits are a lossless partition and `chunk_overlap=0` + `strip_whitespace=False`, every character
index of the source maps to exactly one chunk, and `chunk.content == document.content[span[0]:span[1]]`.
That is what lets retrieved chunk spans be compared against GT character spans with no coordinate drift.

For TraLuat this is the key lesson: **whatever boundary logic you use, keep chunks as a lossless
offset-tracked partition of the exact source text** so a citation can anchor to `(file, start, end)` and
resolve back to verbatim article text.

---

## 3. Retrieval pipeline — embedding / vector store / rerank (pluggable)

File: `refs/legalbenchrag/legalbenchrag/methods/baseline.py` (`BaselineRetrievalMethod`).

Pipeline = **ingest (collect docs) → sync (chunk + embed + index) → query (embed → ANN → rerank → token-trim)**.

**Embedding** — OpenAI `text-embedding-3-large` (set in strategies). Batched (`EMBEDDING_BATCH_SIZE=2048`),
with DOCUMENT vs QUERY input-type distinction (`AIEmbeddingType`). Call via `ai_embedding(...)`
(lines 148-155, 197-201).

**Vector store** — **sqlite-vec** (local, file-backed), lines 158-181:
```python
self.sqlite_db = sqlite3.connect("./data/cache/baseline.db")
sqlite_vec.load(self.sqlite_db)
self.sqlite_db.execute("PRAGMA mmap_size = 3GB")
self.sqlite_db.execute(f"CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[{dim}])")
db.executemany("INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)", insert_data)
```
Vectors serialized to raw bytes via `serialize_f32` (`struct.pack(f"{len(v)}f", *v)`, lines 26-28).
`rowid` indexes into a parallel Python list `embedding_infos: list[EmbeddingInfo]` where
`EmbeddingInfo = {document_id, span}` — i.e. the vector store holds only vectors; the **span metadata
lives alongside by rowid** (lines 48-51, 182-189).

**ANN query** — cosine/L2 top-k via sqlite-vec `MATCH` (lines 202-215):
```sql
SELECT rowid, distance FROM vec_items
WHERE embedding MATCH ? ORDER BY distance ASC LIMIT ?
```
`LIMIT = embedding_topk` (300 when reranking is on, else top_k — see §5).

**Rerank** — optional Cohere `rerank-english-v3.0` (lines 218-230):
```python
if rerank_model is not None:
    reranked_indices = await ai_rerank(model, query, texts=[chunk_text ...])
    retrieved = [retrieved[i] for i in reranked_indices[:rerank_topk]]
```
Reranker is fed the reconstructed chunk text (`get_embedding_info_text` = `content[span0:span1]`).

**Token-limit trim** (lines 232-250) — optional `token_limit` truncates the *last* span so cumulative
retrieved length stays under budget; score assigned as `1.0/(i+1)` (rank-reciprocal).

### Pluggability
- `utils/ai.py` (619 LOC) is a **provider-abstraction layer**: `AIEmbeddingModel`/`AIRerankModel`/`AIModel`
  are pydantic models with `company` ∈ {openai, cohere, voyageai, anthropic}; each of `ai_embedding`,
  `ai_rerank`, `ai_call` `match`es on `company`. Adding a provider = add a case. Per-provider rate limits
  (tpm/rpm/batch) are declared as computed fields; a global `diskcache` (`./data/cache/ai_cache.db`)
  caches every embedding/rerank/LLM call by content hash (lines 120-122, 371-398, 535-547) — so re-running
  the benchmark is cheap/deterministic. Keyed by `md5(text)` + model + type.
- `RetrievalMethod` ABC (benchmark_types.py) is the swap point for an entirely different retriever
  (e.g. TraLuat's structural index) without touching the harness.

Credentials: `utils/credentials.py` loads `./credentials/credentials.toml` into pydantic `SecretStr`.

---

## 4. Metrics — character-level Precision@k / Recall@k

File: `refs/legalbenchrag/legalbenchrag/run_benchmark.py`, class `QAResult` (lines 16-54).

Metrics are **fraction of characters**, computed from span-overlap between retrieved snippets and GT
snippets (same file). Overlap of two spans = `max(0, min(ends) - max(starts))`.

**Precision** = (retrieved chars that are relevant) / (total retrieved chars) — lines 21-36:
```python
@property
def precision(self) -> float:
    total_retrieved_len = 0
    relevant_retrieved_len = 0
    for snippet in self.retrieved_snippets:
        total_retrieved_len += snippet.span[1] - snippet.span[0]
        for gt_snippet in self.qa_gt.snippets:              # GT spans guaranteed disjoint
            if snippet.file_path == gt_snippet.file_path:
                common_min = max(snippet.span[0], gt_snippet.span[0])
                common_max = min(snippet.span[1], gt_snippet.span[1])
                if common_max > common_min:
                    relevant_retrieved_len += common_max - common_min
    if total_retrieved_len == 0: return 0
    return relevant_retrieved_len / total_retrieved_len
```

**Recall** = (relevant chars retrieved) / (total relevant GT chars) — lines 38-54, symmetric:
```python
@property
def recall(self) -> float:
    total_relevant_len = 0
    relevant_retrieved_len = 0
    for gt_snippet in self.qa_gt.snippets:
        total_relevant_len += gt_snippet.span[1] - gt_snippet.span[0]
        for snippet in self.retrieved_snippets:
            if snippet.file_path == gt_snippet.file_path:
                common_min = max(snippet.span[0], gt_snippet.span[0])
                common_max = min(snippet.span[1], gt_snippet.span[1])
                if common_max > common_min:
                    relevant_retrieved_len += common_max - common_min
    if total_relevant_len == 0: return 0
    return relevant_retrieved_len / total_relevant_len
```

Notes:
- This is **character-level**, not chunk-level or doc-level — overlap measured in characters, so partial
  chunk hits count proportionally. "@k" is implicit: k is baked into how many snippets `query()` returns
  (via top_k / rerank_topk / token_limit). The metric itself just consumes whatever snippet list it gets.
- GT disjointness (enforced in benchmark_types) means precision's double loop can't double-count.
  Retrieved snippets are NOT required disjoint (validator commented out, benchmark_types.py line 84) —
  overlapping retrieved spans could inflate `total_retrieved_len`; something to watch if adapting.

**Aggregation** — `BenchmarkResult` (lines 63-107): weighted averages across tests, filterable by tag:
```python
def get_avg_recall_and_precision(self, tag_filter=None):
    # select qa_results whose qa_gt.tags contains tag_filter (or all)
    # weighted mean: sum(metric * weight/avg_weight)/n
```
`avg_precision` / `avg_recall` are computed properties; `benchmark.py` also calls
`get_avg_recall_and_precision(benchmark_name)` per dataset for a breakdown.

**Harness loop** — `run_benchmark` (lines 110-139): ingest all docs → `sync_all_documents()` →
`asyncio.gather` all queries → build `QAResult` list → `cleanup()`. Pure, deterministic given the cache.

---

## 5. Strategy sweep (chunk × size × rerank × top_k)

File: `refs/legalbenchrag/legalbenchrag/methods/retrieval_strategies.py` (whole file, 35 LOC).

A nested cartesian product builds a flat `RETRIEVAL_STRATEGIES: list[RetrievalStrategy]`:
```python
chunk_strategy_names = ["naive", "rcts"]
rerank_models = [None, AIRerankModel(company="cohere", model="rerank-english-v3.0")]
chunk_sizes = [500]
top_ks = [1, 2, 4, 8, 16, 32, 64]

for chunk_strategy_name in chunk_strategy_names:
  for chunk_size in chunk_sizes:
    for rerank_model in rerank_models:
      for top_k in top_ks:
        RETRIEVAL_STRATEGIES.append(RetrievalStrategy(
            chunking_strategy=ChunkingStrategy(strategy_name=..., chunk_size=...),
            embedding_model=AIEmbeddingModel(company="openai", model="text-embedding-3-large"),
            embedding_topk = 300 if rerank_model is not None else top_k,   # retrieve wide then rerank
            rerank_model=rerank_model,
            rerank_topk=top_k,
            token_limit=None,
        ))
```
= 2 × 1 × 2 × 7 = **28 strategies**. Note the pattern: when reranking, ANN retrieves a wide net
(`embedding_topk=300`) and the reranker narrows to `rerank_topk=top_k`; without rerank, ANN directly
returns `top_k`.

**Runner** — `benchmark.py` (lines 90-136): for each strategy, instantiate `BaselineRetrievalMethod`,
run `run_benchmark`, dump `{i}_results.json`, and append a row to a pandas DataFrame with columns
`[i, chunk_strategy_name, chunk_size, top_k, rerank_model, top_k_rerank, token_limit, recall, precision,
<bench>|recall, <bench>|precision ...]` → `results.csv` (lines 111-136). Results saved under
`./benchmark_results/<timestamp>/`.

**Test sampling** (benchmark.py lines 13-64): 4 datasets weighted 0.25 each; `MAX_TESTS_PER_BENCHMARK=194`
cap; `SORT_BY_DOCUMENT=True` groups tests onto fewest documents to cut ingestion cost (at the stated
expense of p-value validity). Weights normalized per dataset so each contributes equally.

There is **no CI wiring in the repo** (no GitHub Actions, no pass/fail threshold, no pytest gate). It
produces a CSV; turning it into a CI gate (L13) is left to the consumer — the raw material (deterministic
scores, cached calls, per-tag breakdown) is all there.

---

## 6. Concrete plan for TraLuat

### Reuse almost verbatim
1. **Data model** (`benchmark_types.py`): `Snippet{file_path, span}`, `QAGroundTruth{query, snippets, tags}`,
   `Benchmark{tests}`, the disjointness validator, and `sort_and_merge_spans`. This is the citation-anchor
   contract TraLuat already wants: `(document, start_char, end_char)` → verbatim article text.
2. **Character-level metrics** (`run_benchmark.py` `QAResult.precision`/`recall`, `BenchmarkResult`
   weighted/tag-filtered aggregation). Portable as-is; they are pure span arithmetic, language-agnostic.
3. **`RetrievalMethod` ABC** as the retriever seam, and the **sweep pattern** (`retrieval_strategies.py` +
   the `benchmark.py` loop → DataFrame/CSV). Keep the "retrieve wide, rerank narrow" `embedding_topk=300`
   idiom.
4. **The span-preservation discipline** from the chunker: lossless partition + running-offset span
   assignment + the two reconstruction assertions (`"".join(splits)==content`). Keep these as regression
   guards even after swapping the boundary logic.
5. **diskcache content-hash caching** of embeddings/reranks so the benchmark is cheap and deterministic in
   CI.

### Adapt / replace
1. **Chunk boundaries → clause-aware (structural), not blind characters.** Replace `naive`/`rcts` with a
   splitter that cuts on Vietnamese legal structural units (Điều / Khoản / Điểm; Chương / Mục) — but keep
   the output a *lossless offset-tracked partition* so metrics and citations still work. Add the structural
   unit id (e.g. `Điều 12 khoản 2`) to chunk metadata alongside `span`. RCTS can remain a fallback baseline
   in the sweep for comparison.
2. **Vietnamese throughout:** embedding model must handle Vietnamese (text-embedding-3-large is
   multilingual but evaluate vs. a VN-tuned model; add as another `company`/`model` in the sweep).
   Reranker: Cohere multilingual rerank or a VN model. The separator ladder in RCTS should include VN
   sentence punctuation. Query synthesis and GT quote-matching (`extract_quote_span`) work on VN text
   unchanged (exact substring + uniqueness), but beware Unicode normalization (NFC) — normalize corpus and
   quotes identically before `.find()`.
3. **Effectivity-filtered retrieval eval (new axis, not in legalbenchrag).** legalbenchrag has no notion of
   temporal validity — a document is just text. TraLuat must evaluate retrieval *as of a date*: GT spans
   should carry effectivity, and the harness should score whether the retriever returns the version in
   force (and suppresses superseded/repealed text). Extend `Snippet`/`QAGroundTruth` with effectivity
   metadata and add a date to the query context.
4. **3-axis benchmark (TraLuat-specific), generalizing the single precision/recall pair:**
   - *correct-article*: current char-level precision/recall (reuse directly).
   - *correct-effectivity*: did the retrieved span belong to the version in force at query date?
     (new metric, needs effectivity metadata on spans).
   - *catch-omission* (recall of must-cite clauses): did we retrieve every GT clause required to answer,
     i.e. no silent omission — essentially recall thresholded per required clause rather than per character.
   Keep the per-tag aggregation machinery (`tags` + `get_avg_recall_and_precision(tag)`) to report each axis.
5. **Wire the CI gate (L13), which the repo lacks.** Add pass/fail thresholds on the aggregated metrics
   (e.g. recall ≥ X, effectivity-accuracy ≥ Y) and fail the build below them; persist `results.csv` as a CI
   artifact and diff against a baseline to catch regressions. The deterministic cache makes this feasible in
   CI.

### Caveats about the reference
- **Contract/English-centric**: datasets are CUAD/MAUD/ContractNLI/PrivacyQA (US commercial contracts &
  privacy policies), not statutes/regulations; no hierarchical legal numbering, no amendment/effectivity
  model. TraLuat's statutory domain is structurally richer.
- **Dormant / thin**: ~2,500 LOC, no tests, no CI, `data/` not included (Dropbox download), single baseline
  retriever. Fine as a *harness skeleton*; not a maintained framework to depend on.
- **Vector store is local sqlite-vec** — great for a reproducible eval harness (file-backed, no server),
  but it is the eval index, not necessarily TraLuat's production store.
- Retrieved spans aren't validated disjoint, so a retriever returning overlapping spans can distort
  precision denominators — add the disjointness/merge step on retrieved spans if adapting.

### Minimal port shape for TraLuat eval harness
`benchmark_types` (data model + spans) + `run_benchmark` (metrics/aggregation) copied; implement a
`RetrievalMethod` subclass wrapping TraLuat's retriever; replace the chunker with a clause-aware
span-preserving splitter; extend the sweep config with VN models + effectivity axis; add threshold-based
CI assertions around the produced metrics.
