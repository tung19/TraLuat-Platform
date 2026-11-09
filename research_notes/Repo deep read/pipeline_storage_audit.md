# Data Pipeline & Data Storage Audit — Reference Repos → TraLuat

Audit date: 2026-11-05. Method: READ-only source inspection; nothing built/run. Paths + line numbers cited.
Scope: ingestion pipeline (stages, orchestration, parallelism, upload, idempotency/dedup, provenance/hash,
checkpoint/resume) and storage handling (what persists where, **LOCAL vs CLOUD**, blob store, derived-index
persistence/rebuild, backup/migration). Verdict per mechanism for TraLuat at the end.

Companion notes (already written, not repeated here): `storage_dataflow_check.md` (storage SoR verification),
`pakton.md` (agent/backend detail), `indigo.md` (FRBR/bitemporal model), `legalbenchrag.md`, `lesicin.md`,
`legalgraphrag_lmars.md`, `eyecite.md`, `claude_for_legal.md`.

**Headline for VN data-residency (NĐ 356/2025 — local-first required):**
- **Indigo** is the ONLY repo with a clean, config-flagged **local⇄cloud blob-storage switch**
  (`FileSystemStorage` ⇄ `S3Boto3Storage`, `settings.py:245-265`) — the directly adoptable pattern; its S3 path
  is S3-API, so it drops onto MinIO-in-VN with zero code change.
- **PAKTON** has a clean **vector-store** local⇄cloud switch (Chroma-on-disk ⇄ Pinecone-SaaS, config flag) but its
  raw-blob handling is a throwaway tempfile (no blob store at all).
- **LegalGraphRAG / LeSICiN / legalbenchrag** are **100% local-file** (pickle / JSON / sqlite) — residency-safe by
  construction, but prototype-grade persistence (single pickle, wipe-and-rebuild) with no cloud story.
- **claude-for-legal** is the inverse: **cloud-only by design** — every data source is a remote HTTP MCP connector
  (Ironclad/DocuSign/iManage/Google Drive/CourtListener…), nothing stored locally. A model NOT to follow for VN.

---

## 1. PAKTON — `refs/PAKTON/PAKTON Framework/`

### Ingestion pipeline
- **Upload entry:** FastAPI `POST /index/document/` (multipart, `.docx/.pdf/.txt`) → enqueues Celery task
  `async_index_document(file_content: bytes, metadata)` (`API/tasks.py:186-271`).
- **Orchestration = Celery** (broker RabbitMQ, result backend Redis — `API/docker-compose.yml:12-25,39-40`).
  Tasks `bind=True, max_retries=3, default_retry_delay=5` with `self.retry(countdown=5)` (`tasks.py:49,77,186,263`).
  A single global Archivist is warmed per worker on `on_after_configure` (`tasks.py:40-47,320-328`). Worker
  concurrency hardcoded `--concurrency=1` (`docker-compose.yml:66`).
- **Upload handling (the critical detail):** the uploaded bytes are written to an OS **tempfile**
  (`tempfile.mkstemp(suffix=ext)`, `tasks.py:231-238`), `archivist.index(filePath=...)` runs, then the tempfile is
  **deleted in a `finally`** (`tasks.py:242-245`). => **The raw document blob is NOT persisted anywhere.** Only the
  derived chunks (in Chroma/Pinecone) survive. No object store.
- **Parse/split stage:** `Archivist` indexing graph `parse_and_split` node (`Archivist/.../graph/nodes/parsing.py`):
  config `parser.type` = `"naive"` (RecursiveCharacterTextSplitter, chunk_size 1000 / overlap 200) or `"structural"`,
  with **try/except fallback to naive on any structural-parse error** (`parsing.py:32-40`). Output `splitDocs` then
  **fans out in parallel** to each enabled indexer (vectordb / lightrag) in the StateGraph (`graph/builder.py`).
- **Parallelism:** per-document fan-out across indexers (parallel graph edges) + Celery worker-level concurrency.
  No intra-document parallel chunk processing.
