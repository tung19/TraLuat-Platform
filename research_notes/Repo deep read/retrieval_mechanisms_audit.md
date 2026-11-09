# Retrieval Mechanisms Audit — Reference Repos → TraLuat Adopt Verdicts

Date: 2026-11-05
Scope: Every retrieval mechanism found by reading source in `refs/` (READ-ONLY; nothing built/run).
Repos audited for retrieval: **legalbenchrag, PAKTON, LegalGraphRAG, L-MARS, eyecite, LeSICiN, indigo**.
No retrieval in **cobalt** / **bluebell** (Akoma Ntoso citation + parser libraries — structural only, no search/embeddings) and **claude-for-legal** (prompt/skill packs; "embedding" hits are prose about product-embedding licensing, not vector retrieval).

TraLuat lens applied throughout: (a) can the mechanism carry an **`as_of_date` effectivity filter** + **`tenant` scope**? (b) does it **transfer to Vietnamese**? (c) **local vs API** (cost / data-residency) and **determinism**.

Headline finding: **6 of 7 retrieval repos do GLOBAL retrieval with no metadata predicate** — they embed/BM25 over one flat corpus and filter nothing. Only **indigo** (a production legislation platform) natively scopes retrieval by `expression_date` (point-in-time ≈ effectivity) and `country`/`locality` (≈ tenant/jurisdiction). That asymmetry is the central lesson for TraLuat: the *algorithms* are reusable, but the *effectivity + tenant predicate must be added by us* — no research repo gives it for free except the one that is actually a legislation CMS.

---

## 1. CHUNKING

| Repo / file:line | Algorithm | Span preservation | Size / overlap |
|---|---|---|---|
| **legalbenchrag** `methods/baseline.py:91-116` | `"naive"` fixed char-window slices **or** `"rcts"` = LangChain `RecursiveCharacterTextSplitter` with a **legal-aware separator ladder** `["\n\n","\n","!","?",".",":",";",",", " ",""]` | **Strongest in the set.** `strip_whitespace=False`; asserts `"".join(splits)==content` (`:118-121`); char spans computed from running offsets (`:123-134`) so every snippet maps back to exact `(start,end)` in the source | `chunk_size=500`, `chunk_overlap=0` (`retrieval_strategies.py:11`, `baseline.py:112`) |
| **PAKTON (naive)** `Archivist/parser/naiveParser.py:31-34,79-83` | `RecursiveCharacterTextSplitter` | Wraps each chunk in `--- ORIGINAL SPAN OF THE DOCUMENT ---` markers so the original span survives into reranking/generation | `chunk_size=1000`, `chunk_overlap=200` (`graph/nodes/parsing.py:28-30`) |
| **PAKTON (structural)** `Archivist/parser/structuralParser.py` | **LLM-based structural chunking**: an LLM (`PARSING_PROMPT`, `get_llm`) extracts a `Section`/`DocumentStructure` tree (`:23-56`); chunks carry **structural ancestors** (`:474`) and/or **descendants** (`:511`) as context | Parent/child hierarchy preserved as a `StructuralTree` (`:57+`); each node keeps its own span marker | tree-sized nodes, not fixed length |
| **L-MARS** `lmars/tools/offline_rag_tool.py:195-246` | **Header-aware structural** chunking: split on markdown `#` headers first; oversize sections fall back to char windows with **sentence/paragraph break preference** (`rfind('\n\n')`, `rfind('. ')`) | file+offset `chunk_id` (md5), no exact-span contract | `chunk_size=500`, `chunk_overlap=100` chars |
| **LegalGraphRAG (baselines)** `baselines/retrieval/splitter.py:5-23`, `naive.py:17-18` | `tiktoken` `cl100k_base` **token windows** (deterministic token count) | none (stores chunk text only) | `CHUNK_TOKENS=1000`, `CHUNK_OVERLAP=200` tokens |

