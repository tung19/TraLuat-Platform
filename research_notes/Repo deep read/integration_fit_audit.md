# TraLuat — Deep Integration-Fit Audit (seam-by-seam)

> Question: if we lift a bit from each cloned repo and merge/migrate them into ONE architecture,
> will it WORK WELL — or will the seams break?
> Method: READ-ONLY inspection of `refs/*` dependency manifests + source, cross-checked against the
> canonical target (`docs/specs/w2-knowledge-graph.md`, `w5-backend.md`,
> `docs/specs/retrieval-and-storage-mechanisms.md`). No build/run/install performed.
> Verdict vocabulary: **WIRE-AS-LIB** (pip-install, call directly) · **REMODEL-PATTERN** (reimplement
> the idea on our schema/runtime, don't run the code) · **RUN-AS-SEPARATE-SERVICE** (keep it in its own
> venv/process) · **REBUILD-FOR-VN** (reimplement with VN data/language).

---

## 0. Bottom line first

**The intended model — "don't merge codebases; lift PATTERNS and re-home them onto ONE canonical
bitemporal schema (W2) + ONE runtime (FastAPI+Celery+SQLAlchemy from PAKTON), touching the system
only through `TemporalRepository` / `RetrievalService` / `GroundingService` / `LLMGateway`" — is the
correct call and it holds up.** The seams break only if the team instead tries to literally
`pip install` and glue the repos together.

Why: the repos do not share a single internally-consistent dependency universe. They disagree on
Python floor (3.10 vs 3.11 vs 3.12), on the langchain major (0.2 vs 0.3), on web framework
(Django 5 vs FastAPI), on torch ABI (plain torch 2.9.1 vs `torch_sparse`), and three carry **no
license at all**. Exactly **two pieces are genuinely pip-mergeable as libraries** (eyecite, cobalt),
and even cobalt forces a Python-version bump. Everything else is either a pattern to reimplement or a
service to isolate.

- **Biggest integration risk:** the **langchain 0.2 → 0.3 break** combined with the **Python 3.11 vs
  3.12 floor split**. These make a single shared virtualenv for "PAKTON engine + legalbenchrag eval +
  cobalt/indigo AKN tooling" physically impossible. If the team tries one env, pip backtracks forever
  or silently installs a resolution that breaks one side at import time.
- **Second risk (semantic, not dependency):** the **data-model impedance** between what the repos
  produce (LangChain `Document` blobs, whole-document AKN XML in one column, US/IPC citation objects,
  in-memory heterogeneous graphs) and the canonical relational `unit_version` + `norm_relation` + AGE
  schema. The glue here is real transformation code, not an import.
- **What would BREAK on a naive code-merge:** (a) one `requirements.txt` union is unsatisfiable
  (langchain pin clash); (b) Django and FastAPI cannot co-host one process/ORM; (c) `torch_sparse`
  will not install against the reranker's torch without CUDA/ABI gymnastics; (d) three repos are
  legally unmergeable (no LICENSE); (e) every retrieval path from the merged code queries GLOBAL with
  no `as_of`/`tenant` predicate, so a literal lift silently violates both correctness (effectivity)
  and the hard multi-tenant isolation invariant.

---

## 1. Dependency / runtime matrix (from manifests, file-cited)