- **Idempotency / dedup:** **NONE.** Grep for `hashlib|md5|sha256|dedup|checksum|provenance` across the Archivist
  package = **empty**. Re-indexing is **wipe-and-replace**: `index()` calls `delete_all()` then `add_documents()`
  (`indexers/vectordb.py:122,132`; Pinecone branch `delete(delete_all=True)` `:156`). Chunks get the vector store's
  auto-generated IDs — no stable content key, no per-document scoping, so you cannot re-index one document without
  wiping the collection.
- **Provenance / hash:** none. Chunks carry only `metadata["retriever"]` tags, no source-file id, no hash, no
  effective-date.
- **Checkpoint / resume:** only Celery task retry (3×). No per-stage checkpoint; a mid-index failure restarts the
  whole document. (Note: the LangGraph `AsyncPostgresSaver` checkpointer is for **conversation** state, not ingestion.)

### Storage handling — LOCAL vs CLOUD
- **3–4 physical stores** (confirmed in `storage_dataflow_check.md §1`):
  1. **Postgres** (`postgres:15-alpine`, volume `postgres_data`, `docker-compose.yml:82-91`) — only conversation
     metadata (SQLAlchemy `User`/`Conversation`) + LangGraph checkpoint tables. NOT documents/chunks. **Local** (container).
  2. **Vector store — SWITCHABLE:** `use_vector_store: "chroma" | "pinecone"` (`indexers/vectordb.py:32-55`).
     - **Chroma = LOCAL on-disk**, `persist_directory` default `/chroma_db`, mounted to Docker volume
       `chroma_data:/chroma_db` (`docker-compose.yml:48,79,96`). Default in `config.example.yaml`.
     - **Pinecone = CLOUD SaaS** (`langchain_pinecone.PineconeVectorStore`, `vectordb.py:63-77`).
     - This is a clean, config-only local⇄cloud switch — the adoptable pattern.
  3. **LightRAG** (optional) — external HTTP service `http://localhost:9621`, graph+vectors inside it, black-boxed
     (`indexers/lightrag.py`). Self-hostable → local-capable.
  4. **HuggingFace cache** bind-mount `~/.cache/huggingface` (reranker/embedding models) — local.
- **Raw blobs:** none persisted (tempfile deleted, above). No MinIO/S3.
- **Derived-index persistence/rebuild:** vector store is the only derived index; rebuilt by wipe-and-reindex from
  re-uploaded files (there is no authoritative source store to rebuild *from* — uploads are the source and they're
  discarded). This is weaker than a true rebuildable-from-SoR design.
- **Backup / migration:** **Alembic** present and real — `API/alembic/versions/001_initial`, `002_add_message_count`
  (migrations cover users+conversations only; the vector store has no migration story). Backup = Docker volumes.

**Grade:** backend scaffolding is production-shaped (FastAPI+Celery+Alembic), but the *data pipeline* is
prototype-grade for a corpus platform: no blob store, no dedup/provenance, wipe-and-rebuild indexing.

---

## 2. Indigo — `refs/indigo/` (the production-grade reference)

### Ingestion pipeline
- **Upload entry:** import a single document via `Importer.import_from_upload(upload, doc, request)`
  (`indigo_api/importers/base.py:211-248`), content-type dispatch → RTF / AKN-XML / DOCX / PDF / HTML / plain
  (`base.py:218-245`).
- **Orchestration = `docpipe` Pipelines** — ordered, declarative stage lists per content type
  (`base.py:134-209`). Representative stages:
  - DOCX: `DocxToHtml → [parse_and_clean → SimplifyHtml → CleanTableStyles → SplitPOnBr → RemoveEmptyParagraphs →
    DoctypePipeline → RemoveInlines → HtmlToBluebellText → text_cleanup] → ParseBluebellText → WrapAnnotations →
    SerialiseXml` (`base.py:150-157,134-148`).
  - PDF: `PdfExtractPages → PdfToText → MinTextRequired → text_cleanup → RemoveBoilerplate → UnbreakLines →
    BreakLines → CorrectSubsectionNumSpaces → TextToHtmlText → …html_to_bluebell… → ParseBluebellText →
    SerialiseXml` (`base.py:159-178`). Page-range + cropbox selection supported (`base.py:296-308`).
  - Post-import analysis stage: `analyse_after_import` → `markup_document_refs` + italics-terms markup
    (`base.py:286-294`). This is where citation/reference extraction runs.
  The import itself is **synchronous within the request** (atomic per document); there's a `# TODO: make a pipeline?`
  at `base.py:247` for the post-analysis step.
