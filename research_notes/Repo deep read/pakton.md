# PAKTON — Deep Read & Extraction for TraLuat

Repo: `refs/PAKTON` (EMNLP 2025 paper code — "A Multi-Agent Framework for Question
Answering in Long Legal Agreements"). Author: Petros Raptopoulos et al.
Read-only analysis. All paths below are relative to `refs/PAKTON/`.

**Bottom line:** PAKTON is a genuinely-built, LangGraph-based multi-agent contract-QA
system with a real FastAPI+Celery+SQLAlchemy backend. The three agents and the
retriever/LLM abstractions are the directly reusable patterns for TraLuat's L5–L9.
BUT it is a single-document, single-contract QA tool with **no multi-tenancy, no
effectivity/temporal filtering, no metadata-scoped retrieval, and no grounding/
citation-verification layer** — exactly the pieces TraLuat must build itself. The
README's "missing components" warning is real: see §7.

---

## 1. Top-level directory map (code vs data vs experiments)

```
refs/PAKTON/
├── PAKTON Framework/        ← THE REAL BACKEND. This is what to study.
│   ├── API/                 FastAPI + Celery + SQLAlchemy + Alembic (production backend)
│   ├── Archivist/           Agent 1 — orchestrator / indexer (installable pkg, src/ layout)
│   ├── Interrogator/        Agent 2 — iterative interviewer (installable pkg)
│   ├── Researcher/          Agent 3 — RAG retrieval engine (installable pkg)
│   └── Frontend/            v0.1 (python chat.py) + v0.2 (TS/turbo monorepo) — UI, skip
├── Experiments and Evaluation/   ← PAPER/EXPERIMENT CODE, not production
│   ├── Quantitative/
│   │   ├── Classification Performance - ContractNLI/  (experimentsLibrary pkg: openai/
│   │   │     bedrock/google/anthropic/watsonx/local provider wrappers + lightRAG + eval)
│   │   └── RAG Performance - LegalBenchRAG/  (legalbenchrag harness; methods/pakton.py)
│   │   Qualitative/ (Human Eval, GEVAL LLM-as-judge, Statistical Agreement)
│   └── Frontend/ (results visualization site)
├── Machine Learning Experimentation/   ← explicitly "not mentioned in the paper";
│       classic sklearn ML (gridSearch, PCA, sampling) — IGNORE for TraLuat
├── deployment/              docker-compose.dev.yml, nginx, per-agent config.*.yaml, env scripts
├── Docs/                    PDFs (paper, poster, preprint)
└── README.md, CONTRIBUTING.md, LICENSE (Apache-2.0)
```

Each agent is a proper installable Python package: `<Agent>/src/<Agent>/...` with
`setup.py` (`python_requires>=3.11`), `requirements.txt`, `config.example.yaml`,
`examples/simple_query.py`, and `tests/`. Clean, modular, src-layout. 173 `.py` files
total; the vast majority of substance is in `PAKTON Framework/`.

**Verdict:** "PAKTON Framework/" is the real backend. "Experiments and Evaluation/" and
"Machine Learning Experimentation/" are research artifacts — mine them only for the
multi-provider LLM wrappers (ContractNLI `experimentsLibrary`) and eval methodology.

---

## 2. The three agents

The runtime composition is a **nested call hierarchy**, not a peer mesh:

```
Archivist (ReAct orchestrator, user-facing)
   └─ tool: interrogation  ──► Interrogator (LangGraph loop)
                                   └─ node get_answer ──► Researcher.search() (LangGraph RAG)
Archivist also owns indexing: parse_and_split ──► indexers (VectorDB / LightRAG)
```

### 2a. Archivist — orchestrator + indexer (L8 + L5-indexing)
Files: `PAKTON Framework/Archivist/src/Archivist/`
- `agent.py` — the `Archivist` class. Two distinct roles:
  1. **Indexing graph** (`index(filePath)`): a StateGraph `parse_and_split` → fan-out to
     each enabled indexer in **parallel** → END (`graph/builder.py`, `graph/nodes/parsing.py`).
  2. **Conversational ReAct agent** (`process_query`, `process_query_stream`): built with
     `langgraph.prebuilt.create_react_agent(model, tools, prompt=ARCHIVIST_SYSTEM_PROMPT,
     checkpointer=...)`. Its only tool is the interrogation tool. Streams via `astream`.
- Persistence: `AsyncPostgresSaver` (langgraph postgres checkpointer) keyed by `thread_id`;
  falls back to no persistence if `DATABASE_URL` missing (`_setup_postgres_checkpointer`).
- `get_conversation_content(thread_id)` reconstructs conversation from checkpoint into a
  frontend "timelineItems" shape (groups ai+tool messages). Good pattern for TraLuat L9 UI.
- `tools/interrogation_tool.py` — wraps Interrogator as a LangChain `@tool`
  (`response_format="content_and_artifact"`), runs the sync Interrogator in an executor to
  avoid blocking the event loop; returns `(conclusion_text, {report, conclusion})`.
- Inputs: user query (+ optional thread_id, model config). Outputs: streamed messages /
  final response; report+conclusion artifacts from the interrogation tool.

### 2b. Interrogator — iterative interviewer (L8 reasoning loop)
Files: `PAKTON Framework/Interrogator/src/Interrogator/`
- `graph/builder.py` defines the loop exactly as described:
  ```
  START → generate_question
  generate_question → (route_interrogation) → {get_answer | save_interrogation}
  get_answer → refine_answer → generate_question   (loop back)
  save_interrogation → write_report → END
  ```
- Nodes (`graph/nodes/`):
  - `generate_question.py` — LLM generates the next strategic legal question. Three prompt
    variants by phase: FIRST_QUESTION (no report yet), normal, FINAL_QUESTION (when
    `remaining_questions == 0`, switches node_name to "write_conclusion"). `remaining_questions
    = max_num_turns - len(messages)/2`.
  - `get_answer.py` — **This is the bridge to the Researcher.** Instantiates
    `Researcher({"enable_hybrid": True, "run_name": "Researcher"})` at module load and calls
    `researcher.search(query=question, instructions="**SEARCH STORED DOCUMENTS**...",
    config={"return_chunks": False})`. Returns the researcher's `response` as the next message.
  - `refine_answer.py` — maintains a running `report`: if no report yet, writes one from the
    full conversation (LEGAL_REPORT_WRITER_PROMPT); otherwise refines the existing report with
    just the latest Q/A (ANSWER_REFINING_PROMPT). Incremental report-building pattern.
  - `router.py` (`route_interrogation`) — ends the loop when `len(messages)//2 >= max_num_turns`
    OR when the interrogator emits the sentinel "Thank you, I am now in a position to answer the
    question with confidence." — matched literally **or** via `similarity_check()` (embedding
    similarity, so paraphrases also stop the loop). Clever, but a soft/fragile stop condition.
  - `save_interrogation.py` — formats the whole Q/A transcript into `interrogation` string.
  - `write_report.py` — final `conclusion` from report + interrogation summary
    (LEGAL_CONCLUSION_WRITER_PROMPT).