| Piece | Python floor | web/runtime | langchain / core | pydantic | sqlalchemy | torch | License | Manifest |
|---|---|---|---|---|---|---|---|---|
| **PAKTON API** | **3.11.11** (`API/Dockerfile:10`) | FastAPI 0.121.3, celery 5.5.3, uvicorn 0.38, redis 7.1.0, alembic 1.13.1, psycopg2-binary 2.9.9 | — | — | **2.0.23** | — | Apache-2.0 (`PAKTON/LICENSE`) | `API/requirements.txt:1-13` |
| **PAKTON Archivist** | (3.11) | langgraph 0.3.5, langgraph-checkpoint-postgres 2.0.21, pinecone 5.4.2, langchain-chroma 0.2.2, psycopg[binary]≥3.2.12 | **0.3.20 / 0.3.41** | **2.10.6** | — | — | Apache-2.0 | `Archivist/requirements.txt:1-21` |
| **PAKTON Researcher** | (3.11) | sentence-transformers 5.1.2, FlagEmbedding 1.3.5, llama-index 0.12.42, numpy 1.26.4, cohere 5.20 | 0.3.20 / 0.3.41 | 2.10.6 | — | **2.9.1** | Apache-2.0 | `Researcher/requirements.txt:1-44` |
| **eyecite** | **≥3.10** | pure lib | — | — | — | — | **BSD-2-Clause** | `eyecite/pyproject.toml:18,37-44` |
| **cobalt** | **≥3.12** | pure lib (iso8601, lxml<6) | — | — | — | — | **LGPLv3+** | `cobalt/pyproject.toml:13-27` |
| **bluebell** | **≥3.12** (Rust `abi3-py312`) | Rust+pyo3 0.29 wheel; dep cobalt≥9, lxml | — | — | — | — | **LGPLv3+** | `bluebell/pyproject.toml:12-28`, `crates/bluebell-python/Cargo.toml:15` |
| **indigo** | **≥3.12** | **Django ~=5.0**, DRF, bluebell-akn≥5, docpipe, boto3 | — | — | — | — | **LGPLv3** | `indigo/pyproject.toml:14,32-78` |
| **legalbenchrag** | **3.12** (pip-compile) | faiss-cpu 1.8, **sqlite-vec 0.1.1**, **diskcache 5.6.3**, anthropic 0.32, cohere 5.6.2, voyageai | **0.2.13 / 0.2.30** | **2.8.2** | **2.0.32** | — | **MIT** | `legalbenchrag/requirements.txt:2,43,92-94,134,178,180` |
| **LeSICiN** | unspecified (no manifest) | script | — | — | — | **torch + torch_sparse** | **NONE** | imports in `model/*.py`; `run.py` |
| **LegalGraphRAG** | unspecified | script, networkx, transformers≥4.51, openai | — | — | — | **≥2.6.0** | **NONE** | `LegalGraphRAG/requirements.txt:2-13` |
| **L-MARS** | unspecified | langchain-openai 0.3.35, openai, pdfplumber, nltk | **0.3.27** / — | — | — | — | **NONE** | `L-MARS/requirements.txt:1-11` |

Verified no-LICENSE: `ls LeSICiN LegalGraphRAG L-MARS` → none contains a licence file; only PAKTON carries one (Apache-2.0).

---

## 2. Per-repo verdicts (concrete)

### 2.1 PAKTON — the backbone. VERDICT: WIRE-AS-LIB (runtime skeleton) + REMODEL the engine seam.
PAKTON genuinely gives the topology we want: FastAPI gateway → Celery (RabbitMQ broker, Redis
backend) → SQLAlchemy 2.0 + Alembic, plus a langgraph Postgres checkpointer and a Pinecone/Chroma
vector store (confirmed in `w5-backend.md §10` against `API/docker-compose.yml:11-95`,
`API/api.py`, `API/tasks.py`, `Archivist/.../agent.py`). Lifting the **mechanics** (session
context-manager, Celery wiring, SSE step/tool streaming, retry, warm-worker, Alembic) bolts on
cleanly because they are framework-generic.

**Where it fights our assumptions — three structural gaps, each confirmed by grep in `w5-backend.md
§10`:**
1. **No multi-tenancy / RBAC.** `conversations` is keyed by `user_email` only; `role` exists on the
   JWT (`auth.py:24`) but is never used to authorize. Our schema needs `tenant_id NOT NULL` on every
   client table + RLS + per-tenant KMS. This is net-new and must thread through, not bolt on.
2. **No effectivity / tenant filter in retrieval.** The retriever contract is literally
   `retrieve(self, query: str, **kwargs) -> List[Document]` (`Researcher/.../retrievers/base.py`):
   no `as_of`, no `valid_from/valid_to`, no namespace. Our `RetrievalService` must add both predicates
   on every query — the single most repeated net-new change (see `retrieval-and-storage-mechanisms.md
   §0`).
3. **LangChain `Document` model everywhere.** `Archivist/.../indexers/vectordb.py:12` imports
   `langchain_core.documents.Document`; `index(docs: List[Document])` (`:110`). PAKTON's unit of
   retrieval is an opaque `Document(page_content, metadata)` blob. Our canonical unit is a relational
   `chunk(unit_version_id FK, embedding VECTOR(1024), struct_header)` tied to bitemporal
   `unit_version` (W2 §2). **Impedance:** the glue must translate `chunk + unit_version` → `Document`
   at the `RetrievalService` boundary and never let the opaque Document become the source of truth.