**Verdict for TraLuat:** **ADOPT** legalbenchrag's RCTS-with-span-contract as the baseline chunker (exact offsets are mandatory for citing *điều/khoản/điểm* back to source). **ADAPT** PAKTON's structural parser *idea* but replace the LLM parser with a **deterministic structural splitter driven by VN legal structure** (Phần/Chương/Mục/Điều/Khoản/Điểm) — we already have that structure from the Akoma-Ntoso-style ingest; LLM structural parsing is non-deterministic and costly. Keep ancestors-as-context (article heading + chapter) from PAKTON. Fixed separators `["!","?","."...]` are punctuation-neutral and transfer to Vietnamese fine; token windows (`cl100k_base`) also transfer but split VN mid-word — prefer char/structural.

---

## 2. EMBEDDING MODELS

| Repo / file:line | Model | Dims | Local / API | Notes |
|---|---|---|---|---|
| **legalbenchrag** `utils/ai.py:378-532`, `retrieval_strategies.py:26-29` | `text-embedding-3-large` (OpenAI); code also supports Cohere + VoyageAI (`AIEmbeddingModel`, `:59-97`) | 3072 | **API** | `input_type` document/query split (`ai.py:481-511`); batch 2048; English-centric |
| **PAKTON** `Researcher/retrievers/vectordb.py:61,67` | `text-embedding-3-large` via `langchain_openai.OpenAIEmbeddings` (config default; `ada-002` commented) | 3072 | **API** | key from `EMBEDDINGS_API_KEY` |
| **LegalGraphRAG** `core/graph_construct/embedding.py:5-6` | **`bge-m3`** served by **Ollama** (`http://localhost:11434/api/embed`); `configure_embedding()` swappable (`:9-15`) | 1024 | **LOCAL** | **Multilingual (incl. Vietnamese).** Same backend reused for the graph baselines (`baselines/retrieval/naive.py:52`) |
| **LeSICiN** `model/submodules.py:4` (HierAttnNet) | **learned** word/sentence embeddings (HAN), trained end-to-end on the task | hidden_size=200 | LOCAL (trained) | not a general text embedder; task-specific |

**Verdict for TraLuat:** **ADOPT `bge-m3` served locally (Ollama / TEI / vLLM), exactly as LegalGraphRAG does.** It is the single most important transferable choice in the whole audit: multilingual (strong Vietnamese), local (no per-token cost, no data-residency/PDPD exposure), deterministic, 1024-dim (cheap to store). **SKIP** `text-embedding-3-large` as a dependency (API cost + Vietnamese legal text leaves the building + nondeterministic across model versions) — keep the pluggable `configure_embedding`/`AIEmbeddingModel` seam so it *can* be an optional backend. The document/query `input_type` split from legalbenchrag/PAKTON is worth copying (bge-m3 supports instruction prefixes).

---

## 3. VECTOR SEARCH (engine + algorithm)

| Repo / file:line | Engine | Algorithm | Metadata filter? |
|---|---|---|---|
| **legalbenchrag** `methods/baseline.py:169-213` | **sqlite-vec** `vec0` virtual table | `WHERE embedding MATCH ? ORDER BY distance ASC LIMIT k` — vec0 does an **exact (brute-force) KNN scan**, not ANN | **None** — single table, global |
| **PAKTON** `retrievers/vectordb.py:88-164` | **Pinecone** *or* **ChromaDB** (config `use_vector_store`) | `similarity_search_with_relevance_scores(query,k)` — Chroma = local **HNSW ANN**; Pinecone = managed ANN | **None passed** (`:164` has no `filter=`); `collection_metadata` (`:116`) is HNSW index config, not a predicate — global |
| **LegalGraphRAG** `core/graph_construct/graph_db.py:134-174` | **NetworkX in-memory** (`MultiDiGraph`) + numpy arrays | **numpy brute-force cosine** (`scipy.spatial.distance.cosine`, `1-dist`), full linear scan then `sort[:top_k]` | None — in-memory single graph |
| **LegalGraphRAG (naive baseline)** `baselines/retrieval/naive.py:44-77` | numpy | L2-normalized matrix then `embeddings @ query` dot product (= cosine), `argsort` top-5 | None |
| **L-MARS** | — | **No vector store** (BM25 offline + external web APIs) | n/a |