- State (`types/state.py`): `MessagesState` + userQuery/userContext/userInstructions,
  max_num_turns, interrogation, report, conclusion, config.
- `interrogation()` entry (`agent.py`) uses an ephemeral per-call `thread_id` (timestamp).
  Default `max_num_turns` = 1 (from config). Returns `{report, conclusion, ...}`.

### 2c. Researcher — RAG engine (L5 retrieval + L6-ish synthesis)
Files: `PAKTON Framework/Researcher/src/Researcher/`
- `graph/builder.py` flow:
  ```
  START → extract_query → (tools_condition) → {tools | generate_response}
  tools → rerank → generate_response → END
  ```
- Nodes (`graph/nodes/`):
  - `query_extractor.py` — binds the retriever tools to the LLM (`llm.bind_tools(tools)`),
    invokes with SEARCH_QUERY_PROMPT; takes the **first tool call's first arg** as the refined
    query and stores the tool-call message. Wrapped in `tenacity` retry (up to 10×, exp backoff)
    on `ValueError` (i.e. "no tool used"). So retrieval tool selection = the LLM's tool choice.
  - `router.py` (`tools_condition`) — route to `tools` if the message has tool_calls else to
    `generate_response` (standard langgraph pattern, reimplemented locally).
  - `tools.py` (`ToolNode`) — executes each tool_call, concatenates all returned Documents into
    `retrievedDocuments`.
  - `reranking.py` (`rerank`) — optional cross-encoder / FlagReranker / LayerWise-LLM reranker
    (sentence-transformers / FlagEmbedding), configurable top_k + similarity_threshold. **Off by
    default** (`use_reranker: False` → just takes `retrievedDocuments[:top_k]`). Note: filters to
    docs containing a literal `"--- ORIGINAL SPAN OF THE DOCUMENT ---"` tag before scoring.
  - `response_generator.py` — two modes: (a) standard RAG answer (RAG_SYSTEM_PROMPT +
    RAG_HUMAN_PROMPT over formatted context); (b) `return_chunks` mode that returns raw relevant
    spans, optionally LLM-filtered via gpt-4o structured output or Cohere command-r (Bedrock)
    with multi-retry JSON parsing. The Interrogator calls it with `return_chunks: False`.