**Fit verdict:** effectivity + multi-tenant + canonical schema do NOT bolt onto PAKTON cleanly as
code — but they bolt onto its *shape* cleanly. Take the runtime skeleton as a library/starter; replace
the Archivist/Interrogator/Researcher engine guts with our grounding loop behind the interfaces.
Python 3.11 base is fine for the runtime itself, **but see §3(a): it must be bumped to 3.12** to share
an env with the AKN libraries.

### 2.2 Indigo — Django. VERDICT: REMODEL-PATTERN (cannot co-host).
`indigo/pyproject.toml:32` pins `django~=5.0.0`; it is "A Django application for publishing
legislation" with ~40 Django-ecosystem deps (DRF, django-fsm, django-treebeard, django-reversion).
**It cannot coexist in one FastAPI process:** Django brings its own ORM, settings/app-registry, and
request/response stack that do not share a process model with FastAPI+SQLAlchemy. Running both means
two frameworks, two ORMs, two migration systems — not an integration, a second app.

**Data-model impedance (the real reason to remodel, not run):** Indigo stores the **entire document's
Akoma Ntoso XML in a single column** — `document_xml = models.TextField(...)`
(`indigo/indigo_api/models/documents.py:368`), with `content` as an alias (`:413-418`) and
`self.document_xml = self.doc.to_xml()` (`:560`). Our canonical model is the opposite: a recursive
`unit` tree + per-`unit` bitemporal `unit_version(text, valid_from, valid_to, tx_from, tx_to)`
(W2 §2). Indigo's AKN-XML-in-a-blob and our relational unit_version are structurally opposed; the
only sound seam is to **lift the patterns** — FRBR/bitemporal expression dates, amendment→version FSM,
point-in-time + jurisdiction scoping (`expression_date` ≈ `as_of`, `country/locality` ≈ tenant, per
`retrieval-and-storage-mechanisms.md §0`), the S3/FileSystem blob switch (→ MinIO-VN) — and
reimplement them on W2's schema. W2 §10 already scopes this as a steal-list, not a dependency.

### 2.3 Cobalt — AKN serialization lib. VERDICT: WIRE-AS-LIB (with a Python bump + licence note).
`cobalt/cobalt/uri.py` is pure Python (`import re` only; `class FrbrUri` / `def parse` at `:23,:192`),
and the package depends only on `iso8601` + `lxml<6` (`cobalt/pyproject.toml:24-27`). This is directly
pip-usable as a library for URN parse/serialize — exactly what W2 §1 wants
(`port refs/cobalt/.../uri.py::FrbrUri.parse`). **Two caveats:** (1) `requires-python >= 3.12`
(`:14`) — so adopting cobalt forces the canonical runtime to 3.12, above PAKTON's 3.11 base;
(2) **LGPLv3+** (`:13`) — fine to pip-depend on as an unmodified library (dynamic use), but if we vendor
and modify `uri.py` the copyleft attaches; cleanest is to depend on the published wheel or reimplement
the ~200-line parser.

### 2.4 Bluebell — Rust+Python AKN transformer. VERDICT: WIRE-AS-LIB only if we accept a native wheel; else REMODEL.
`bluebell/pyproject.toml:13-14` requires Python 3.12/3.13; the Python binding is a Rust crate built via
pyo3 0.29 with `abi3-py312` stable-ABI wheels (`crates/bluebell-python/Cargo.toml:15`) and depends on
`cobalt>=9.0.0`. **Embeddable** in principle (one prebuilt wheel per platform), but it introduces a
**Rust toolchain + maturin build** into our pipeline unless we consume a published wheel, and it is
**LGPLv3+**. W2 only wants the **stable-eId idea** (`bluebell/.../eid.rs`), not the transformer engine.
Recommendation: treat the eId-generation convention as a REMODEL-PATTERN (a few rules), and only
WIRE-AS-LIB if we genuinely need bidirectional AKN text↔XML — which TraLuat's relational model does
not require.