**Verdict for TraLuat:** **ADOPT `pgvector` (not any of these) + the SQL `WHERE` predicate pattern.** None of the repos' engines carry metadata, but all are trivially replaceable by a single relational vector store where the effectivity + tenant filter is *just a WHERE clause*. legalbenchrag's sqlite-vec is the closest spiritual match (SQL + vectors in one store) and proves the pattern; swap SQLite→Postgres so we get `WHERE tenant_id = ? AND effective_from <= :as_of AND (effective_to IS NULL OR effective_to > :as_of)` **in the same query as the ANN search** (pgvector HNSW with filtered search). **SKIP** the NetworkX/numpy brute-force stores (don't scale, lose on every re-run) and **SKIP** Pinecone (managed = residency risk + cost; PAKTON's own code never filters it anyway). Determinism: brute-force cosine is exact/deterministic; HNSW ANN is approximate — fine for recall at our scale but pin `ef_search` for reproducibility.

---

## 4. SPARSE / LEXICAL

| Repo / file:line | Mechanism | Tokenization | TraLuat transfer |
|---|---|---|---|
| **PAKTON** `retrievers/bm25.py:21,64-65,148` | `rank_bm25.BM25Okapi` + sigmoid score squash (`:30-32,154`) | **`query.split()` / `doc.split()` — raw whitespace** | **Weak for VN**: no accent folding, no legal-token handling; VN whitespace-splits into syllables not words. Needs a VN analyzer |
| **L-MARS** `tools/offline_rag_tool.py:15-107,119-133` | **Hand-rolled BM25** (`k1=1.5, b=0.75`, IDF `log((N-df+0.5)/(df+0.5)+1)`) | lowercase, strip non-alphanumeric, **English stopword list**, drop tokens ≤2 chars | **Won't transfer**: English stopwords + `len>2` filter destroy VN tokens; hard-coded |
| **indigo** `indigo_api/utils.py:50-52,34-47` | **PostgreSQL full-text search**: `SearchRankCD` = `ts_rank_cd` (cover-density, proximity-aware), `Headline` = `ts_headline` snippets, `SearchVector`/`SearchQuery` with a **language `config`** | Postgres text-search config (language-parametrized) | **Best-transferring lexical option**: Postgres FTS with an `unaccent` + `simple`/custom VN config; already date/place-scoped (see §10) |
| **eyecite** `eyecite/tokenizers.py:452-492` | **Aho-Corasick multi-pattern prefilter** (`pyahocorasick`) that narrows *which* reporter/law regexes to run; whitespace-relaxed prefilter strings (`:469-481`); `HyperscanTokenizer` (Intel Hyperscan) also available | string-set match over `reporters_db` strings | Pattern = **ADOPT for VN citation detection** (see §9/§10) |

**Verdict for TraLuat:** For keyword/lexical recall, **ADOPT indigo's Postgres FTS approach** (one store, `ts_rank_cd` proximity ranking, language config, and it already filters by date+place) over the two Python BM25 implementations, both of which are English-tokenized and would silently under-retrieve Vietnamese. If a true BM25 is wanted alongside, **ADAPT** `rank_bm25`/BM25Okapi but **replace tokenization with a Vietnamese analyzer** (e.g. `pyvi`/`underthesea` + accent-aware folding) and drop the English stopword/`len>2` filters. The Aho-Corasick prefilter from eyecite is orthogonal (citation extraction, not document search) and is **ADOPT** — see §9.

---

## 5. FUSION

| Repo / file:line | Mechanism |
|---|---|
| **PAKTON** `retrievers/hybrid.py:48,152-155` | LangChain **`EnsembleRetriever`** combining `BM25RetrieverWrapper` + `VectorDBRetriever`, `weights=[bm25_weight, vector_weight]` default **0.5/0.5** (`config.example.yaml:46-47`). EnsembleRetriever implements **weighted Reciprocal Rank Fusion** (RRF, constant c≈60): `score(d)=Σ weight_i / (c + rank_i(d))`. Hybrid `top_k=64` (`config:45`) |
| **LegalGraphRAG** `core/graph_construct/feature_graph.py:76-148` | Not RRF — **set union with dedup + priority ordering**: community-expansion results merged *before* semantic-match results, dedup by id (`seen_ids_cases/_laws`). `R(q)=R_sem ∪ R_com ∪ R_chg` |