- **Bulk ingestion orchestration:** `BatchAddWorkView` / `BatchUpdateWorkView` (`indigo_app/views/works.py:880-966`)
  create many Works+Documents from a **Google Sheets spreadsheet** (`bulk_creator.get_spreadsheet_sheets`,
  `is_gsheets_enabled`, `works.py:906-954`) or CSV. Row-by-row validate→create, permission-gated (`bulk_add_work`).
  Per-row import can call `importer.import_from_upload` (`works.py:1021`).
- **Background jobs = `django-background-task`** (DB-backed queue, NOT Celery): `@background(queue="indigo",
  remove_existing_tasks=True) @transaction.atomic` (`indigo_api/tasks.py:11-14,94-107`) for maintenance
  (prune deleted docs, ensure revisions). `remove_existing_tasks=True` gives built-in task-level idempotency.
- **Parallelism:** none notable in import (synchronous); background queue is serial per queue.
- **Idempotency / dedup:** Work identity = **`frbr_uri` UNIQUE** (`works.py:503`) — the natural dedup key for
  legislation (you cannot create two Works with the same FRBR URI). Attachments: `unique_together=(document,
  filename)` + `ensure_filename_unique()` auto-suffixes `-1,-2` on collision (`documents.py:768,773-788`). No content
  hash, but strong natural-key idempotency.
- **Provenance:** the **original uploaded blob is preserved as an `Attachment`** — e.g. RTF import keeps BOTH the
  source RTF and the converted DOCX (`import_from_rtf` → `stash_attachment`, `base.py:250-284`). `publication_document`
  (gazette PDF) is also stored. So raw source is retained for audit, unlike PAKTON.
- **Checkpoint / resume:** none for a single import (atomic). Bulk import is row-by-row (a failed row doesn't lose
  prior rows — each Work is committed independently).

### Storage handling — LOCAL vs CLOUD (★ the adoptable switch)
- **System-of-record = Postgres** (`postgres:13`, `settings.py:184-195`). AKN **XML stored whole in one TextField**
  `document_xml` (`documents.py:368`); structure/TOC parsed from XML on demand, not persisted as rows
  (`storage_dataflow_check.md §2`). Relational FRBR model (Work/Document/Amendment/Commencement). **Local** (container
  or managed PG).
- **Blob store — SWITCHABLE via Django `STORAGES`** (`settings.py:245-265`):
  ```python
  STORAGES["default"]["BACKEND"] = "django.core.files.storage.FileSystemStorage"   # DEBUG/local (line 247)
  if not DEBUG:
      STORAGES["default"]["BACKEND"] = "storages.backends.s3boto3.S3Boto3Storage"  # prod/cloud (line 256)
      AWS_S3_FILE_OVERWRITE = False; AWS_STORAGE_BUCKET_NAME = env('AWS_S3_BUCKET'); ...
  ```
  Attachments declared `file = FileField(upload_to=attachment_filename)` → path `attachments/{document_id}/{filename}`
  (`documents.py:749-757`) on whatever backend is configured. **This is the single cleanest local⇄cloud switch in the
  whole reference set** and it is **S3-API** → points at AWS S3 *or any S3-compatible store (MinIO) hosted in VN* with
  only env changes. `AWS_S3_FILE_OVERWRITE=False` gives immutable, versioned-ish writes.
- **Derived indexes:** TOC/provisions re-parsed from the XML column on demand (derived, not persisted). No vector/graph
  index at all (citation/amendment graph is relational FKs).
- **Backup / migration:** **Django migrations** (`indigo_api/migrations/`, squashed + 9 files) — the Alembic-equivalent.
  django-reversion stores edit-history snapshots (`works.py:720-724`). Backup = PG dump + blob-store bucket.

**Grade:** production-grade, battle-tested. The storage-switch and raw-source-retention patterns are the most directly
adoptable for TraLuat's residency requirement.

---

## 3. legalbenchrag — `refs/legalbenchrag/`

### Ingestion pipeline
- **Orchestration = plain Python script** (`legalbenchrag/benchmark.py`), no Celery/Temporal. Loop:
  load `Benchmark` JSON → build corpus → for each strategy: `ingest → sync → query → write CSV`.
