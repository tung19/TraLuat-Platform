# Storage / DB Performance Audit — reference repos vs TraLuat's missing pieces

Scope: how the reference repos handle (1) DB index strategy, (2) materialized / consolidation
caching (avoid re-assembling a document from per-provision versions), (3) pagination / query
limits, (4) caching layers, (5) async / batching for throughput — and whether any of it is
reusable for TraLuat's four undesigned pieces:

- **(a)** bitemporal date-index strategy
- **(b)** materialized consolidated snapshot of "văn bản tại ngày T"
- **(c)** caching layers
- **(d)** pagination / batching

Method: READ-ONLY. No build/run. All claims are file+line cited. Focus = Indigo (only
production-grade CMS) + PAKTON, with legalbenchrag / LegalGraphRAG for async/caching patterns.

**Headline:** No repo in the set has a performance *design* — none state an SLO, latency budget,
p95/p99, or QPS target anywhere (confirmed by grep across indigo / PAKTON / legalbenchrag /
LegalGraphRAG; the only timing code is a wall-clock stopwatch in `LegalGraphRAG/run.py:158,178`).
Indigo's *architecture* (whole-document materialized expressions) is the single most reusable idea;
its *index tuning* is a cautionary counter-example, not a template.

---

## 1. Indigo — DB INDEX strategy

DB is PostgreSQL (`indigo/settings.py:183`). Indexes are **field-level only** — `db_index=True`,
`unique=True`, `unique_together`. There are **zero** `models.Index`, `index_together`, composite,
GIN, GiST, or `SearchVectorField` declarations anywhere in the models or the 9 migrations
(confirmed: grep for `models.Index|GinIndex|SearchVectorField|tsvector|index_together` → no hits in
`indigo_api/` models or migrations).

What IS indexed:
- `Work.frbr_uri` — `unique=True` (`indigo_api/models/works.py:503`) → implicit unique btree. This
  is the global identity key and the one well-indexed lookup path.
- `Work.slug` — unique SlugField, `max_length=4096` (`works.py:57`).
- `Document.work` FK — `db_index=True` (`indigo_api/models/documents.py:346`).
- `Attachment.filename` — `db_index=True` (`documents.py:759`); `unique_together('document','filename')` (`documents.py:768`).
- `DocumentActivity.document` FK indexed (`documents.py:892`); `unique_together('document','user','nonce')` (`documents.py:905`); edit-lease `token` unique UUID (`documents.py:927`).
- `Commencement`: `unique_together('commenced_work','commencing_work','date')` (`works.py:978`).
- `ArbitraryExpressionDate`: `unique_together('date','work')` (`works.py:1043`).
- `Commencement`/amendment date fields are plain `DateField` (`works.py:952`), and the work-level
  date fields `publication_date` / `assent_date` / `repealed_date` / `as_at_date_override`
  (`works.py:524,526,535,556`) are **all unindexed**.

**The critical gap for a temporal engine:** `Document.expression_date` — the axis every point-in-time
query filters on — is `DateField(null=False)` with **NO `db_index`** (`documents.py:373`). And
`Document.frbr_uri` is a plain `CharField`, **not unique, not indexed** (`documents.py:355`). Yet the
hot lookup `DocumentQuerySet.get_for_frbr_uri()` filters exactly on
`frbr_uri` + `expression_date__lte=... ORDER BY -expression_date` (`documents.py:103,123,128`). That
query is served only by the `work_id` FK index plus a sequential scan/sort on `expression_date`.
There is no composite `(work_id, expression_date)` or `(frbr_uri, expression_date, language)` index
despite that being the dominant access pattern.

**Full-text search:** Postgres FTS helpers exist — `SearchRankCD` (`ts_rank_cd`) and `Headline`
(`indigo_api/utils.py:50,40`) — but they are computed at query time and, in the open codebase, are
imported only within `utils.py` itself (grep: `SearchRankCD` / `Headline` → `utils.py` only). There
is **no materialized tsvector column and no GIN index** backing search. Live full-text search is
evidently a downstream/private concern, not solved here.

> Verdict for TraLuat (a): Indigo offers the *schema shape* to copy (an `expression_date` column on a
> whole-document row) but its indexing is an anti-pattern to avoid. TraLuat must add the composite
> bitemporal index Indigo lacks. **Net-new design work; repo gives a warning, not a solution.**

---

## 2. Indigo — MATERIALIZED / CONSOLIDATION caching (the reusable idea)

This is where Indigo earns its "production-grade" label and is the one mechanism worth adopting.