**Verdict for TraLuat:** **ADOPT weighted RRF** as PAKTON does — it is rank-based (scale-free, so it fuses pgvector cosine with Postgres `ts_rank_cd` without score normalization headaches), deterministic, and cheap. Prefer our own ~20-line RRF over the LangChain `EnsembleRetriever` wrapper to avoid a heavy dependency and to keep the effectivity+tenant filter inside each arm. Note PAKTON's hybrid re-fetches *all* docs for BM25 on every query (`hybrid.py:147`) — do **not** copy that; index BM25 once. Start weights 0.5/0.5, tune on a VN eval set.

---

## 6. RERANKING

| Repo / file:line | Model(s) | When | Cost / determinism | VN? |
|---|---|---|---|---|
| **legalbenchrag** `methods/baseline.py:218-231`, `retrieval_strategies.py:9,30` | **Cohere `rerank-english-v3.0`** (also VoyageAI, `ai.py:594`) | **wide-then-narrow**: `embedding_topk=300` → rerank → `rerank_topk` | **API**, nondeterministic across versions, per-call cost | English-only model |
| **PAKTON** `graph/nodes/reranking.py:27-54,91-116`; `config.example.yaml:66-73` | configurable **cross-encoder** (`sentence-transformers.CrossEncoder`, e.g. `cross-encoder/ms-marco-MiniLM-L6-v2`) / **flag-reranker** (`FlagEmbedding.FlagReranker`, default **`BAAI/bge-reranker-v2-m3`**) / **llm-reranker** (`LayerWiseFlagLLMReranker` minicpm) | after retrieval, `top_k=64`→final; default `use_reranker=False` | **LOCAL**, deterministic, `use_fp16` speed knob | **`bge-reranker-v2-m3` is multilingual (Vietnamese)** |
| **LegalGraphRAG** `core/graph_construct/ontology_graph.py:27-71` | **LLM-as-reranker** (`rerank_clusters`, `rerank` via `model.generate_response`, parse `rank:[...]`) | inside R_com and R_sem, over cluster summaries + neighbor descriptions | LLM calls, nondeterministic | depends on LLM (fine if VN-capable) |

**Verdict for TraLuat:** **ADOPT `BAAI/bge-reranker-v2-m3` served locally**, exactly PAKTON's flag-reranker path — multilingual, local (residency-safe), deterministic, pairs naturally with bge-m3 embeddings. **ADOPT** legalbenchrag's **wide-then-narrow discipline** (retrieve ~100-300 candidates with the cheap vector/BM25 stage, cross-encode down to ~10-20) — this is the single highest-leverage retrieval-quality pattern in the set and is engine-agnostic. **SKIP** Cohere `rerank-english-v3.0` (English-only + API). **ADAPT (optional)** LLM-reranking for the final handful only (expensive, nondeterministic) — not for bulk. Cross-encoder reranking is naturally effectivity/tenant-safe because it only sees already-filtered candidates.

---

## 7. GRAPH RETRIEVAL / TRAVERSAL

All in **LegalGraphRAG** (`core/`) and **LeSICiN** (`model/`).

**LegalGraphRAG** — `R(q) = R_sem ∪ R_com ∪ R_chg` (`core/agents/researcher.py:1-4`):
- **R_sem (semantic match)** `ontology_graph.py:292-316`: brute-force cosine over `Cases` nodes → LLM rerank.
- **R_com (community expansion)** `ontology_graph.py:228-289`: cosine to `Cluster` nodes → `rerank_clusters` (LLM) → walk `BELONGS_TO` to member cases → cosine + LLM rerank. Communities built by **NetworkX greedy-modularity** `detect_communities` (`graph_db.py:191-203`), **PageRank** (`graph_db.py:176-180`) + degree centrality, cluster key-nodes by **composite `0.7*pagerank + 0.3*degree`** (`ontology_graph.py:146`).
- **R_chg (charge-anchored)** `researcher.py:22-35` + `fact_graph.py:193`: LLM predicts charge labels → embed each charge → cosine to `Crimes` nodes → follow edges to linked `Laws` articles. **This is the stand-out legal-domain pattern**: anchor retrieval on a predicted legal *concept* (charge/offence) rather than raw text similarity.
- **kNN graph** `ontology_graph.py:74-107`: `SIMILAR_TO` edges, `top_k=3`, built once at construction.
- Multi-hop traversal via `get_neighbors(node, relation_type)` (`graph_db.py:121-130`) across typed edges (`RELATES_TO_LAW`, `RELATED_CRIME`, `BELONGS_TO`).