- **Corpus load:** local files only — `open(f"./data/corpus/{path}.txt")` → `Document(file_path, content)`
  (`benchmark.py:69-94`); benchmarks from `./data/benchmarks/{name}.json` (`benchmark.py:36-37`).
- **Data source / download:** `generate/utils.py:106-112` `download_zip(name, url, save_path, check_path)` — streaming
  `requests.get(stream=True)` with a **skip-if-exists idempotency check** (`:108 "already exists. Skipping download"`).
  Source datasets (CUAD/MAUD/ContractNLI/PrivacyQA) fetched once for GT generation; `data/` itself not in repo.
- **Chunking stage (span-preserving):** `sync_all_documents` lossless partition + running-offset spans, with hard
  assertions `"".join(splits)==content` (`methods/baseline.py:117-134`; detail in `legalbenchrag.md §2`).
- **Idempotency / dedup:** **content-hash caching** via `diskcache` — every embedding/rerank/LLM call keyed by
  `md5(text)+model+type` (`utils/ai.py:122,374`). GT spans kept only if the quote matches **exactly once**
  (`generate_cuad.py:extract_quote_span`). So dedup is at the AI-call layer, not the document layer.
- **Provenance / hash:** `md5` content hash as the cache key (`utils/ai.py`); no document-level provenance beyond
  `file_path`.
- **Checkpoint / resume:** the diskcache IS the resume mechanism — re-running skips already-computed embeddings; the
  sqlite-vec DB is **deleted and rebuilt** each run (`baseline.py:161-162`), so index build itself is not resumable
  (intentionally disposable).

### Storage handling — LOCAL (entirely)
- **Vector store = sqlite-vec**, file `./data/cache/baseline.db`, `vec0` virtual table, vectors as raw f32 bytes
  (`baseline.py:160-181`). Chunk metadata (`document_id, span`) held in an **in-memory Python list** index-aligned to
  `rowid` (`:182-189`). **Local file.**
- **Cache = diskcache** `./data/cache/ai_cache.db` (local). Corpus = local `.txt`. Results = local CSV/JSON under
  `./benchmark_results/<ts>/`.
- **No cloud anything** (except outbound LLM/embedding API calls). **Derived index = wiped+rebuilt every run** (the
  purest "derived stores are disposable" pattern). **No backup/migration** (ephemeral by design).

**Grade:** eval-harness grade. Storage is deliberately throwaway-local; not a production store. The span-preserving
chunker and content-hash cache are the transferable pieces.

---

## 4. LeSICiN — `refs/LeSICiN/`

### Ingestion pipeline
- **Orchestration = `run.py` script** (no queue). Wires data→graph→model→train/test.
- **Data load:** JSONL line-by-line `json.loads(line)` (`data_helper.py:27-29`); graph from JSON edge files
  (`label_tree.json`, `citation_network.json`) built into `torch_sparse.SparseTensor` adjacency per edge-type
  (`helper.py:28-64`). Sent2Vec model from a local `.bin`.
- **Parallelism:** PyTorch DataLoader batching + metapath sampling; no pipeline-level parallelism.
- **Idempotency / dedup:** none (research script). **Checkpoint:** caches preprocessed data as **pickle**
  (`data_helper.py:45-49` `pickle` save/load), trained model `saved/best_model.pt`; re-run loads the pickle cache
  (crude resume). Graph/adjacency rebuilt from JSON if cache absent.

### Storage handling — LOCAL (entirely)
- Everything is local files: `data/*.jsonl`, graph edge JSON, `cache/*.pkl`, `saved/*.pt`. No DB, no cloud.
- **Derived index (adjacency tensors) = rebuilt from JSON**, cached as pickle. No backup/migration; `data/` gitignored
  (from Zenodo). Residency-safe but prototype persistence.

**Grade:** research prototype. Only the *concept* (file-based rebuildable hetero-graph) transfers, not the storage code.

---

## 5. LegalGraphRAG — `refs/LegalGraphRAG/`