**Whole-document materialization, confirmed:**
- `Document.document_xml = models.TextField()` stores the **entire** Akoma Ntoso XML of one
  expression in a single column (`documents.py:368-369`). `content` is just an alias
  (`documents.py:412-415`). Indigo does **not** store per-provision rows and reassemble on read —
  it stores the assembled document.
- **One Document row per point-in-time version.** `expression_date` identifies the version
  (`documents.py:371-374`). A new consolidated snapshot is produced by
  `Work.create_expression_at(date, language)` (`works.py:685-708`): it finds the most recent
  expression at/before the date (`works.py:694-698`), **clones its whole `content`** into a fresh
  `Document` row, stamps the new `expression_date`, and saves (`works.py:701-708`). Amendments are
  applied by an editor into that materialized row — not computed at read time.
- `ArbitraryExpressionDate(date, work)` is a first-class "consolidation date" marker not tied to an
  amendment (`works.py:1026-1032`), with `.expressions()` returning the materialized docs at that
  date (`works.py:1048-1051`). `WorkMixin.possible_expression_dates()` assembles the whole timeline
  from publication + amendment + arbitrary/consolidation dates (`works.py:252-261`).

So "văn bản tại ngày T" in Indigo = **look up the pre-built row whose `expression_date` ≤ T** (a
filter + sort, `documents.py:125-129`), never a per-provision merge. That is exactly the
materialization strategy TraLuat is missing — read cost is one row fetch, write/consolidation cost is
paid once when the editor creates the expression.

**Caveat:** materialization is **author-initiated and manual** (an editor runs
`create_expression_at` and edits the XML). There is no automatic "apply amendment diffs to generate
snapshot T" engine. TraLuat, if it wants auto-generated consolidations from provision-level
amendments, must build that generator itself — Indigo only shows the *storage* target, not the
*assembly* automation.

**Rendered-output caches (separate from the XML store):**
- PDF / EPUB render cache in the Django cache backend, key = `format:id:updated_at.isoformat()`
  (+ component/portion + GET params) so it self-invalidates on edit
  (`indigo_api/renderers.py:135,149-173,178-200`).
- `adiff_html_str()` HTML-diff cache keyed by md5(old)+md5(new), 7-day TTL
  (`indigo_api/utils.py:156-162`).
- TOC is **not** persisted — computed on demand and memoised only in-process on the instance
  (`self._toc`, `documents.py:191-193`).
- **No** rendered-HTML-of-document DB column, no published-document table, no CDN/static publish of
  rendered docs. S3 is used only for uploaded attachments (`settings.py:256`, `documents.py:750`);
  whitenoise serves static JS/CSS (`settings.py:112,314`). HTML is rendered via XSLT per request
  (see `exporters.py` / `renderers.py`), relying on the PDF/EPUB cache for the expensive formats
  only.

> Verdict for TraLuat (b): **ADOPT the pattern** — one materialized whole-document row per
> (work, expression_date, language), fetched by a date filter. **ADAPT** the trigger: Indigo's is
> manual; TraLuat likely needs an automated consolidator from provision-version diffs, which is
> net-new. Verdict (c, rendered cache): the timestamp-keyed render cache
> (`renderers.py:178-200`) is a clean, directly reusable invalidation recipe.

---

## 3. Indigo — pagination / query limits / N+1

- DRF global pagination: `DEFAULT_PAGINATION_CLASS = indigo_api.utils.PageNumberPagination`
  (`settings.py:388`), `page_size=500, page_size_query_param='page_size', max_page_size=500`
  (`utils.py:55-58`). Search results use a tighter `SearchPagination(page_size=20)` (`utils.py:62`).
- N+1 avoidance is deliberate:
  - `DocumentQuerySet.for_rendering()` — `select_related('language__language','work__country__country',
    'work__locality')` + `prefetch_related(...commencements..., main_commencement, amendments,
    arbitrary_expression_dates)` (`documents.py:62-75`).
  - `no_xml()` defers the big `document_xml` column for list views (`documents.py:59-60`).
  - `DocumentManager.get_queryset()` prefetches `work` by default (`documents.py:42-44`).
  - Content API list endpoints apply `.undeleted().published().no_xml()` and
    `prefetch_related('work__aliases')` (`indigo_content_api/v2/views.py:82,182,390`).
  - `latest_expression()` uses `distinct('frbr_uri').order_by('frbr_uri','-expression_date')`
    (Postgres `DISTINCT ON`) to collapse to the newest expression per work (`documents.py:77-80`).
- For bulk PDF/EPUB/zip list exports it **bypasses pagination and serialization** and sorts in
  Python, not the DB (`v2/views.py:244-250`) — a deliberate escape hatch.