**LeSICiN** — `model/submodules.py:39,101-130`, `data_helper.py:149-168`:
- **Metapath sampling** over a citation/section graph: `generate_metapaths` walks schema-defined metapaths, `adjacency.sample(num_neighbors=1)` random-walk neighbor sampling, `num_mpath_samples=2`.
- **MAGNN** (`MetapathAggrNet`): intra-metapath attention then inter-metapath attention aggregation → structural node embedding.

**Verdict for TraLuat:** **ADAPT, not adopt wholesale.** The **charge-anchored / concept-anchored retrieval** pattern (R_chg) is genuinely valuable for VN legal QA — anchor on predicted legal concepts (tội danh, loại quan hệ pháp luật, lĩnh vực) then follow curated edges to articles; it is explainable and controllable. The **typed multi-hop traversal** (article → amends/amended-by → references → implementing-decree) maps directly onto VN legislative cross-references and is worth building **on a real graph store (pgvector relations or a graph DB), not NetworkX in-memory** (LegalGraphRAG's singleton in-memory graph is rebuilt per process, unscoped, and won't carry tenant/effectivity). **SKIP** the LLM-at-every-rerank-step design (cost + nondeterminism) and **SKIP** LeSICiN's MAGNN/metapath model as infra (it is a *trained* classifier for Indian IPC, hidden_size=200, needs labeled citation data and retraining for VN; its value to us is conceptual — structural alignment — not code). Effectivity/tenant: graph edges must themselves be effectivity-dated (an "amends" edge is only valid in a date window) — none of these repos do this; it is net-new work.

---

## 8. QUERY UNDERSTANDING

| Repo / file:line | Mechanism |
|---|---|
| **PAKTON** `graph/nodes/query_extractor.py:45-70` | LLM **query rewrite + tool-calling retriever selection**: `llm.bind_tools(tools)`, the chosen tool's first arg becomes the refined query; `SEARCH_QUERY_PROMPT` (`utils/prompts.py:11+`) asks to "refine into focused/comprehensive/retrieval-optimized query" and pick tools; `tenacity` retry. Router `graph/nodes/router.py` branches on presence of tool calls |
| **LegalGraphRAG** `core/agents/researcher.py:10-35`, `core/preprocess/get_features.py` | **Ontology-structured query**: `get_features` extracts 4 ontology dimensions (defendant_info / criminal_acts / victim_property / intent_remorse), serialized to the embedding text (`ontology_query_text`); charge prediction via `RETRIEVE_LAW_PROMPT` |
| **L-MARS** `lmars/faith_search/router.py:53-184`, `aggregator.py:42-75` | **Verification-driven re-search routing**: after answering, route by failure type — `_fabricated_source`, **`_temporally_invalid`** (`:102`), `_partially_relevant`, `_unsupported`, `_no_citation` — each emits a `ReSearchPlan`; aggregator abstains below `min_confidence=0.6`. Iterative search↔judge loop (`workflow.py`, `agents.py`) |
| **eyecite** `eyecite/resolve.py:63-227` | **Antecedent resolution** (not query rewrite but reference resolution): `_resolve_shortcase`/`_resolve_supra` match `antecedent_guess` against candidate names (`:63-200`); `_resolve_id_citation` resolves `id.`/`ibid.` to the previous citation; pin-cite validity guard (`:110-135`) |

