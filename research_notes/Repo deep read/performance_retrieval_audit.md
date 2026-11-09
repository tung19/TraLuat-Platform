# Retrieval / Compute Performance Audit — Reference Repos → TraLuat

Scope: the **speed mechanisms** behind retrieval in the refs, read for what transfers to
TraLuat (Postgres + pgvector + FTS, bge-m3 local embeddings, bge-reranker-v2-m3 local,
effectivity+tenant `WHERE` predicate). Six axes: (1) ANN/vector index config, (2) prefilter/
narrowing, (3) wide-then-narrow rerank budgets, (4) bounded graph traversal, (5) embedding/LLM
batching & concurrency, (6) precomputation. Every claim is file+line cited. **Honesty lens: most
of these repos are research prototypes and several are performance-naive (brute-force cosine,
O(N²) build, per-query full-corpus refetch). Those are warnings, not templates.**

Companion to `retrieval_mechanisms_audit.md` (quality lens) and `pipeline_storage_audit.md`
(storage lens) — this file is the *compute cost* lens only.

Headline: **The repos give TraLuat the wide-then-narrow rerank budget (legalbenchrag/PAKTON),
the cheap-prefilter-before-expensive discipline (eyecite Aho-Corasick), the batch+rate-limit
embedding client (legalbenchrag `ai.py`), and the build-once/query-many precompute split
(LegalGraphRAG, LeSICiN). They do NOT give TraLuat: an ANN index-type decision for pgvector
(every vector store here is either brute-force or hides the index behind a wrapper), a
bounded-hop guard as a reusable parameter (LegalGraphRAG's bounds are hardcoded structure, not a
guard; LeSICiN's are fixed sampling constants), or a metadata-prefilter inside the vector query
(six of seven do fully global search). Those are net-new.**

---

## 1. ANN / vector index configuration

### legalbenchrag — sqlite-vec `vec0`: BRUTE-FORCE (linear scan), not indexed
`legalbenchrag/legalbenchrag/methods/baseline.py`
- Table creation, L170: `CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[{dim}])`.
  A plain `vec0` virtual table with only an `embedding` column and **no partition/ANN index** —
  sqlite-vec `vec0` executes a **brute-force full-scan KNN**, not HNSW/IVF. There is no `ef`,
  no `M`, no probe/list parameter anywhere.
- Query, L202-213: `SELECT rowid, distance FROM vec_items WHERE embedding MATCH ? ORDER BY
  distance ASC LIMIT ?` — exact KNN over all rows every query. Deterministic and exact, O(N·dim)
  per query. Fine at benchmark corpus sizes; does not scale to a national legal corpus.
- The only "perf" tuning is RAM: L168 `PRAGMA mmap_size = 3*1024*1024*1024` (3 GB mmap).
- Embedding dim is inferred from the vector (`float[{len(embeddings[0])}]`, L170) — 3072 for
  `text-embedding-3-large`.

### PAKTON — Pinecone **or** Chroma via LangChain; index type is HIDDEN behind the wrapper
`PAKTON/.../Archivist/src/Archivist/indexers/vectordb.py` (writer),
`PAKTON/.../Researcher/src/Researcher/retrievers/vectordb.py` (reader)
- Chroma path: `Chroma(collection_name, embedding_function, client_settings,
  collection_metadata=collection_metadata)` (indexer L96-101; retriever L123-128). Chroma's
  engine is **hnswlib HNSW** internally, but PAKTON never sets `M`/`ef_construction`/`ef_search`
  explicitly — they ride as opaque `collection_metadata` from `config.yaml` (indexer L89,
  retriever L116). No HNSW params are set in code.
- Pinecone path: `PineconeVectorStore(index_name, embedding)` (retriever L100-103) — ANN is fully
  managed server-side; TraLuat gets zero index knowledge from this (and it is a cloud/residency
  risk anyway).
- Query is `similarity_search_with_relevance_scores(query, k=top_k)` (retriever L164) — no index
  tuning, no probe count.
- **Warning (anti-pattern):** `fetch_all_documents()` for the Pinecone hybrid path does
  `self.invoke(" ", k=10000)` (retriever L200) — pulls up to 10k docs to rebuild BM25 per query
  (see §2/§3). That is an O(corpus) per-query cost.

### LegalGraphRAG — numpy/scipy BRUTE-FORCE cosine, O(N) per query AND O(N²) at build
`LegalGraphRAG/core/graph_construct/graph_db.py`
- `find_similar_nodes` L145-174: Python `for` loop over every stored vector calling
  `cosine_similarity` (L159-161) which is `scipy.spatial.distance.cosine` on one pair at a time
  (L134-143). This is **not even vectorized numpy** — a per-element Python loop with a scipy call
  per node. O(N) per query with a large constant. `top_k=5` default (L145).
- `_update_vector_index` L51-67 rebuilds the **entire** `np.array(vectors)` for a node type on
  **every** `add_node` (L80) and `update_node` (L97) → O(N) rebuild per insert → **O(N²) ingest**.
  Severe build-time anti-pattern.
- No HNSW/IVF anywhere; the whole store is an in-memory NetworkX `MultiDiGraph` singleton (L13-26)
  pickled to disk (`save`/`load` L208-240).

### Implication for TraLuat's pgvector choice (ivfflat vs hnsw)
None of the repos decide this for you — they are either brute-force (legalbenchrag,
LegalGraphRAG) or hide it (PAKTON/Chroma=HNSW, Pinecone=managed). The transferable facts:
- **Brute-force is exact + deterministic** (legalbenchrag, LegalGraphRAG). That is the recall
  ceiling and the reproducibility baseline. Use it as a *correctness oracle* for a pgvector eval,
  not as production.
- **Verdict: ADOPT pgvector `hnsw`, not `ivfflat`, for TraLuat.** Rationale grounded in the
  effectivity/tenant lens from `retrieval_mechanisms_audit.md` §4: TraLuat *must* filter by
  `tenant_id` + `as_of_date` in the same query as the ANN search. `ivfflat` degrades badly under
  selective pre-filters (it probes a fixed number of lists; a tight tenant/date predicate can
  empty most probed lists → recall collapse), and it needs a rebuild/`REINDEX` as data grows.
  `hnsw` tolerates filtered search far better and is incremental-insert friendly (matches
  TraLuat's per-version incremental index rebuild, `pipeline_storage_audit.md` #274). Pin
  `hnsw.ef_search` for reproducibility (HNSW is approximate — the one determinism cost vs the
  brute-force repos). Suggested starting params: `m=16`, `ef_construction=64`, `ef_search=40-100`
  tuned on a VN eval set. Keep a brute-force exact path (legalbenchrag-style) available for
  recall@k validation of the HNSW index.

---

## 2. Prefilter / narrowing (cheap pass before expensive pass)

### eyecite — Aho-Corasick literal-string prefilter before expensive regex (the key pattern)
`eyecite/eyecite/tokenizers.py`
- `AhocorasickTokenizer` L451-521. The idea: only run a citation-extractor's expensive regex when
  the target text literally contains one of that extractor's trigger strings.
- Build (once, `__post_init__` L458-481): two `pyahocorasick` automata — case-sensitive
  (L469-474) and case-insensitive (L476-481) — mapping each extractor's literal `strings` to the
  extractor. Extractors with no literal anchor go in `unfiltered_extractors` and always run
  (L461).
- Query (`get_extractors` L483-498): run the automaton over the text **once** (L492-497),
  union the matched extractors; only those regexes then execute. Whitespace is stripped on both
  sides (`_strip_ws`, L490) so spaced-out forms ("N. Y. S. 2d") still select the compact
  prefilter ("N.Y.S.2d") — the prefilter is deliberately a *sound superset* of the regex matches
  (comment L462-467). Classic cheap-O(text) multi-pattern scan gating many O(text·patterns)
  regexes.
- Bonus precompute variant: `HyperscanTokenizer` L524+ precompiles **all** regexes into one Intel
  Hyperscan database and scans in a single pass; the compiled DB is cached on disk via `cache_dir`
  (L531-535) because "precompiling the database takes several seconds."

### legalbenchrag / PAKTON — NO prefilter, NO metadata predicate (confirmed global)
- legalbenchrag `baseline.py` query is pure ANN: `WHERE embedding MATCH ?` (L208) with no
  attribute filter. Grep for `filter=`/metadata predicate across `legalbenchrag/legalbenchrag` and
  PAKTON retrievers/indexers returns nothing — confirmed. PAKTON's `similarity_search_with_
  relevance_scores(query, k)` (retriever L164) passes no `filter`. `collection_metadata`
  (indexer L89, retriever L116) is HNSW index config, not a query predicate.
- So "prefilter-before-expensive **for vector retrieval**" is **net-new** for TraLuat. eyecite's
  Aho-Corasick is a prefilter but for *citation extraction*, not document search — it transfers to
  TraLuat's VN citation detector (below), not to the vector query.

### LeSICiN — structural narrowing via precomputed adjacency (a different kind of prefilter)
`LeSICiN/data_helper.py` — metapath sampling only ever touches precomputed `adjacency[keys]`
(L158), never scans the full graph. The "narrowing" is that the typed adjacency is built offline
and sampling is bounded (see §4). Conceptually: structure prunes the candidate set before any
scoring.

### Implication for TraLuat
- **ADOPT the eyecite pattern for the VN citation detector** (already recommended in
  `retrieval_mechanisms_audit.md` §9): Aho-Corasick over VN trigger literals ("Điều", "khoản",
  "Nghị định", "Luật", "NĐ-CP", "/QH") to decide *which* citation regexes to run, then resolve to
  canonical article IDs. Cheap, deterministic, no model. The whitespace-relaxed-superset trick
  (L462-467) matters for VN too (diacritic/spacing variants).
- **The vector-query prefilter (tenant + effectivity) is net-new** and is the single most
  important perf+correctness addition: it must be an **index-level pre-filter inside the pgvector
  query** (`WHERE tenant_id=? AND effective_from<=:as_of AND (effective_to IS NULL OR
  effective_to>:as_of)` in the same statement as the ANN `ORDER BY embedding <=> :q`), never a
  post-filter — post-filtering after top-k wrecks recall. This is exactly why §1 picks HNSW over
  IVFFlat.

---

## 3. Wide-then-narrow rerank budgets

### legalbenchrag — the canonical budget: embed top-300 → rerank down to top-k
`legalbenchrag/legalbenchrag/methods/retrieval_strategies.py`
- L30: `embedding_topk = 300 if rerank_model is not None else top_k`.
- L32: `rerank_topk = top_k` where `top_ks = [1,2,4,8,16,32,64]` (L12).
- So **with a reranker on, the cheap ANN stage always fetches 300 candidates; the expensive
  cross-encoder/API reranker narrows to the final 1–64. Without a reranker, ANN fetches exactly
  the final k** (no waste). This is the clean separation of a cheap wide stage from an expensive
  narrow stage.

`legalbenchrag/legalbenchrag/methods/baseline.py` (the execution)
- ANN stage honours `embedding_topk`: query `LIMIT ?` bound to `self.retrieval_strategy.
  embedding_topk` (L212).
- Rerank stage, L218-230: if a rerank model is set, rerank the retrieved texts then slice
  `reranked_indices[: self.retrieval_strategy.rerank_topk]` (L229). Narrowing is a plain slice.
- A third budget — **token budget** — caps the emitted context: L233-249 walks reranked snippets
  subtracting `remaining_tokens` and truncates the last span to fit `token_limit`. Three nested
  budgets: ANN-k → rerank-k → token-limit.

### PAKTON — same discipline, local cross-encoder, retrieve-wide config comment
`PAKTON/.../deployment/development/config.researcher.yaml`
- Explicit comment L11-12: "*Reranking happens after retrieving, so we must pick bigger top_k for
  retrievers; top_k of the reranker will determine the final number of documents to be fed to the
  LLM.*"
- vectordb retriever `top_k: 100` (L26); hybrid retriever `top_k: 64` (L46); **reranking `top_k:
  64`** (L69). So the wide stage is 100 (vector) and the reranker narrows to ≤64.
- `reranking.use_reranker: False` by default (L68) — reranker is **opt-in**; `reranker_type:
  flag-reranker`, `model: BAAI/bge-reranker-v2-m3` (L71-72), `use_fp16: True` (L73, a speed knob:
  FP16 inference "speeds up computation with slight performance degradation").

`PAKTON/.../Researcher/src/Researcher/graph/nodes/reranking.py` (execution)
- `top_k = reranker_config.get("top_k", 5)` (L18), optional `similarity_threshold` (L19).
- If reranker off: `return responseContext = retrieved_documents[:top_k]` (L76) — plain slice.
- If on: cross-encoder `reranker.predict(pairs)` (L94) or FlagReranker `compute_score(...,
  normalize=True)` (L103/L112-114), sort desc (L119), drop below `similarity_threshold` (L124),
  then `final_docs[:top_k]` (L129). Narrowing = threshold + slice.
- Note L83 pre-filters to docs containing a span tag before reranking — minor narrowing.

### Implication for TraLuat
- **ADOPT the wide-then-narrow budget as a first-class, configurable pair:** `ann_topk` (wide,
  ~100-300) → `rerank_topk` (narrow, ~10-20) → optional `context_token_limit` (legalbenchrag's
  third budget — valuable for bounding LLM cost on long VN articles). Make reranker opt-in like
  PAKTON (L68) so cheap queries skip it.
- **ADOPT** `use_fp16: True` (PAKTON L73) for the local `bge-reranker-v2-m3` — direct, free speed
  with negligible quality loss; pairs with the local-serving decision already made.
- **Caveat:** legalbenchrag's fixed 300 is a benchmark constant; TraLuat should tune `ann_topk`
  against recall@rerank_topk on a VN eval set — too wide wastes cross-encoder compute (the
  dominant cost), too narrow caps recall.

---

## 4. Bounded graph traversal / hop limits / fan-out control

### LegalGraphRAG — bounded by HARDCODED STRUCTURE, not by a guard parameter
`LegalGraphRAG/core/graph_construct/ontology_graph.py`, `feature_graph.py`, `LegalGraphRAG.py`
- Query entry `retrieve_evidence` (`feature_graph.py` L59-148) runs exactly two bounded strategies
  and unions them — there is **no recursive/BFS expansion, no configurable depth**.
- `community_expansion_retrieval` (`ontology_graph.py` L228-289): ANN on `Cluster` top_k=5 (L232)
  → LLM reranks clusters → **takes only the top 2 clusters** `cluster_ids[:2]` (L249, a hard
  fan-out cap) → within each cluster, cosine over that cluster's cases → `top_k` per cluster
  (L274) → LLM rerank (L286) → fixed hop to laws via `_cases_and_laws`. Depth is a fixed chain
  Cluster→Case(`BELONGS_TO`)→Law(`RELATES_TO_LAW`), not a loop.
- `semantic_match_retrieval` (L292-316): ANN on `Cases` top_k (L296) → LLM rerank → fixed one hop
  to laws. 
- Config: `community_expansion_top_k: int = 5`, `semantic_match_top_k: int = 5`
  (`LegalGraphRAG.py` L66-67, env-overridable L135-136). **There is no `max_hops`/`max_depth`/
  `fan_out` config** — `grep` for hop/depth/fanout in the config returns nothing. Bounds exist but
  are baked into the code's shape.
- **Warning (anti-patterns inside the "bounded" traversal):** to find a cluster's member cases it
  iterates **all** `db.nodes_data` and calls `get_neighbors` per node (L255-262) — O(N) full scan
  per selected cluster; and every similarity is the brute-force scipy cosine of §1. So "bounded
  hops" still ride on O(N) scans. Do not copy the scan; copy the *bound*.
- **Build-time (offline, correctly precomputed — see §6):** `run_knn(top_k=3)` (`ontology_graph.py`
  L74-107) builds `SIMILAR_TO` edges by **O(N²) all-pairs** brute-force cosine (nested loop
  L97-102) — expensive but one-time; `build_communities` (L110+) runs Louvain + PageRank + degree
  once.

### LeSICiN — bounded metapath sampling with FIXED fan-out and FIXED sample count
`LeSICiN/data_helper.py`, `LeSICiN/configs/hyperparams.json`
- `generate_metapaths` L149-173: for each schema (a fixed metapath template, e.g.
  Section→Act→…), walk the schema steps; at each step sample **`num_neighbors=1`** from the
  precomputed `adjacency[keys]` (L158). Fan-out per hop = 1. Path length = schema length (fixed).
- `num_samples` independent walks per schema, class default `num_mpath_samples=2` (L81, L106); the
  **actual config is `num_mpath_samples: 8`** (`configs/hyperparams.json` L16) — the "8
  instances/schema". Document side is also bounded: `max_segments=4`, `max_segment_size=8` (L81).
- So every traversal is O(num_schemas × 8 × schema_len × 1) — fully bounded, constant per target,
  independent of graph size because sampling reads precomputed adjacency, never scans the graph.
  This is the disciplined version of bounded traversal.

### PAKTON / legalbenchrag — no graph traversal at all (flat retrieval).

### Implication for TraLuat
- **The bounded-hop guard TraLuat needs is net-new as a reusable parameter.** Neither repo offers
  a `max_hops`/`fan_out`/`beam_width` knob: LegalGraphRAG hardcodes the shape (and leans on O(N)
  scans inside), LeSICiN hardcodes sampling constants. **ADOPT the discipline, build the guard.**
- Concrete recommendation for TraLuat's phase-2 reference graph (amends / amended-by / references
  / implementing-decree): make traversal an explicit bounded beam — `max_hops` (e.g. 2-3),
  `max_fanout_per_hop` (e.g. 5-10, LeSICiN-style sampling or top-k by edge weight), optional
  `beam_width` — and crucially run it over the **persistent store with indexed edge lookups**
  (pgvector relations / Apache AGE), never LegalGraphRAG's full-`nodes_data` scan. Edges must be
  effectivity-dated so a hop is only valid in a date window (net-new, per
  `retrieval_mechanisms_audit.md` §8). LeSICiN's "sample ≤k neighbours from precomputed adjacency"
  (L158) is the right primitive; LegalGraphRAG's "iterate all nodes to find neighbours" (L255-262)
  is the wrong one.

---

## 5. Embedding / LLM batching & concurrency

### legalbenchrag — the most reusable artifact in the set: `ai.py` batch + rate-limit client
`legalbenchrag/legalbenchrag/utils/ai.py` and `methods/baseline.py`
- **Ingest batch size:** `baseline.py` L143 `EMBEDDING_BATCH_SIZE = 2048`; embeddings computed in
  2048-chunk batches (L145-155), each batch bulk-inserted via `executemany` (L178-181).
- **Provider-aware max batch length:** `ai.py` `AIEmbeddingModel.max_batch_len` L88-97 — openai
  2048, cohere 96, voyageai 128. `ai_embedding` **recursively splits** any request larger than
  `max_batch_len` into sub-batches and runs them concurrently with `asyncio.gather` (L404-430).
- **Rate-limit handling (per-provider, proactive + reactive):**
  - Per-provider `asyncio.Semaphore(1)` guards (L134-137) — gate only the *pacing sleep*, not the
    API call, so requests still overlap.
  - Proactive pacing: sleep `expected_wait = max(60/rpm, tokens/(tpm/60))` before each call
    (embeddings L446-449/L475-477/L501-503; chat L251-253/L293-295), with declared per-provider
    `ratelimit_tpm`/`ratelimit_rpm` (L36-51, L63-97, L109-117) scaled by `RATE_LIMIT_RATIO = 0.95`
    (L124). I.e. it throttles itself to 95% of the published limit rather than waiting for 429s.
  - Reactive backoff: on `RateLimitError`, retry up to `num_ratelimit_retries=10` with
    `backoff_algo = lambda i: min(2**i, 5)` (capped exponential, L230-232, L384-386), raising
    `AITimeoutError` if exhausted (L285-286, L468-469, etc.).
- **One connection per event loop** (L157-166) — "API clients cannot be called from multiple
  event loops." A detail worth keeping if TraLuat mixes async workers.

### PAKTON — async at the API/service layer; no custom embedding batcher
- Embedding/vector ops go through LangChain (`OpenAIEmbeddings`, Chroma/Pinecone) which batches
  internally — PAKTON sets no batch size. Parsing chunking: `chunk_size=1000, chunk_overlap=200`
  (`Archivist/.../parser/naiveParser.py` L23; `graph/nodes/parsing.py` L28-30).
- Concurrency is request-level: FastAPI `async def` endpoints + Celery workers (`API/api.py`
  async handlers L55/L114/L412/L484; `API/tasks.py` `asyncio.run(process_query_async())` L119-126;
  Celery retry 3× per `pipeline_storage_audit.md`). LightRAG indexer does batch status polling
  (`indexers/lightrag.py` L90). So PAKTON's concurrency story is "scale out stateless workers,"
  not "batch within a call."
- Reranker speed knob: `use_fp16: True` (`config.researcher.yaml` L73) — see §3.

### LegalGraphRAG — process-level data parallelism, one worker per GPU
`LegalGraphRAG/run.py`
- `multiprocessing.Pool(processes=num_processes)` with `num_processes = len(devices)` (one per GPU,
  L142/L155); test cases split round-robin across workers (L144-147); `apply_async` per chunk
  (L162-173); `spawn` start method (L282).
- Graph built **once in the parent**, then each worker loads it **read-only** (`auto_build=False,
  auto_save=False`, L36-38) — clean build-once/parallel-eval split. No per-query concurrency, no
  embedding batching (embeddings are generated one node at a time in a loop, `feature_graph.py`
  L30-49 — a build-time serial loop, another naive spot).

### LeSICiN — GPU tensor batching (training-oriented)
`data_helper.py`: `pin_memory` (L176) for faster CPU→CUDA transfer, `collate_func` (L205) batches
examples; metapath tensors are shaped `[M, D, L+1]` (L165) to batch all 8 samples × documents in
one tensor op. Relevant only as "batch the graph sampling into tensor ops," not directly reusable.

### Implication for TraLuat
- **ADOPT legalbenchrag's `ai.py` as the template for TraLuat's embedding/LLM client** (adapted to
  local bge-m3 via vLLM/TEI/Ollama): batched embedding with a provider-declared `max_batch_len`,
  recursive split + `asyncio.gather`, proactive token/req pacing at ~95% of the backend's
  throughput, and capped-exponential retry. Even for a *local* server this prevents overrunning
  vLLM's queue. Keep `EMBEDDING_BATCH_SIZE` configurable (2048 is an OpenAI-shaped constant; a
  local TEI server may prefer 32-256 depending on VRAM).
- **ADOPT LegalGraphRAG's build-once / parallel-workers split** (`run.py` L36-38, L94-127, L155)
  for TraLuat's **offline ingestion** (embed + index a corpus once across N workers, workers load
  derived indexes read-only). **SKIP** its one-node-at-a-time embedding loop — batch it with the
  `ai.py` pattern.
- **ADOPT PAKTON's stateless-async-worker model** for *query-time* serving (FastAPI async +
  Celery), which complements the SQL store — but keep TraLuat's effectivity/tenant filter inside
  each worker's query. **SKIP** PAKTON's per-query BM25 refetch (retriever L147 → L200 `k=10000`).

---

## 6. Precomputation (compute once offline vs per-query)

| Artifact | Repo + file:line | Computed once (offline) | Per-query |
|---|---|---|---|
| Chunk embeddings | legalbenchrag `baseline.py` L136-191 | ✅ all chunks embedded+stored at `sync_all_documents` | only the **query** embedding (L197-201) |
| Embedding/rerank cache | legalbenchrag `ai.py` L120-122, L391-401, L535-547 | ✅ `diskcache` keyed `model‖input_type‖md5(text)` (embeds) and `model‖top_k‖hash(texts)` (reranks) — memoized across runs | cache hit = 0 compute |
| Aho-Corasick / Hyperscan automaton | eyecite `tokenizers.py` L458-481, L531-535 | ✅ automaton built in `__post_init__`; Hyperscan DB cached on disk | run automaton over query text only |
| Graph + SIMILAR_TO kNN edges | LegalGraphRAG `feature_graph.py` L54-56, `ontology_graph.py` L74-107 | ✅ `run_knn(top_k=3)` O(N²) edges built once | none |
| Communities / PageRank / degree | LegalGraphRAG `ontology_graph.py` L110-128 | ✅ Louvain + PageRank + degree once, stored on nodes (`communityId`, `pagerank`, `degree`) | none — read from node props |
| Cluster summaries + embeddings | LegalGraphRAG `ontology_graph.py` L185-208 | ✅ LLM-summarized per community, embedded once, stored as `Cluster` nodes | none |
| `judge_dep` (law dependency) | LegalGraphRAG (stored on law nodes, surfaced `feature_graph.py` L104/L131) | ✅ precomputed, carried as node data | read-only at query |
| Graph persistence | LegalGraphRAG `graph_db.py` L208-240; `run.py` L94-127 | ✅ pickled; `auto_build` rebuilds from source JSON, `auto_save` writes on exit | workers load read-only |
| Typed adjacency matrices | LeSICiN `data_helper.py` L158 (reads `adjacency`), built offline | ✅ adjacency precomputed; sampling only reads it | bounded sampling (§4) |
| sent2vec / doc vectors | LeSICiN `data_helper.py` L72-80, L116-131 | ✅ sentences pre-vectorized (`sent_vectorize`), stored | token/segment lookup only |

Pattern across the set: **everything structural and corpus-level is precomputed and persisted;
only the query embedding, the automaton scan, the ANN lookup, and the reranker run per query.**
LegalGraphRAG is the cleanest example (all graph analytics offline, workers read-only) — the
*discipline* is right even though the *implementations* are naive (O(N²) build, single pickle,
in-memory).

### Implication for TraLuat
- **ADOPT the precompute split wholesale as a principle:** per-version offline = chunk embeddings
  (bge-m3, batched), HNSW index build, FTS index, citation-resolution of cross-references, and —
  phase 2 — graph edges/analytics. Per-query = query embedding + reranker + bounded graph hops
  only.
- **ADOPT the cache discipline from `ai.py`** (embed/rerank memoization) **but** make the result/
  rerank cache key include `tenant` + `as_of` snapshot (embedding cache can stay tenant-agnostic —
  text→vector is pure), per `retrieval_mechanisms_audit.md` §8. Add a corpus+params digest so the
  index is invalidated when chunking/model changes.
- **ADAPT, don't adopt, the persistence form:** keep "derived stores are disposable/rebuildable
  from the Postgres SoR" (LegalGraphRAG `auto_build`), but reject single-pickle / whole-collection
  wipe in favour of incremental per-version rebuild (`pipeline_storage_audit.md` #274).
- **SKIP** LegalGraphRAG's O(N²) `run_knn` as-is — if TraLuat ever needs case-similarity edges,
  compute them via the HNSW index (each node's top-k neighbours), not all-pairs scipy.

---

## 7. ADOPT / ADAPT / SKIP summary for TraLuat

| # | Mechanism | Best evidence (file:line) | Does a repo give TraLuat the piece? | Verdict |
|---|---|---|---|---|
| 1 | **ANN index type for pgvector** | legalbenchrag `baseline.py:170,202-213` (brute-force); PAKTON Chroma=HNSW `vectordb.py:96-101`; LegalGraphRAG `graph_db.py:145-174` (brute-force) | **No** — all brute-force or hidden. Decision is ours. | **ADOPT `hnsw`** (filter-tolerant, incremental); pin `ef_search`. Keep brute-force (legalbenchrag-style) as an exact recall oracle. **SKIP** ivfflat (recall collapses under tenant/date pre-filter), Pinecone (residency), NetworkX/numpy (O(N)/O(N²)). |
| 2 | **Prefilter before expensive** (vector) | — (none of the vector stores filter: `baseline.py:208`, PAKTON `:164`) | **No — net-new.** | **BUILD:** tenant+effectivity predicate *inside* the pgvector query (pre-filter, not post). This is why #1 = HNSW. |
| 2b | **Prefilter before expensive** (citation) | eyecite `tokenizers.py:451-521` (Aho-Corasick); `:524-535` (Hyperscan+disk cache) | **Yes — directly.** | **ADOPT** for the VN citation detector: AC literal triggers → regex → resolve to article IDs. Reuse whitespace-superset trick (`:462-467`). |
| 3 | **Wide-then-narrow rerank budget** | legalbenchrag `retrieval_strategies.py:30,32` (300→k) + `baseline.py:212,229,233-249` (ANN-k→rerank-k→token-limit); PAKTON `config.researcher.yaml:11-12,26,69` + `reranking.py:76,129` | **Yes — directly, the strongest transferable pattern.** | **ADOPT** `ann_topk`(~100-300)→`rerank_topk`(~10-20)→optional `context_token_limit`, reranker opt-in (PAKTON `:68`). **ADOPT** `use_fp16:True` (`:73`) for local bge-reranker. Tune `ann_topk` on VN eval. |
| 4 | **Bounded graph traversal / hop guard** | LegalGraphRAG `ontology_graph.py:249,274` + `feature_graph.py:59-148` + `LegalGraphRAG.py:66-67` (hardcoded bounds, no guard param); LeSICiN `data_helper.py:149-173` + `hyperparams.json:16` (num_mpath_samples=8, num_neighbors=1) | **Partial — the *discipline* yes, a reusable *guard* no.** | **ADAPT:** build an explicit `max_hops`/`max_fanout`/`beam_width` guard over the persistent, effectivity-dated graph. Use LeSICiN's "sample ≤k from precomputed adjacency" (`:158`). **SKIP** LegalGraphRAG's full-`nodes_data` scan (`:255-262`) and brute-force cosine. |
| 5 | **Embedding/LLM batching & concurrency** | legalbenchrag `ai.py:88-97,120-124,134-137,404-430,446-449` + `baseline.py:143`; LegalGraphRAG `run.py:36-38,155`; PAKTON `api.py`/`tasks.py` async | **Yes — `ai.py` is a ready template.** | **ADOPT** `ai.py` batch+pace+retry client (adapt to local bge-m3/vLLM, configurable batch). **ADOPT** build-once/parallel-workers for ingest (`run.py`). **ADOPT** async workers for serving (PAKTON). **SKIP** per-query BM25 refetch (PAKTON `retriever:147,200`), one-at-a-time embed loop (LegalGraphRAG `feature_graph.py:30-49`). |
| 6 | **Precomputation** | legalbenchrag `ai.py:120-122,391-401`; LegalGraphRAG `feature_graph.py:54-56` + `ontology_graph.py:110-128` + `run.py:94-127`; LeSICiN `data_helper.py:72-80,158` | **Yes — discipline is clean across repos.** | **ADOPT** offline-everything-structural / per-query-only-query-embed+rerank+hops. **ADOPT** embed/rerank cache (tenant+as_of in result-cache key). **ADAPT** persistence to incremental per-version rebuild. **SKIP** O(N²) all-pairs kNN (use HNSW neighbours). |

### Net-new for TraLuat (no repo provides)
1. **Vector-query metadata pre-filter** (tenant + effectivity inside the ANN query) — the central
   gap; drives the HNSW decision.
2. **A reusable bounded-hop guard** (`max_hops`/`max_fanout`/`beam_width`) over a persistent,
   effectivity-dated reference graph.
3. **Effectivity-dated edges/rows** so precomputed indexes and hops are valid only in a date
   window; and **tenant+as_of in result/rerank cache keys**.
4. **Incremental per-version index rebuild** (repos do whole-wipe or single-pickle).

### Warnings (naive in the repos — do NOT copy)
- legalbenchrag/LegalGraphRAG vector search is **brute-force** (exact, but O(N)/O(N²)) — a recall
  oracle, not production.
- LegalGraphRAG rebuilds the full vector array on **every insert** (`graph_db.py:80,97`) → O(N²)
  ingest; and does full-`nodes_data` scans inside "bounded" traversal (`ontology_graph.py:255-262`).
- PAKTON's hybrid retriever **refetches the whole corpus to rebuild BM25 on every query**
  (`hybrid.py:147` → `vectordb.py:200` `k=10000`) — index BM25 once instead.
- LegalGraphRAG embeds nodes **one at a time** in a Python loop (`feature_graph.py:30-49`) — batch it.