### 2.5 eyecite — citation extractor. VERDICT: WIRE-AS-LIB for the *engine*, REBUILD-FOR-VN for the *data*.
The cleanest merge: pure Python, **BSD-2-Clause** (`eyecite/LICENSE`), `requires-python >= 3.10`
(compatible with 3.11 and 3.12), deps are all lightweight (`lxml`, `pyahocorasick`, `regex`,
`reporters-db`, `courts-db`, `fast-diff-match-patch` — `pyproject.toml:37-44`). No pydantic/langchain/
torch, so **no version clash with anything**. The Aho-Corasick prefilter + antecedent/`id.`/`supra`
resolution is directly reusable (`retrieval-and-storage-mechanisms.md §B.1` linking row). **But** its
pattern DB is US (`reporters-db`, `courts-db`): the extraction *engine* installs and runs, while the
Vietnamese citation patterns (Điều/Khoản/Điểm, "Điều này", "nêu trên") must be **rebuilt** —
reporters_db → VN pattern set. So: lib-merge the algorithm, rebuild the data.

### 2.6 legalbenchrag — RAG eval harness. VERDICT: RUN-AS-SEPARATE-SERVICE.
Useful bits (`sqlite-vec` 0.1.1, `diskcache` 5.6.3 content-hash caching, span-preserving RCTS chunking)
are called out as ADOPT in `retrieval-and-storage-mechanisms.md §B.1`. **But it cannot share the
PAKTON env:** it pins `langchain==0.2.13` / `langchain-core==0.2.30` (`requirements.txt:92-94`) against
PAKTON's `0.3.20 / 0.3.41` — a **major-version break** (0.2→0.3 moved modules and changed APIs). It also
pins `pydantic==2.8.2` vs PAKTON's `2.10.6` and `sqlalchemy==2.0.32` vs `2.0.23`. These are
unsatisfiable together. Keep it as an **isolated eval venv/service** that reads our corpus and writes
metrics; port the *ideas* (sqlite-vec→pgvector, diskcache keying) into our retrieval code rather than
importing the harness. License (MIT) is friction-free.