**Verdict for TraLuat:**
- **ADOPT** PAKTON's **query rewrite** (VN legal queries are colloquial; normalize to statutory terminology) and **tool-selection** idea, but keep tools few and typed (vector / lexical / citation-lookup / graph-hop).
- **ADAPT** LegalGraphRAG's **ontology-structured query** into a VN legal facet extractor (lĩnh vực, loại văn bản, quan hệ, as_of_date) — this is exactly where the **`as_of_date` gets parsed out of the user's question** ("luật đất đai năm 2020" → `as_of = 2020`) and turned into the retrieval predicate. High value.
- **ADOPT** L-MARS's **`_temporally_invalid` routing** concept — it is the only repo that treats *temporal/effectivity validity of a cited source as a first-class re-search trigger*. For TraLuat this becomes: if a retrieved article is not in force at `as_of_date`, re-search for the version that was. Pair with its abstention gate (answer "không chắc chắn" rather than cite a repealed article).
- **ADOPT** eyecite's antecedent/`id.`/supra resolution for VN cross-references ("Điều này", "khoản trên", "Nghị định nói trên").

---

## 9. CACHING

| Repo / file:line | Mechanism |
|---|---|
| **legalbenchrag** `utils/ai.py:120-122,234-238,371-375,535-547` | **`diskcache` content-hash cache** for all three AI ops: `ai_call` (md5 of model+messages), `ai_embedding` (`"{company}||{model}||{DOC/QUERY}||{md5(text)}"`), `ai_rerank` (md5 of query+texts+top_k). Persistent at `./data/cache/`. Also a corpus/chunking **digest** guard in the graph naive baseline (`LegalGraphRAG/baselines/retrieval/naive.py:33`) so a stored index is only reused if corpus+chunk params match |

**Verdict for TraLuat:** **ADOPT** content-hash caching for embeddings and reranks (keyed on `model||input_type||hash(text)`), and **ADOPT the corpus+params digest guard** so an index is invalidated when chunking/model/embedding changes. **Critical TraLuat addition the repos lack:** the cache key must include **`tenant` and the effectivity snapshot** (or embeddings/results leak across tenants and across legal versions). Embedding cache is tenant-agnostic (text→vector is pure) and can be shared; *result/rerank* caches must be tenant+as_of scoped.

---

## 10. LINKING / MATCHING RETRIEVAL

| Repo / file:line | Mechanism |
|---|---|
| **LeSICiN** `model/model.py:4-88`, `submodules.py:130-146` | **Trained bi-encoder matcher** for fact→law-section: `HierAttnNet` (HAN) text encoder for both sides; `MatchNet` (LSTM+attention+label-wise linear) scores query vs each section; **inductive via alignment** — `scores = λ0*attr_scores (text↔text) + λ1*align_scores (fact-text ↔ section-graph-structure)` (`model.py:50,60,80`), so sections with *no* training citations can still be matched by aligning to their graph structure. Multi-label, `pred_threshold=0.65` |
| **eyecite** `eyecite/tokenizers.py:452-492` + `resolve.py` | **Rule/pattern matcher** (not ML): Aho-Corasick prefilter → reporter/law regexes from `reporters_db` → citation objects → resolution to a `Resource`. Deterministic, no training |

**Verdict for TraLuat:**
- **SKIP LeSICiN as code / ADOPT as concept.** It is the most sophisticated matcher here, but it's a supervised model tied to Indian IPC with labeled citation graphs; standing it up for VN means building a VN section-citation graph + labels + retraining (large effort). Its transferable insight — **inductive matching via text↔structure alignment** so you can match to articles that have never been cited — is worth remembering for a later phase, not v1. bge-m3 + bge-reranker give us a zero-training bi-encoder+cross-encoder that covers most of the same ground.
- **ADOPT eyecite's pattern** for a **Vietnamese citation detector/linker**: build an Aho-Corasick/regex layer over VN citation forms ("Điều 5 Luật X 2013", "khoản 2 Điều 10 Nghị định 99/2015/NĐ-CP") to extract and **resolve references to canonical article IDs** — this is what lets retrieval hops and effectivity checks operate on resolved IDs, not strings. Deterministic, cheap, no model. (eyecite's `reporters_db` is US-specific; we supply a VN pattern/gazetteer.)