> Verdict for TraLuat (d, pagination): **ADOPT** — standard DRF PageNumberPagination with a hard
> `max_page_size`, a dedicated deferred-`xml` list queryset (`no_xml()`), and a `for_rendering()`
> prefetch bundle are exactly the right defaults and transfer directly to a Django/DRF TraLuat API.

---

## 4. PAKTON — throughput (Celery, warm worker, pooling); batching NOT present

- **Celery**, broker+backend from env, tasks routed to one per-service queue
  (`API/tasks.py:24-30`; `TASK_ROUTES = {f"{SERVICE_NAME}.tasks.*": {"queue": SERVICE_QUEUE}}`,
  `API/config.py:40`). Every task has retry: `bind=True, default_retry_delay=5, max_retries=3`
  (`tasks.py:49,77,186,273`).
- **Warm-per-worker agent:** a module-global `archivist = None` with lazy `get_archivist()` that
  builds the heavy Archivist once per worker process and reuses it (`tasks.py:37-47`). This is the
  "load the model/agent once, amortise across tasks" pattern.
- **DB connection pooling:** SQLAlchemy engine with `pool_pre_ping=True, pool_size=10,
  max_overflow=20` (`API/database/config.py:25-28`); non-autocommit `sessionmaker`
  (`database/config.py:34`).
- **Embedding batching — absent in PAKTON itself.** `Archivist/.../indexers/vectordb.py` does NOT
  batch: it hands the whole list to `PineconeVectorStore.from_documents(documents=docs,...)` or
  `self.db.add_documents(docs)` with no `batch_size` (`vectordb.py:110-132`), and it calls
  `delete_all()` before every index — a destructive rebuild-each-run (`vectordb.py:122,140-152`).
  (The "batch_size=2048" the brief expected lives in the *vendored* legalbenchrag copy under
  `PAKTON/Experiments and Evaluation/.../legalbenchrag/...baseline.py:143`, not in PAKTON's own
  indexer.)

> Verdict for TraLuat (d, throughput): **ADOPT** the warm-per-worker singleton (`tasks.py:37-47`),
> Celery retry/routing config, and the SQLAlchemy pool settings — all small, proven, directly
> portable. **SKIP** PAKTON's indexer as a batching reference (it has none and wipes the index each
> run).

---

## 5. legalbenchrag — content-hash disk cache + wide-then-narrow + rebuild-each-run

- **diskcache content-hash cache** (`legalbenchrag/legalbenchrag/utils/ai.py`): a persistent
  `diskcache.Cache("./data/cache/ai_cache.db")` (`ai.py:122`). Chat calls are keyed by
  `md5(model + messages)` (`get_call_cache_key`, `ai.py:202-212`), checked before the API call and
  stored after (`ai.py:234-238,367`). Embeddings are keyed by `md5(text)` per model+type
  (`get_embeddings_cache_key`, `ai.py:371-374`) with per-item cache-miss batching (`ai.py:390-393`).
  Per-provider `asyncio.Semaphore(1)` rate-limit gates (`ai.py:133-137`).
- **Embedding batching:** `EMBEDDING_BATCH_SIZE = 2048`, looped in slices
  (`methods/baseline.py:143-156`).
- **Wide-then-narrow retrieval:** sqlite-vec KNN `ORDER BY distance ASC LIMIT embedding_topk` (wide,
  `baseline.py:202-213`) → rerank and keep `reranked_indices[:rerank_topk]` (narrow,
  `baseline.py:218-230`) → truncate to a token budget (`baseline.py:232-237`).
- **Rebuild-each-run tradeoff:** the vector store `baseline.db` is deleted and recreated on every
  sync (`baseline.py:71-74,160-167`), but because embeddings are content-hash cached in diskcache,
  the expensive step is not repeated — only the cheap vector insert is. `run_benchmark()` ingests all
  docs, syncs once, then `asyncio.gather`s the queries (`run_benchmark.py:118-132`).

> Verdict for TraLuat (c): **ADAPT** the content-hash cache for TraLuat's own LLM/embedding calls —
> md5-of-input keying with a persistent store makes re-embedding Vietnamese provisions free across
> re-ingests, which decouples "rebuild the index cheaply" from "never re-pay for embeddings." The
> wide-then-narrow + token-budget retrieval shape is also directly reusable. Rebuild-each-run is fine
> for a benchmark harness but TraLuat needs incremental upserts, not `delete_all()` — **ADAPT, don't
> copy.**

---

## 6. LegalGraphRAG — precompute-once-then-pickle + data-parallel multiprocessing