### 2.7 LeSICiN — heterogeneous-graph statute identification. VERDICT: REBUILD-PATTERN only.
**No LICENSE file** → the code is legally unmergeable; the pattern must be clean-reimplemented.
Independently, the code is heavy ML: `import torch` + `import torch_sparse` with a HAN text encoder and
MAGNN metapath aggregation (`model/model.py:34,56`, `model/submodules.py:101-120`). `torch_sparse` is
the worst dependency in the set — it requires wheels ABI-matched to the exact torch/CUDA build and
routinely fails to install against an arbitrary torch (here it would fight the reranker's torch 2.9.1).
The data format is JSONL + pickle, IPC-specific. W2 §5.2 already decides to keep only the *inductive
matching idea* (encode new judgment text with bge-m3, bi-encoder + cross-encoder match to unit nodes,
plus effectivity filter the repo lacks) and NOT the code. Confirmed: REBUILD-PATTERN.

### 2.8 LegalGraphRAG / L-MARS — no-LICENSE. VERDICT: REBUILD-PATTERN only.
Both lack any LICENSE → cannot be merged as code; reimplement the patterns.
- **LegalGraphRAG:** `torch>=2.6.0` + `transformers>=4.51` + `networkx` (`requirements.txt:2-7`). Useful
  patterns = 4-tier KG construction + concept/charge-anchored retrieval + bge-m3 local embeddings
  (`retrieval-and-storage-mechanisms.md §B.1`), to be rebuilt on the **persistent, dated** AGE graph,
  not its in-memory NetworkX/single-pickle store.
- **L-MARS:** `langchain==0.3.27` (`requirements.txt:1`) — notably this *would* be
  env-compatible with PAKTON's 0.3.x line, the one repo besides PAKTON that is. But with no licence,
  the only safe path is to lift the **temporal-routing + abstain-gate idea** (`router.py` temporal
  invalidation, aggregator confidence gate) and reimplement.

---

## 3. Cross-cutting integration risks

**(a) Python version + dependency conflicts across the pip-mergeable pieces.**
- **Python floor split is real:** PAKTON runs on **3.11.11** (`API/Dockerfile:10`), but cobalt,
  bluebell, indigo and legalbenchrag all require **≥3.12** (`cobalt/pyproject.toml:14`;
  `bluebell` abi3-py312; `indigo/pyproject.toml:14`; legalbenchrag pip-compiled for 3.12). eyecite is
  ≥3.10 (fine). **Resolution:** set the canonical runtime to **Python 3.12** — it satisfies everything
  that could possibly share an env (PAKTON runtime, eyecite, cobalt) and is only a minor bump for
  PAKTON.
- **langchain 0.2 vs 0.3 is the hard wall:** PAKTON `0.3.20`/core `0.3.41` vs legalbenchrag
  `0.2.13`/core `0.2.30`. No single env satisfies both. L-MARS `0.3.27` is the only other 0.3.x.
- **pydantic:** everyone is on **v2** — there is **no v1/v2 schism to fear** (the task's worry does not
  materialize). The only friction is pin drift within v2 (2.8.2 legalbenchrag vs 2.10.6 PAKTON), which
  only bites if you literally union the requirements; behind a service boundary it is a non-issue.
- **torch:** three different expectations — PAKTON Researcher `torch==2.9.1` (for sentence-transformers
  + FlagEmbedding reranker), LegalGraphRAG `>=2.6.0`, LeSICiN `torch + torch_sparse`. `torch_sparse` is
  the one that will not co-install. Since LeSICiN/LegalGraphRAG are REBUILD-PATTERN anyway, the runtime
  only needs the reranker's torch — keep it on the (heavy) engine worker image, not the API image.

**(b) Framework conflict (Django vs FastAPI).** Indigo is Django 5; PAKTON is FastAPI. They cannot
share a process, ORM, or migration system. One framework must win — it is **FastAPI + SQLAlchemy**
(PAKTON). Indigo contributes patterns only (§2.2).

**(c) Data-model impedance — where the glue needs real transformation (not an import):**
- **Indigo AKN-XML-in-a-column** (`documents.py:368` whole-doc `document_xml` TextField) **vs our
  relational `unit`/`unit_version` tree** (W2 §2). Transformation: parse AKN → explode into unit tree +
  bitemporal versions. This is W1→W2 ingestion work, not a dependency.
- **eyecite citation objects (US reporter model) vs our `norm_relation`** (W2 §2, relation_type ∈
  {cites, amends, …}). The linker returns resolved spans; glue must map resolved citations → canonical
  `unit_eid` so `norm_relation` edges and effectivity run on IDs, not strings
  (`retrieval-and-storage-mechanisms.md §B.1`).
- **LeSICiN heterogeneous-graph + metapath/pickle format vs Apache AGE** (W2 §5.1-5.2). No format
  bridge exists; the graph is rebuilt in AGE from `norm_relation`.
- **PAKTON LangChain `Document`/chunk-metadata vs our `chunk`+`unit_version`** (§2.1). Glue translates
  at the `RetrievalService` boundary; the relational row stays the source of truth.

**(d) Language mismatch (US / Chinese / Indian patterns → VN rebuild).** eyecite (US reporters),
LeSICiN (Indian IPC), LegalGraphRAG (charge-anchored, non-VN), legalbenchrag (English-tokenized BM25:
`PAKTON bm25.py query.split()`, L-MARS English stopwords — both under-retrieve Vietnamese per
`retrieval-and-storage-mechanisms.md §B.1`). Every data/pattern DB is foreign; the **engines port, the
data is REBUILD-FOR-VN** (VN splitter Điều/Khoản/Điểm, VN citation patterns, pyvi/underthesea + unaccent
analyzer, bge-m3 multilingual embeddings).

**(e) License.** LeSICiN, LegalGraphRAG, L-MARS carry **no LICENSE** → their code cannot be copied into
the product; only clean reimplementation of the ideas is lawful. cobalt/bluebell/indigo are **LGPLv3+**
→ safe to pip-depend on unmodified (dynamic use), but vendoring+modifying triggers copyleft — so prefer
the published wheel or a from-scratch port of the small pieces we need (uri.py, eId rules).
eyecite (BSD-2) and legalbenchrag (MIT) are permissive and friction-free. PAKTON is Apache-2.0 — safe to
lift and modify with attribution.

**(f) Runtime-state mismatch.** The repos assume state models our runtime forbids:
- **Global retrieval, no tenant/effectivity:** 6/7 repos query global with no `as_of`/`tenant`
  predicate (`retrieval-and-storage-mechanisms.md §0`; PAKTON `retrieve(query, **kwargs)`). Our
  invariant is the opposite — every query carries `as_of` + `tenant`, and the LLM gateway refuses
  cross-tenant chunks (`w5-backend.md §2.3, §6`). A literal lift is silently wrong on both correctness
  and isolation.
- **In-memory/disposable graph (LegalGraphRAG single pickle, LeSICiN torch_sparse) vs persistent dated
  AGE** (W2 §5). 
- **Stateless component (eyecite) — fine**; **stateful warm-agent (PAKTON per-worker global
  `archivist`)** must stay stateless w.r.t. tenant: tenant/as_of ride task args, never the warm
  instance (`w5-backend.md §1`).

---

## 4. Seam / verdict table

| Repo | What we take | Integration seam (maps to) | Verdict | Concrete risk if merged naively |
|---|---|---|---|---|
| **PAKTON** | FastAPI+Celery+SQLAlchemy+Alembic skeleton, SSE, retry, warm-worker, checkpointer, vector wiring | becomes the ONE runtime; engine guts replaced behind `RetrievalService`/`GroundingService`/`LLMGateway` | **WIRE-AS-LIB** (skeleton) + **REMODEL** (engine) | No tenant/RBAC and no `as_of`/tenant filter in `retrieve(query,**kwargs)`; LangChain `Document` blob becomes de-facto SoR → isolation + effectivity silently violated |
| **Indigo** | FRBR/bitemporal pattern, amendment→version FSM, point-in-time+jurisdiction scoping, blob S3-switch | patterns reimplemented on W2 `unit`/`unit_version`/`norm_relation` | **REMODEL-PATTERN** | Django 5 can't co-host FastAPI; whole-doc `document_xml` TextField (`documents.py:368`) opposes relational unit_version |
| **cobalt** | `FrbrUri.parse` URN parse/serialize | `TemporalRepository` URN layer (W2 §1) | **WIRE-AS-LIB** | Forces Python ≥3.12 (above PAKTON 3.11); LGPL copyleft if vendored+modified |
| **bluebell** | stable-eId convention (idea) | `eid` column rule (W2 §1) | **REMODEL-PATTERN** (WIRE-AS-LIB only if AKN round-trip truly needed) | Rust/maturin build + abi3-py312 (≥3.12) + LGPL dragged in for a feature the relational model doesn't need |
| **eyecite** | Aho-Corasick citation engine + antecedent resolution | VN citation linker → `norm_relation` IDs | **WIRE-AS-LIB** (engine) + **REBUILD-FOR-VN** (patterns) | US reporters_db/courts_db produce zero VN matches; must swap pattern DB |
| **legalbenchrag** | sqlite-vec, diskcache content-hash, span-preserving RCTS chunk | eval harness reading our corpus; ideas ported to pgvector retrieval | **RUN-AS-SEPARATE-SERVICE** | `langchain==0.2.13` clashes with PAKTON 0.3.x (unsatisfiable env); pydantic/sqlalchemy pin drift |
| **LeSICiN** | inductive judgment↔statute matching idea | `LinkingService` (W2 §5.2) rebuilt with bge-m3 + bi/cross-encoder + effectivity | **REBUILD-PATTERN** | No LICENSE (unmergeable); `torch_sparse` won't co-install with reranker torch; IPC/pickle format |
| **LegalGraphRAG** | 4-tier KG + concept/charge-anchored retrieval idea | W2 §5.3 AGE graph (phase 3+) | **REBUILD-PATTERN** + **REBUILD-FOR-VN** | No LICENSE; in-memory NetworkX/single-pickle vs persistent dated AGE; non-VN charge model |
| **L-MARS** | temporal-routing + abstain-gate idea | query-understanding in `RetrievalService` (`retrieval §B.1`) | **REBUILD-PATTERN** | No LICENSE; English stopwords under-retrieve VN |

---

## 5. Recommendations to keep migration safe

1. **One seam only: the canonical schema + the four interface contracts.** `TemporalRepository`,
   `GraphQuery`/`LinkingService` (W2 §6), `RetrievalService`, `GroundingService`, `LLMGateway` are the
   *only* places a lifted pattern touches the system. No repo type (LangChain `Document`, AKN XML blob,
   eyecite citation object, torch graph) may cross those boundaries as the source of truth — the
   relational `unit_version`/`norm_relation`/`chunk` rows are.
2. **Pin the canonical runtime at Python 3.12 + langchain 0.3.x.** This is the only choice that lets
   PAKTON's runtime, eyecite and cobalt share one env. Everything on langchain 0.2 (legalbenchrag) or
   needing `torch_sparse` (LeSICiN) stays out of that env.
3. **Genuinely pip-mergeable = exactly two libraries:** **eyecite** (BSD-2, ≥3.10, no heavy deps) and
   **cobalt** (LGPL, ≥3.12, pure Python). Wire these directly. Everything else is REMODEL/REBUILD or a
   separate service.
4. **Isolate legalbenchrag as an eval service** in its own venv; port sqlite-vec→pgvector and diskcache
   keying as ideas, never import the harness into the engine.
5. **Reimplement — never copy — the three no-LICENSE repos** (LeSICiN, LegalGraphRAG, L-MARS). Keep the
   ideas, write the code fresh.
6. **Add `as_of` + `tenant` to every retrieval/cache call from day one** (the one net-new predicate
   6/7 repos omit); make the LLM gateway cross-tenant refusal and the RLS fail-closed tests
   (`w5-backend.md §7`) part of acceptance so a lifted global-query can't regress isolation.
7. **Keep torch on the engine-worker image only** (reranker needs 2.9.1); the API image stays torch-free.
8. **Treat Django/Indigo as a reading reference, not a runtime dependency** — lift the bitemporal/FRBR
   and blob-switch patterns into W1/W2 code.

---

### Appendix — evidence index (file:line)
- PAKTON Python base: `PAKTON/PAKTON Framework/API/Dockerfile:10` (python:3.11.11-slim).
- PAKTON API deps: `API/requirements.txt:1-13` (celery 5.5.3, fastapi 0.121.3, sqlalchemy 2.0.23, alembic 1.13.1).
- PAKTON engine deps: `Archivist/requirements.txt:1-21`, `Researcher/requirements.txt:1-44` (langchain 0.3.20, langgraph 0.3.5, pydantic 2.10.6, torch 2.9.1, sentence-transformers 5.1.2).
- PAKTON retriever contract: `Researcher/src/Researcher/retrievers/base.py` `retrieve(self, query: str, **kwargs) -> List[Document]`.
- PAKTON LangChain Document: `Archivist/src/Archivist/indexers/vectordb.py:12,110`.
- eyecite: `eyecite/pyproject.toml:13,18,37-44`; `eyecite/LICENSE` (BSD-2).
- cobalt: `cobalt/pyproject.toml:13,14,24-27`; `cobalt/cobalt/uri.py:1,23,192`.
- bluebell: `bluebell/pyproject.toml:12-28`; `bluebell/crates/bluebell-python/Cargo.toml:15` (pyo3 0.29 abi3-py312); `bluebell/Cargo.toml` (LGPL-3.0-or-later).
- indigo: `indigo/pyproject.toml:14,32` (django~=5.0.0, py≥3.12); `indigo/indigo_api/models/documents.py:368,413-418,560` (document_xml TextField).
- legalbenchrag: `legalbenchrag/requirements.txt:2,43,92-94,134,178,180` (langchain 0.2.13, pydantic 2.8.2, sqlalchemy 2.0.32, sqlite-vec, diskcache); `legalbenchrag/LICENSE` (MIT).
- LeSICiN: `model/model.py:34,56`, `model/submodules.py:101-120` (HAN/MAGNN); imports `torch`, `torch_sparse`; no LICENSE.
- LegalGraphRAG: `requirements.txt:2-13` (torch≥2.6, transformers≥4.51, networkx); no LICENSE.
- L-MARS: `requirements.txt:1` (langchain 0.3.27); no LICENSE.
- Canonical schema/runtime: `docs/specs/w2-knowledge-graph.md §1,§2,§5,§6`; `docs/specs/w5-backend.md §1,§2,§6,§7,§10`; `docs/specs/retrieval-and-storage-mechanisms.md §0,§B.1`.