---

## 11. EVALUATION + ADOPT TABLE

| Mechanism | Best repo + file | Algorithm / model | Cost / determinism | VN transfer | Effectivity-filter + tenant-scope? | **VERDICT** |
|---|---|---|---|---|---|---|
| **Chunking** | legalbenchrag `baseline.py:91-134` | RCTS + exact span contract | free / deterministic | good (punctuation separators) | chunk carries no metadata; add `tenant`+`effective_*` as chunk cols | **ADOPT** (RCTS+spans); **ADAPT** PAKTON structural → deterministic VN structure splitter |
| **Embedding** | LegalGraphRAG `embedding.py:5-6` | **bge-m3** / Ollama, 1024-d, local | free / deterministic / swappable | **excellent (multilingual)** | model is scope-agnostic; vectors stored in filterable store | **ADOPT bge-m3 local**; **SKIP** text-embedding-3-large (API/residency) |
| **Vector search** | legalbenchrag `baseline.py:169-213` (pattern) | SQL + vectors, exact KNN | free / exact=deterministic | n/a | **engine must add WHERE** — none do | **ADOPT pattern on pgvector** (filter in same query); SKIP NetworkX/Pinecone |
| **Sparse / lexical** | indigo `utils.py:50-52` | Postgres FTS `ts_rank_cd` + `ts_headline`, language config | free / deterministic | good w/ `unaccent`+VN config | **indigo already scopes by date+place** | **ADOPT** indigo FTS; **ADAPT** rank_bm25 only w/ VN tokenizer |
| **Fusion** | PAKTON `hybrid.py:152-155` | weighted RRF (EnsembleRetriever) 0.5/0.5 | free / deterministic | model-agnostic | fuse already-filtered arms | **ADOPT RRF** (hand-rolled, filter inside arms); don't re-fetch-all like PAKTON |
| **Reranking** | PAKTON `reranking.py:37-54` | **bge-reranker-v2-m3** (FlagReranker), local | local / deterministic / fp16 | **excellent (multilingual)** | sees only filtered candidates → safe | **ADOPT bge-reranker-v2-m3** + **ADOPT** legalbenchrag wide-then-narrow; SKIP Cohere |
| **Graph retrieval** | LegalGraphRAG `researcher.py`, `ontology_graph.py` | charge-anchored + community(PageRank/modularity) + typed multi-hop | LLM-heavy / nondeterministic / in-memory | concepts transfer; code VN-agnostic | edges not effectivity-dated — net-new | **ADAPT** charge/concept-anchored + typed hops on persistent store; SKIP in-memory+LLM-every-step |
| **Query understanding** | PAKTON `query_extractor.py`; L-MARS `faith_search/router.py:102` | LLM rewrite + tool-select; temporal-validity re-search; abstention | LLM / nondeterministic | good (VN-capable LLM) | **this is where `as_of_date` is parsed**; L-MARS temporal routing | **ADOPT** rewrite + temporal re-search + abstention; **ADAPT** ontology facet→filter extractor |
| **Caching** | legalbenchrag `ai.py:371-375` | diskcache content-hash + params digest | free / deterministic | n/a | **must add tenant+as_of to result-cache key** | **ADOPT** (embed cache shared; result cache tenant+as_of scoped) |
| **Linking / matching** | eyecite `tokenizers.py:452`, `resolve.py`; LeSICiN `model.py` | Aho-Corasick + regex + antecedent resolution; (LeSICiN: trained HAN+MAGNN+MatchNet) | eyecite free/deterministic; LeSICiN trained | eyecite needs VN patterns; LeSICiN needs VN retrain | resolved IDs enable scoped hops | **ADOPT** eyecite-style VN citation linker; **SKIP** LeSICiN code (concept only) |
| **Point-in-time + tenant scoping** | **indigo** `indigo_api/utils.py`, `views/works.py`, `views/documents.py` | FRBR `expression_date` + `country`/`locality` filters native to every query | free / deterministic | production-grade | **YES — the only repo that does it** | **ADOPT as the architectural template** for effectivity+tenant |