- **Precompute-once-then-pickle:** the whole constructed graph (graph + node data + embeddings) is
  serialized with `pickle.dump` / `pickle.load` (`core/graph_construct/graph_db.py:208-234`), path
  `{model}_graph_db.pkl` (`run.py:91`). Build the graph once, reload the pickle on later runs.
- **Data-parallel throughput:** `multiprocessing.Pool(processes=num_processes)` with test cases
  round-robin-sharded across processes/devices and dispatched via `apply_async`, each writing its own
  `results_part_{i}.json` (`run.py:144-176`); `set_start_method("spawn")` (`run.py:282`). Wall-clock
  timing bracket at `run.py:158,178` is the closest thing to a benchmark in any repo — still no SLO.

> Verdict for TraLuat (c): **ADAPT** the precompute-then-persist idea at the artifact level — it is
> the same principle as Indigo's materialized expression (pay once, read many), applied to a derived
> graph/index rather than a document. The `multiprocessing.Pool` shard pattern is a reasonable
> offline-batch ingestion accelerator but is **not** a serving-path mechanism.

---

## ADOPT / ADAPT / SKIP table (per TraLuat missing piece)

| TraLuat missing piece | Best source mechanism | Where (file:line) | Verdict | Why / what's net-new |
|---|---|---|---|---|
| **(a) Bitemporal date index** | Indigo `expression_date` column shape | `documents.py:368,373` | **ADAPT (schema), SKIP (indexing)** | Copy the per-expression row shape; Indigo leaves `expression_date` + `frbr_uri` **unindexed** (`documents.py:355,373`) and has no composite index despite filtering on them (`documents.py:123-129`). The `(work_id/frbr_uri, expression_date, language)` composite + a second `knowledge/transaction-time` axis are **net-new** — no repo does true bitemporal. |
| **(b) Materialized "văn bản tại ngày T"** | Indigo whole-doc expression + `create_expression_at` + `ArbitraryExpressionDate` | `documents.py:368`; `works.py:685-708,252-261,1026-1051` | **ADOPT (store), ADAPT (assembly)** | Store one assembled row per (work, date, lang), read by date filter — directly reusable and is the core thing TraLuat lacks. But Indigo's snapshot creation is **manual/editor-driven**; an automatic consolidator that applies provision-level amendment diffs to emit snapshot T is **net-new**. |
| **(c) Caching layers** | Indigo render cache (timestamp key) + Indigo country FS-version cache; legalbenchrag content-hash disk cache; LegalGraphRAG pickle | `renderers.py:178-200`; `places.py:71-150`; `utils.py:156-162`; `legalbenchrag .../ai.py:122,202-238`; `graph_db.py:208-234` | **ADOPT/ADAPT** | Render cache keyed by `id+updated_at` and the md5-of-input LLM/embedding cache are small, proven, portable. Cross-process cache-coherency via a FS version counter (`places.py:122-150`) is a neat pattern for TraLuat's reference-data caches. **No repo caches a consolidated legal document at a date** — TraLuat's snapshot cache (b) is still the net-new centerpiece. |
| **(d) Pagination / batching** | Indigo DRF pagination + `no_xml()`/`for_rendering()`; PAKTON warm worker + pool; legalbenchrag embedding batch | `utils.py:55-62`, `settings.py:388`, `documents.py:59-75`; `PAKTON tasks.py:37-47`, `database/config.py:25-28`; `baseline.py:143-156` | **ADOPT** | PageNumberPagination with hard `max_page_size`, deferred-XML list querysets, explicit select/prefetch bundles, warm-per-worker singleton, SQLAlchemy pool, and `EMBEDDING_BATCH_SIZE` slicing are all directly transferable. PAKTON's own vector indexer has **no** batching and rebuilds destructively (`vectordb.py:122-132`) — don't use it as the batching model. |

## Where the repos offer NOTHING (net-new for TraLuat)

- **Any performance SLO / latency budget / p95 / QPS target.** None exist in any repo. TraLuat sets
  its own from scratch.
- **True bitemporal (valid-time + transaction-time) indexing.** Indigo has single-axis valid-time
  (`expression_date`) only, and leaves even that unindexed.
- **Automatic consolidation** of a document-at-date from provision-level amendment versions. Indigo
  stores the result of manual consolidation; it does not compute it.
- **A served, cached, consolidated-document-at-date cache.** Render caches cover PDF/EPUB/diff only;
  the point-in-time legal text snapshot cache is TraLuat's to design.
- **A stored/GIN-backed full-text search index.** Indigo's FTS helpers are query-time only with no
  materialized tsvector.