### Ingestion pipeline
- **Orchestration = `run.py` with `multiprocessing.Pool`** (no queue/Temporal). Flow (`run.py:94-155`):
  1. **Build graph ONCE** on the first device (`build_config`, `build_device = devices[0]`, `run.py:100-114`) →
     persist pickle.
  2. **Split cases into N chunks**, one per GPU device; `multiprocessing.Pool(processes=len(devices))`
     (`run.py:138-155`) — **data-parallel over cases**, each worker reloads the graph pickle.
  - Inner loop `for case in tqdm(cases, ...)` per device (`run.py:45`).
- **Graph construction stages:** `_prepare_nodes_data` → `construct_hierargraph` (embed all nodes via bge-m3) →
  `store_nodes_with_embeddings` + `build_relationships` (fact-layer edges) → `run_knn(top_k=3)` → `build_communities`
  (Leiden) → rule-layer writes `judge_dep`+`related_laws` onto Law nodes (`legalgraphrag_lmars.md §A4`).
  `judge_dep` checklists generated **offline** (`scripts/prepare_law_judge_dep.py`) and frozen on the graph.
- **Idempotency / dedup / provenance:** none (research). **Checkpoint/resume:** the persisted graph pickle is the only
  checkpoint — `auto_build=True` rebuilds from source JSON if the pickle is missing; `auto_save=True` writes on exit
  (`env.example`; `LegalGraphRAG.py:244-265`). Per-case inference is **not** resumable (no run-ledger).

### Storage handling — LOCAL (entirely)
- **Graph + vectors = ONE pickle file** `graph_db_path=./outputs/main_experiment/qwen3_graph_db.pkl`
  (`graph_db.py:208-240` `pickle.dump/load`; in-memory NetworkX MultiDiGraph + numpy embedding dicts). **Local file.**
- **Source data = local JSON** (`case_db_path`, `law_to_crime_path`, `datasets_path` in `env.example`).
- **Embeddings via local Ollama HTTP** `http://localhost:11434/api/embed`, model bge-m3 (`embedding.py:5`, `env.example`);
  LLM via local vLLM `http://localhost:8000/v1` (some sub-tasks hit cloud DeepSeek `api.deepseek.com`).
- **Derived index rebuildable from source JSON** (`auto_build`) — the good pattern — but single-pickle persistence is
  fragile (no concurrency, no partial update, whole-graph rewrite). **No cloud, no backup/migration.**

**Grade:** research prototype with a *good rebuildable-derived-index idea* but fragile single-file persistence.

---

## 6. eyecite — `refs/eyecite/`

### Pipeline & storage
- **STATELESS pure-function library.** 4 stages are 4 functions: `clean_text → get_citations → resolve_citations →
  annotate_citations` (`eyecite/__init__.py:1-11`). Operates on in-memory strings; returns data objects.
- **No ingestion orchestration, no persistence, no DB, no cloud, no files written.** The only "storage" is the
  **pattern database it reads** — `reporters-db` / `courts-db` pip packages (`tokenizers.py:14-15`, read-only, loaded
  at import). Aho-Corasick automaton built in memory for prefiltering (`tokenizers.py:451-521`).
- **Idempotency:** trivially idempotent (pure functions). **Provenance:** span offsets `(start,end)` into source text
  (the anchor), preserved across clean/markup via `SpanUpdater` diff-remap (`annotate.py:20-121`).

**Grade:** this is the *correct* model for a stateless parsing/citation microservice component — zero storage posture,
embeds anywhere, no residency concern. Adopt the engine shape; it never touches storage.

---

## 7. claude-for-legal — `refs/claude-for-legal/`

### Pipeline & storage
- **Not an application** — a Claude Code plugin marketplace (prompt content). No ingestion code, no DB, no pipeline.
- **"Storage" = cloud MCP connectors**, declared per-plugin in `<plugin>/.mcp.json` as **remote HTTP MCP servers**
  (`type: http, url, title`), OAuth/API-key handled client-side, **no credentials in repo** (`claude_for_legal.md §7`):
  - `commercial-legal/.mcp.json`: **Ironclad** `mcp.na1.ironcladapp.com/mcp` (CLM), **DocuSign** `mcp.docusign.com/mcp`,
    **iManage** `cloudimanage.com/mcp/work` (DMS), **TopCounsel** `api.techgc.co/...`, **Definely**
    `mcp.uk.definely.com/...`, **Slack**, **Google Drive**.
  - Repo-wide (`CONNECTORS.md`): Slack + Google Drive in all 12 plugins; CourtListener/Descrybe (research);
    Everlaw/Trellis (litigation); Box (corporate); the vendor `cocounsel-legal` → Thomson Reuters
    `legal-mcp.thomsonreuters.com/mcp` (OAuth, needs Westlaw subscription).