---

## 12. Critical lens for TraLuat — synthesis

**Effectivity (`as_of_date`) + tenant scope.**
- **Reality check:** legalbenchrag, PAKTON, LegalGraphRAG, L-MARS, LeSICiN all do **global, unfiltered** retrieval. Their vector queries (`baseline.py:202`, `vectordb.py:164`, `graph_db.py:145`) take no predicate; their caches are not tenant-keyed. Treating any of them as a drop-in would silently retrieve across tenants and across repealed/future law versions.
- **The template to copy is indigo**, which is not a research RAG repo but a production legislation CMS: it models documents as FRBR expressions with `expression_date` and filters retrieval/listing by date and `country`/`locality` as a matter of course (`views/works.py:712`, `views/documents.py:224`). TraLuat should mirror this: every chunk/article/edge row carries `tenant_id`, `effective_from`, `effective_to` (and `version`), and **the effectivity+tenant predicate rides inside the same SQL as the pgvector ANN and the FTS rank** — never as a post-filter (post-filtering wrecks top-k recall).
- The **place to compute `as_of_date`** is the query-understanding layer (PAKTON rewrite + a LegalGraphRAG-style facet extractor), and the place to **enforce it as a quality gate** is an L-MARS-style `_temporally_invalid` re-search + abstention loop.

**Multilingual / local vs API-bound (cost + data residency).**
- **Local & multilingual (ADOPT):** `bge-m3` embeddings (LegalGraphRAG) and `bge-reranker-v2-m3` (PAKTON) — both run locally, both strong on Vietnamese, both deterministic, zero per-query cost, and keep VN legal text inside our infrastructure (PDPD / residency).
- **API-bound (flag / avoid as hard dependency):** `text-embedding-3-large` (legalbenchrag + PAKTON), Cohere `rerank-english-v3.0` (legalbenchrag) — cost scales per token/query, nondeterministic across model versions, and send Vietnamese legal text to a third party. Keep the pluggable backend seam (legalbenchrag's `AIEmbeddingModel`, LegalGraphRAG's `configure_embedding`) so these are optional, not default.
- **English-tokenized lexical (do not copy verbatim):** PAKTON `query.split()` BM25 and L-MARS's English-stopword BM25 will under-retrieve Vietnamese; use Postgres FTS with a VN config or rank_bm25 with a VN analyzer.

**Determinism / reproducibility.** Deterministic & reproducible: bge-m3/bge-reranker, brute-force cosine, Postgres FTS, RRF, Aho-Corasick, caching. Nondeterministic (quarantine to where quality justifies it): every LLM step — PAKTON/LegalGraphRAG LLM reranking, LegalGraphRAG charge prediction, query rewrite. Keep LLMs for query understanding and final-few reranking, not for bulk candidate scoring.

## 13. Recommended TraLuat retrieval stack (what the audit points to)
1. **Ingest/chunk:** deterministic VN-structural splitter (Điều/Khoản/Điểm) with legalbenchrag-style exact spans + PAKTON ancestor-context; rows carry `tenant_id, effective_from, effective_to, version`.
2. **Embed:** bge-m3 local (Ollama/TEI), doc/query input-type split; content-hash embedding cache.
3. **Store/search:** Postgres + pgvector (HNSW) **and** Postgres FTS in one DB; effectivity+tenant predicate in the same `WHERE` as ANN/FTS.
4. **Fuse:** hand-rolled weighted RRF over the vector arm + FTS arm (filter applied inside each arm).
5. **Rerank:** bge-reranker-v2-m3 local, wide-then-narrow (≈200 → ≈15).
6. **Graph (phase 2):** persistent typed, effectivity-dated reference graph; concept/charge-anchored retrieval + multi-hop over amends/references.
7. **Query understanding:** LLM rewrite + VN facet/`as_of_date` extractor; eyecite-style VN citation linker to resolve references to canonical IDs; L-MARS-style temporal-validity re-search + abstention gate.
8. **Cache:** embeddings shared; result/rerank caches keyed by `tenant + as_of + params-digest`.