- `agent.py` `Researcher.search(query, instructions, max_num_turns, config)` → invokes the graph
  with a fresh timestamp thread_id, returns the result dict (`response`, `responseContext`, ...).
- State (`types/state.py`): `MessagesState` + query, instructions,
  `retrievedDocuments: Annotated[List[Document], operator.add]` (reducer for parallel retrievers),
  responseContext, response, config, max_num_turns. `types/search_query.py` holds a `SearchQuery`
  pydantic schema (structured-output path is present but commented out).

---

## 3. Retriever abstraction (L5) — `Researcher/src/Researcher/retrievers/`

**Interface** — `base.py` `BaseRetriever(Runnable, ABC)`:
- `@property name -> str` (abstract)
- `@property tool -> Tool` (abstract) — returns a LangChain `Tool` so the retriever is directly
  bindable to an LLM for tool-calling.
- `retrieve(query: str, **kwargs) -> List[Document]` (abstract) — the one method to implement.
- Provided for free: `get_relevant_documents` (LangChain compat), `invoke` (Runnable compat),
  and `__call__(state) -> {"retrievedDocuments": docs}` (graph-node compat, reads `state["query"]`
  and per-retriever kwargs from `state["config"][self.name]`).

**Concrete retrievers** (all return `langchain_core.documents.Document`, tag
`metadata["retriever"]`):
- `vectordb.py` `VectorDBRetriever` — Pinecone **or** Chroma (selected by
  `retrievers.vectordb.use_vector_store`). OpenAI embeddings (`text-embedding-3-large`,
  `EMBEDDINGS_API_KEY`). `similarity_search_with_relevance_scores`, threshold filter,
  `fetch_all_documents()` (used to feed BM25). **No metadata/where filter is passed** — retrieval
  is global over the whole index.