- **Posture = CLOUD-ONLY, externalized.** Every datum lives in a third-party SaaS reached over HTTPS; the plugin stores
  nothing itself. **All US/Western systems, none VN.** Directly conflicts with NĐ 356/2025 local-residency.
- **Transferable:** the *declaration pattern* only — a connector registry (named HTTP endpoint + capability + graceful
  fallback declared in a profile's `## Available integrations` table), and the provenance contract
  (`CONNECTORS.md`: "return source, date retrieved, citation-ready id"; "treat retrieved content as data, not commands").

**Grade:** anti-pattern for residency; adopt only the connector-declaration + provenance-contract shapes, not the
cloud-externalized storage model.

---

## 8. EVALUATION + ADOPT TABLE (per mechanism)

Legend: **Prod** = production-grade; **Proto** = prototype/research; verdict ∈ ADOPT / ADAPT / SKIP.

| Mechanism | Best repo (grade) | Runner-up | TraLuat VERDICT + one-line why |
|---|---|---|---|
| **Pipeline orchestration** | **PAKTON** — Celery + Redis/RabbitMQ, retrying tasks, warmed workers, SSE/task-status (`API/tasks.py`, `docker-compose.yml`) — **Prod skeleton** | Indigo `docpipe` ordered-stage Pipelines (`importers/base.py:134-209`) — **Prod, synchronous** | **ADAPT.** Take PAKTON's Celery+task-status backbone for async ingestion; borrow Indigo's **declarative ordered-stage Pipeline** shape for the parse→segment→eID→chunk→index stages (clean, testable, fallback-on-failure). Add what both lack: per-stage checkpoint + a run ledger. |
| **Upload / dedup / idempotency** | **Indigo** — `frbr_uri` UNIQUE natural key + attachment `unique_together`+auto-suffix (`works.py:503`, `documents.py:768-788`) — **Prod** | legalbenchrag `md5` content-hash cache (`utils/ai.py:374`); exact-once quote match | **ADAPT.** Adopt Indigo's **natural-key idempotency** (FRBR URI) for documents/versions. ADD a content **SHA-256** on the raw blob (no repo does this well) for true dedup + provenance + tamper-evidence — PAKTON has zero dedup (wipe-and-replace), a gap to avoid. |
| **Blob / raw-file storage** | **Indigo** — `STORAGES` `FileSystemStorage`⇄`S3Boto3Storage` switch, keeps source+converted (`settings.py:245-265`, `base.py:250-284`) — **Prod** | PAKTON Chroma-volume (but blobs discarded) | **ADOPT.** Indigo's switch is exactly TraLuat's MinIO/S3 requirement — S3-API means a VN-hosted **MinIO** backend with only env changes; immutable writes (`AWS_S3_FILE_OVERWRITE=False`). **Retain the raw source blob** (Indigo does; PAKTON throws it away — don't). |
| **Derived-index persistence / rebuild** | **legalbenchrag** — wipe+rebuild sqlite-vec every run (`baseline.py:161-162`) & LegalGraphRAG `auto_build` from source JSON (`LegalGraphRAG.py:244-265`) — **Proto but right principle** | PAKTON vector re-index; Indigo TOC re-parse | **ADOPT (principle), ADAPT (impl).** Keep "derived stores (pgvector, AGE graph) are disposable, rebuildable from the Postgres SoR." Reject the fragile forms: single-pickle (LegalGraphRAG), in-memory span list (legalbenchrag), full-wipe-only reindex (PAKTON). TraLuat needs **incremental** per-document rebuild keyed by version id, not whole-collection wipe. |
| **Local⇄cloud switchability** | **Indigo** (blobs) + **PAKTON** (vectors) — both config-flag switches — **Prod/Prod** | — | **ADOPT.** Generalize both into one TraLuat "storage-backend" config: blob (MinIO-local ⇄ S3), vector (pgvector-local, since TraLuat consolidates — vs PAKTON's Chroma⇄Pinecone), LLM/embed endpoint (local vLLM/Ollama ⇄ cloud, per LegalGraphRAG/PAKTON `endpoint_url`). Default every switch to **local** for NĐ 356/2025. |
| **Backup / migration** | **Indigo** — Django migrations (squashed + 9) + django-reversion history (`works.py:720-724`) — **Prod** | PAKTON Alembic (`alembic/versions/*`, metadata only) — **Prod but narrow** | **ADOPT.** TraLuat (SQLAlchemy) uses **Alembic** (PAKTON pattern) for the Postgres SoR; add reversion/audit on legal-content tables (Indigo's edit-history idea) — essential for a bitemporal, auditable legal store. Derived indexes need no migration (rebuilt). |
| **Resume / checkpoint** | **PAKTON** — Celery retry (3×) (`tasks.py`); LangGraph `AsyncPostgresSaver` for *conversation* state — **partial** | LegalGraphRAG graph-pickle as build checkpoint; legalbenchrag diskcache | **ADAPT + BUILD.** No repo has a real ingestion checkpoint/resume. Combine: Celery retry (PAKTON) + content-hash skip-if-exists (legalbenchrag `download_zip`) + a **per-document per-stage status ledger in Postgres** (net-new) so a crashed corpus import resumes mid-batch. This is a TraLuat gap to build, not borrow. |

---

## 9. Local-first posture vs cloud dependencies (NĐ 356/2025)

**Clean local/cloud switch — the two to lift:**
1. **Indigo blob switch** (`settings.py:245-265`): `FileSystemStorage` (local) ⇄ `S3Boto3Storage` (S3/MinIO). S3-API →
   runs fully on VN-hosted MinIO. **This is TraLuat's object-storage blueprint.**
2. **PAKTON vector switch** (`indexers/vectordb.py:32-55`): Chroma-local ⇄ Pinecone-cloud. TraLuat's analogue is
   simpler — pgvector is *always* local (co-located in the Postgres SoR), so TraLuat is more local-first than PAKTON by
   construction (no SaaS vector dependency at all).
3. **Local inference endpoints** (LegalGraphRAG `localhost:11434` Ollama + `localhost:8000/v1` vLLM; PAKTON
   `endpoint_url` OpenAI-compatible): model serving can be fully local. Keep embeddings/LLM on VN infra by default.

**Residency-safe by construction (all-local, but prototype persistence):** legalbenchrag (sqlite+diskcache),
LeSICiN (JSON+pickle), LegalGraphRAG (pickle+local JSON), eyecite (stateless). Good news for residency; their storage
*code* is not reusable at production scale.

**Cloud dependencies to be aware of / avoid:**
- **claude-for-legal** — 100% cloud MCP connectors (Ironclad/DocuSign/iManage/Google Drive/Thomson Reuters/
  CourtListener). All foreign SaaS. **Do not inherit its storage model**; only its connector-declaration + provenance
  contract.
- **PAKTON** — Pinecone (if selected, cloud) and **Supabase JWT auth** (`API/auth.py`, cloud IdP) and optional cloud
  LLM keys. Choose the Chroma/pgvector + self-hosted-auth paths for VN.
- **Indigo** — optional **Google Sheets** for bulk work import (`works.py:906-954`) and Sentry; both are convenience
  integrations, droppable/replaceable for an air-gapped VN deployment.

**Bottom line for TraLuat storage/pipeline design:**
- Object blobs → **MinIO (VN) behind Indigo's S3 switch**, keep raw source + SHA-256.
- SoR → **Postgres + Alembic** (PAKTON/Indigo migration discipline), bitemporal content tables with reversion audit.
- Derived indexes → **pgvector + AGE, local, disposable, incrementally rebuildable** from the SoR (principle validated
  across legalbenchrag/LegalGraphRAG; implement incrementally, not wipe-and-rebuild).
- Ingestion → **Celery async (PAKTON) over declarative ordered stages (Indigo `docpipe`)**, with a net-new per-document
  per-stage status ledger for resume (no repo supplies this).
- Keep a **stateless parsing/citation component** (eyecite model) that touches no storage.