- `bm25.py` `BM25RetrieverWrapper` — `rank_bm25.BM25Okapi` directly (not just LangChain's), exposes
  `retrieve_with_scores`, optional sigmoid normalization, threshold. Tokenization is naive
  `str.split()` (whitespace) — **a real problem for Vietnamese** (no word segmentation, diacritics).
- `hybrid.py` `HybridRetriever` — LangChain `EnsembleRetriever` fusing BM25 + VectorDB with
  configurable weights (default 0.5/0.5). Fetches all docs from vectordb each call to build BM25
  in-memory (expensive at scale). This is the default retriever the Interrogator uses.
- `lightrag.py` `LightRAGRetriever` — HTTP client to an external LightRAG server
  (`LIGHTRAG_BASE_URL`, default :9621); graph-RAG modes local/global/mix; `only_need_context`.
  Response parsed by `utils/lightrag_parser.py`. Graceful-degrade if server down.
- `web.py` `WebRetriever` — Tavily (`TAVILY_API_KEY`).
- `wikipedia.py` `WikipediaRetriever`.

**Pluggability:** high. `Researcher._setup_retrievers()` enables retrievers by boolean config
flags (`enable_web/wikipedia/vectordb/bm25/hybrid/lightrag`); `GraphBuilder.add_retriever(name, r)`
registers `r.tool`. Adding a retriever = subclass `BaseRetriever`, implement 3 members, add an
`enable_*` flag. Clean seam for TraLuat's hybrid+effectivity retriever — but note the tool is
registered by `.tool` and the LLM picks which to call, so all share the name `"DocumentSearch"`
(bm25/vectordb/hybrid all return a Tool named `DocumentSearch` — a latent collision if several are
enabled at once).

---

## 4. LLM provider abstraction (L7) — `*/models/`

Factory pattern, replicated per agent (Researcher/Interrogator/Archivist each have their own
`models/` dir — duplicated, not shared).
- `models/llm.py` `get_default_llm(node_name=None)`:
  - Looks up `config["models"][node_name]`; falls back to `config["models"]["default"]`.
  - Each model config = `{API: openai|bedrock|google, model_id, args:{temperature,max_tokens,...},
    endpoint_url?}`. Dispatches to `get_openai_llm` / `get_bedrock_llm` / `get_google_llm`.
- `models/openai.py` — `ChatOpenAI`; `endpoint_url` → `base_url`, so **any OpenAI-compatible
  endpoint works** (vLLM, Qwen/DashScope, DeepSeek — all noted in config.example.yaml). This is the
  "local model" path (there is no working local HF loader — see §7).
- `models/bedrock.py` — `ChatBedrock(beta_use_converse_api=True)`, AWS creds from env.
- `models/google.py` — `ChatGoogleGenerativeAI`.
- `models/local.py` (Interrogator only) — **stub**: `get_local_llm` immediately `return None`
  before any HF code (the comment says "use vLLM via the OpenAI path instead").
- `models/bert.py` — embedding/similarity helper; `router.py` uses `similarity_check()` from here.

**Per-node model routing is the key L7 idea for TraLuat:** different graph nodes
(`query_extractor`, `response_generator`, `question_generator`, `report_generator`,
`write_conclusion`) can each be pinned to a different model/provider via config, with a default
fallback. Config-driven, env-based secrets. The Archivist has a slightly different `get_llm(config)`
that accepts a per-request model override from the API payload.

Richer provider set lives in the experiments pkg
`Experiments and Evaluation/Quantitative/Classification Performance - ContractNLI/
experimentsLibrary/src/experimentsLibrary/` (openai, bedrock, google, anthropic, watsonx, local) —
worth copying the provider-normalization patterns from there if TraLuat wants Anthropic/WatsonX.

---

## 5. Backend shape (concrete, real) — `PAKTON Framework/API/`

This is a production-shaped backend, not a notebook.
- **FastAPI** (`api.py`): routes —
  - `POST /query/celery` (async via Celery, returns task_id)
  - `POST /query/sse` and `POST /query/stream_steps/sse` (Server-Sent Events streaming of
    Archivist steps/tokens; the stream_steps one surfaces tool_calls + artifacts)
  - `POST /index/document/` (multipart upload → Celery index task; accepts .docx/.pdf/.txt)
  - `POST /research/` (direct Researcher), `POST /interrogation/` (direct Interrogator)
  - `GET /task_status/{task_id}` (Celery AsyncResult)
  - `GET /conversations`, `GET /conversations/{thread_id}`,
    `GET /conversations/{thread_id}/messages`, `DELETE /conversations/{thread_id}`
  - `GET /health`, `GET /`
  - CORS wide-open (`allow_origins=["*"]`) — flagged as "configure for production".
- **Celery** (`tasks.py`): `celery_app` with broker/result backend from env
  (Redis/RabbitMQ per compose). Tasks: `process_query`, `index_document`, `research`,
  `interrogation` — all `bind=True`, `max_retries=3`, countdown retry. A single global
  Archivist instance is created per worker (`get_archivist`, warmed on `on_after_configure`).
  `index_document` writes the upload to a tempfile and calls `archivist.index()`.
- **SQLAlchemy** (`database/`): models `User` (PK email) and `Conversation` (PK thread_id, FK
  user_email CASCADE, title, message_count, created/updated). Repositories
  (`conversation_repository.py`, `user_repository.py`) encapsulate queries incl.
  `count_human_and_ai_messages`. `database/config.py` holds `Base`/session; `get_db` (FastAPI dep)
  and `get_db_session` (context mgr for Celery).
- **Alembic** (`alembic/versions/`): `001_initial` (users + conversations tables),
  `002_add_message_count`. Real migrations.
- **Auth** (`auth.py`): **Supabase JWT** (HS256, `python-jose`), `SupabaseUser` from token claims.
  `get_current_user` is toggleable via `ENABLE_AUTHENTICATION` env (off = anonymous in dev).
  No RBAC, no org/tenant scoping — user identity is just an email from the JWT.
- **Important architectural note:** the **actual message history / document store is NOT in
  SQLAlchemy.** Conversation turns live in the **langgraph Postgres checkpointer** (keyed by
  thread_id); the chunks live in **Chroma/Pinecone + optional LightRAG**. The SQL DB only tracks
  conversation metadata (owner, title, counts). So there are effectively three stores.
- Config (`config.py`): `SERVICE_NAME`, Supabase, Celery URLs — all `get_required_env`.
- Dockerized: `API/Dockerfile`, `API/docker-compose.yml`, `entrypoint.sh`, `migrate.sh`;
  `deployment/` has dev compose, nginx configs, per-agent `config.*.yaml`, env-gen scripts.

---

## 6. REUSE vs REIMPLEMENT for TraLuat (mapped to L5–L9)

### L5 Retrieval (hybrid + effectivity filter)
- **REUSE (pattern):** `BaseRetriever` interface (`name`/`tool`/`retrieve` + Runnable/graph compat)
  — a clean, small seam. The hybrid BM25+vector `EnsembleRetriever` fusion and the
  config-flag retriever registry.
- **REIMPLEMENT / BUILD NEW (critical gaps):**
  - **Effectivity / temporal filtering does not exist.** No `valid_from/valid_to`, no
    as-of-date, no jurisdiction/document-status filter anywhere (grep confirms). Retrieval is
    global over the index. TraLuat's core L5 requirement (which law version is in force on date X)
    must be built — add metadata filters to the vectordb `similarity_search` call and a
    pre/post-filter stage; PAKTON passes no `filter=`/`where=` at all.
  - **Vietnamese tokenization:** BM25 uses `query.split()` — replace with VN word segmentation
    (e.g. underthesea/VnCoreNLP) and diacritic-aware normalization.
  - **Scale:** HybridRetriever calls `fetch_all_documents()` (up to 10k) and rebuilds BM25
    in-memory on every query — fine for one contract, unacceptable for a national legal corpus.
    Use a persistent lexical index (Elasticsearch/OpenSearch) instead.
  - **No metadata/tenant scoping** on any retriever (see L-multitenancy below).

### L6 Grounding / Verify
- **REUSE (weakly):** the `return_chunks` + span-extraction / LLM-filter path in
  `response_generator.py` is the closest thing to grounding — it isolates minimal supporting
  spans. The reranker stage is a relevance filter.
- **REIMPLEMENT / BUILD NEW:** There is **no citation verification, no faithfulness/attribution
  check, no "does the answer's claim actually appear in a cited article" step.** Answers are
  free-text from the LLM with no enforced citations to specific legal provisions. TraLuat's L6
  (grounding against authoritative article IDs, hallucination guard) is entirely greenfield.
  PAKTON relies on prompt instructions + reranking, which is not verification.

### L7 Model / Inference runtime (LLM Gateway)
- **REUSE (strongly):** the `get_default_llm(node_name)` factory + per-node model config + provider
  dispatch (openai/bedrock/google) + OpenAI-compatible `endpoint_url` for self-hosted/vLLM. This is
  essentially a lightweight LLM gateway and maps cleanly to TraLuat L7. Pull the richer provider
  wrappers (anthropic/watsonx) from the ContractNLI `experimentsLibrary` if needed.
- **REIMPLEMENT:** centralize it (PAKTON duplicates `models/` in all three agents — TraLuat should
  have one gateway module). Add what PAKTON lacks: token/cost accounting, rate limiting, caching,
  structured-output enforcement (their structured-output path is commented out), tenant-scoped keys,
  prompt-caching. `models/local.py` HF loader is a stub — don't port it; use the vLLM-via-OpenAI path.

### L8 Reasoning / Orchestration (multi-agent)
- **REUSE (strongly, as reference):** the whole LangGraph `StateGraph` + `GraphBuilder.compile(
  checkpointer).with_config(run_name=...)` pattern; the Interrogator's generate→answer→refine→
  report loop with a turn budget and an embedding-similarity stop signal; the Archivist ReAct
  orchestrator that exposes a sub-agent as a `@tool`; the Postgres checkpointer for durable
  per-thread state; the `operator.add` reducer for parallel retriever fan-in. These are directly
  transferable orchestration recipes for TraLuat's Review/Draft/Assistant agents.
- **REIMPLEMENT / HARDEN:** the stop-condition (literal sentinel string + similarity) is fragile;
  `max_num_turns` defaults to 1 (barely a loop as shipped). Thread IDs are timestamp-based in the
  agent entrypoints (collision/traceability risk). No per-step audit trail beyond logs.

### L9 Capability / Workflow (Review/Draft/Assistant)
- **REUSE:** PAKTON's single capability = "contract Q&A → report + conclusion" and its
  conversation-reconstruction into `timelineItems` (`Archivist.get_conversation_content`) is a good
  template for a chat/assistant workflow UI contract. The SSE `stream_steps` endpoint showing tool
  calls + artifacts is a reusable UX pattern for an agentic workflow.
- **REIMPLEMENT / BUILD NEW:** PAKTON has only the QA/report capability. TraLuat's Review / Draft
  workflows (clause-by-clause review, redlining, drafting from templates) are not present and must
  be built. No workflow state machine beyond the one interrogation loop.

### Multi-tenancy (cross-cutting, TraLuat requirement — ABSENT in PAKTON)
- Confirmed by grep: **no tenant/org model, no row-level scoping, no per-tenant vector namespace.**
  Vector store uses a single index name from config; auth yields only a user email. TraLuat must add
  tenant_id to every store (SQL rows, vector namespace/metadata filter, checkpointer thread keys)
  and enforce it at the retrieval and conversation layers. This is foundational and greenfield.

### Backend scaffolding (L7–L9 infra)
- **REUSE (strongly):** the FastAPI + Celery + Redis/RabbitMQ + SQLAlchemy + Alembic shape, the
  task-status polling + SSE streaming endpoints, the "SQL for metadata / checkpointer for history /
  vector DB for chunks" three-store split, per-worker warmed agent instance. Good production
  skeleton that matches TraLuat's Python/FastAPI stack.
- **REIMPLEMENT:** swap Supabase JWT for TraLuat's auth + tenant claims; lock down CORS; add
  authorization (PAKTON only authenticates); make the Archivist instance tenant-aware (it is a
  process-global singleton today).

---

## 7. What's actually missing / stubbed (verifying the README warning)

README (line 51) warns "the deployed version and the code ... are missing a few components."
Verified against the code actually present:
- **Present and real:** all three agents' graphs & nodes; all 6 retrievers; the model factory for
  openai/bedrock/google; the full API (FastAPI routes, Celery tasks, SQLAlchemy models,
  repositories, 2 Alembic migrations, auth, Dockerfiles, compose, nginx); per-agent
  `config.example.yaml`; tests dirs; frontend v0.1 (python) and v0.2 (TS monorepo skeleton).
- **Stubbed / non-functional:**
  - `Interrogator/.../models/local.py` → `get_local_llm` returns `None` immediately (HF loader
    commented out). Local models only work through the OpenAI-compatible `endpoint_url` (vLLM).
  - `query_extractor.py` structured-output path and `with_structured_output(SearchQuery)` branch
    are **commented out** — only the tool-call-argument extraction path runs.
  - Reranking is **disabled by default** (`use_reranker: False`); LLM-filtering disabled by default.
- **Absent (not just stubbed) — and these are the TraLuat-critical ones:**
  - No effectivity/temporal/jurisdiction filtering; no metadata-filtered retrieval.
  - No multi-tenancy / org scoping / RBAC.
  - No grounding/citation-verification (L6) layer.
  - No shared/centralized LLM gateway (duplicated per agent).
  - Real secrets/config (`config.yaml`, `.env`) are not committed — only `.example` files and
    `.env.example`; `deployment/env/` is gitignored. So you cannot run it as-is without supplying
    Supabase, OpenAI/AWS, Pinecone/Chroma, Tavily, Postgres, Redis/RabbitMQ, (optional LightRAG).
- **Config knobs worth noting** (`Researcher/config.example.yaml`): default model `gpt-4o` for
  default/query_extractor/response_generator; hybrid top_k 64, bm25/vector weights 0.5/0.5;
  vectordb top_k 100 on Chroma; reranker `BAAI/bge-reranker-v2-m3` (off); llm_filtering `command-r`
  via Bedrock (off).

---

## 8. Concrete "steal this" list for TraLuat (file-cited)

1. Retriever seam → `Researcher/src/Researcher/retrievers/base.py` (BaseRetriever) +
   `Researcher/.../agent.py::_setup_retrievers` (config-flag registry). Add effectivity-filter
   retriever as a new subclass; add `filter=`/namespace to `vectordb.py`.
2. LLM gateway → `Researcher/src/Researcher/models/llm.py::get_default_llm` (per-node routing)
   + `models/openai.py` (endpoint_url pattern for self-hosted). Centralize across agents.
3. Interrogator loop → `Interrogator/.../graph/builder.py` + `graph/nodes/{generate_question,
   get_answer,refine_answer,router,save_interrogation,write_report}.py` (iterative
   question→RAG→refine with turn budget + incremental report). Harden the stop condition.
4. Sub-agent-as-tool → `Archivist/.../tools/interrogation_tool.py` (ReAct agent calling a
   LangGraph sub-agent via `@tool(response_format="content_and_artifact")`, run in executor).
5. Durable orchestration → `GraphBuilder.compile(checkpointer=AsyncPostgresSaver)` in
   `Archivist/.../agent.py`; conversation reconstruction `get_conversation_content`.
6. Backend skeleton → `API/api.py` (SSE + Celery + task_status), `API/tasks.py` (retrying
   tasks, warmed worker), `API/database/*` + `API/alembic/versions/*` (metadata store + migrations).
   Rework auth/tenancy.
7. Multi-provider wrappers (if needed) → `Experiments and Evaluation/Quantitative/Classification
   Performance - ContractNLI/experimentsLibrary/src/experimentsLibrary/{anthropic,watsonx,bedrock,
   google,openai}.py`.

Do NOT port: `Machine Learning Experimentation/` (unrelated sklearn), frontend v0.1/v0.2 (own UI),
`models/local.py` stub.
