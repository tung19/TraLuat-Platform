# Permissively-Licensed Repos — Clone & Study Decisions for TraLuat

> Scope note (per coordinator update): this is a REFERENCE/LEARNING phase, not commercial. Verdicts are driven by **architectural / feature learning value**, NOT license. License is recorded as a one-line note for later commercialization. Verdict scale: **[CLONE & STUDY — high learning value] / [SKIM README/PAPER ONLY] / [SKIP — low value]**.
> All repos verified live via `gh api` on 2026-11-05. TraLuat target stack assumed: Python / FastAPI, multi-tenant, needs effectivity-aware RAG, clause-level retrieval, contract review/omission, multi-agent reasoning, bitemporal/AKN data model, citation extraction.

## PAKTON — petrosrapto/PAKTON

### Takeaway
A complete, cleanly-architected open-source multi-agent contract-QA system (EMNLP 2025 oral) built on **LangGraph**, with a real FastAPI+Celery backend, three installable agent packages (Archivist / Interrogator / Researcher), and a hybrid multi-retriever RAG. This is the single highest-value repo in the set for TraLuat — it is a near-blueprint for a multi-agent, multi-stage-RAG legal backend.

### Cited Findings
- Repo is active (pushed 2025-12-08), Apache-2.0, 46 stars, default branch `develop`; language tagged Jupyter but the core is Python. Paper: arXiv 2506.00608 / ACL Anthology 2025.emnlp-main.403 — [GitHub](https://github.com/petrosrapto/PAKTON), [Paper](https://aclanthology.org/2025.emnlp-main.403/)
- README states it is "an open-source, end-to-end framework for automated contract review ... a team of LLM agents working together, along with smart retrieval tools (RAG)", privacy-first / on-premise, modular plug-and-play. Claims SOTA retrieval on LegalBench-RAG and wins over GPT-4o on ContractNLI in human + GEVAL eval — [README](https://github.com/petrosrapto/PAKTON)
- Full backend IS present under `PAKTON Framework/` (not just experiments): `API/` (FastAPI `api.py`, `auth.py`, Celery `tasks.py`, Alembic migrations `alembic/versions/`, SQLAlchemy `database/models/{user,conversation}.py` + `database/repositories/`, SSE streaming test `tests/test_query_sse.py`), plus three agent packages each as a pip-installable `src/<Agent>/` with `setup.py` — [tree](https://github.com/petrosrapto/PAKTON)
- **Archivist** (ingestion/indexing agent): LangGraph `StateGraph` in `graph/builder.py` that runs `parse_and_split` then fans out to indexers **in parallel**; `parser/{naiveParser,structuralParser}.py` (structural = clause/hierarchy-aware splitting); `indexers/{lightrag,vectordb}.py`; `tools/interrogation_tool.py` — [builder.py](https://github.com/petrosrapto/PAKTON/blob/develop/PAKTON%20Framework/Archivist/src/Archivist/graph/builder.py)
- **Interrogator** (reasoning agent): LangGraph nodes `generate_question.py → get_answer.py → refine_answer.py → write_report.py` (+ `router.py`, `save_interrogation.py`) — an iterative self-questioning / answer-refinement loop that produces an explainable report — [tree](https://github.com/petrosrapto/PAKTON)
- **Researcher** (RAG agent): nodes `query_extractor → tools → reranking → response_generator`; pluggable `retrievers/{bm25,hybrid,vectordb,lightrag,web,wikipedia}.py` with a `base.py` interface; has real tests (`tests/test_retrievers.py`, `test_graph.py`) — [tree](https://github.com/petrosrapto/PAKTON)
- Each agent ships `utils/prompts.py`, `models/{openai,bedrock,google,local,bert}.py` (provider abstraction incl. local models), `types/state.py` (typed LangGraph state), `config.example.yaml` — a consistent, copyable package layout — [tree](https://github.com/petrosrapto/PAKTON)
- The `Experiments and Evaluation/.../experimentsLibrary/src/experimentsLibrary/multiAgentFramework.py` is only a thin HTTP client (polls Celery `task_status`, hits `/interrogation/` and `/index_document`) — confirms the agents run behind the FastAPI service, not inline — [multiAgentFramework.py](https://github.com/petrosrapto/PAKTON)
- Caveat: README warns "the deployed version and the code currently in the repository are missing a few components that will be added shortly" — verify completeness before relying on any single module — [README](https://github.com/petrosrapto/PAKTON)

### Inferences (mapping to TraLuat + verdict)
- Maps to nearly every TraLuat need: multi-agent reasoning (Interrogator), multi-stage RAG with hybrid BM25+vector+graph retrieval and a dedicated rerank node (Researcher), clause/structure-aware ingestion (Archivist structuralParser + parallel indexers), and contract review/omission (the generate→refine→report loop is directly adaptable to "what obligations/clauses are missing?").
- Architecturally the best fit of the set: already Python + FastAPI + Celery + SQLAlchemy/Alembic, provider-abstracted (swap in Vietnamese-capable models), each agent a standalone package you can lift individually. The LangGraph node-per-step pattern and the retriever `base.py` interface are the most directly copyable designs.
- **FINAL VERDICT: [CLONE & STUDY — high learning value]** — a working reference architecture for exactly TraLuat's shape; mine the LangGraph agent packaging, the hybrid-retriever+rerank Researcher, and the FastAPI/Celery/SSE service layer. (License note: Apache-2.0 — permissive, attribution + NOTICE if reused later.)

## Claude for Legal — anthropics/claude-for-legal

### Takeaway
Anthropic's official suite of legal-workflow **plugins/skills** (Markdown instructions + light Python), not an application or RAG engine. High value as a *prompt-engineering / workflow-decomposition* reference and a skill-schema template; near-zero value as reusable backend code.

### Cited Findings
- Very active (pushed 2026-11-03), Apache-2.0, ~9.9k stars, small (1.6 MB), language tagged Python. Described as "A suite of plugins for legal workflows" — [GitHub](https://github.com/anthropics/claude-for-legal)
- It is plugin/skill content (Claude Code / Cowork style: SKILL.md + supporting markdown/JSON + small scripts), i.e. structured instructions that decompose legal tasks (e.g. contract review checklists, playbooks) rather than a server — [GitHub](https://github.com/anthropics/claude-for-legal)

### Inferences (mapping to TraLuat + verdict)
- Value for TraLuat: the **skill/playbook markdown+JSON schema** and the way each legal workflow is decomposed into steps/checklists — directly reusable as the content layer for TraLuat's contract-review and omission-detection agents (what to look for, how to phrase findings), independent of runtime.
- It is Claude-Cowork/Claude-Code-oriented, not a FastAPI component; nothing to clone into a backend. Treat as a corpus of prompt/playbook patterns to study and re-encode.
- **FINAL VERDICT: [SKIM README/PAPER ONLY]** — read the skills/playbooks for workflow decomposition and finding-phrasing patterns; do not expect reusable engine code. (License note: Apache-2.0.)

## LegalBench-RAG — zeroentropy-ai/legalbenchrag

### Takeaway
A compact (68 KB), MIT-licensed legal **retrieval benchmark harness** whose real asset is its **character-span ground-truth model** enabling deterministic precision/recall at the exact character level, plus a clean reference RAG pipeline (span-tracked chunking → embeddings in sqlite-vec → optional Cohere rerank → top-k). Dormant (last push 2025-05-30) but that is fine for an eval harness.

### Cited Findings
- MIT code / CC BY 4.0 data; 219 stars; purpose: "evaluate any retrieval system against complex legal contract understanding questions ... deterministically compute precision and recall, even at the exact character level" — [README](https://github.com/zeroentropy-ai/legalbenchrag)
- Ground-truth model: each benchmark test case has a query and ground-truth **snippets**, each referencing a corpus file path + a **character index range** — this is what makes clause-level/character-level scoring possible (`benchmark_types.py`: `Document`, `QueryResponse`, `RetrievedSnippet`) — [README](https://github.com/zeroentropy-ai/legalbenchrag)
- Reference pipeline `methods/baseline.py`: two chunkers — `naive` (fixed window) and `rcts` (LangChain `RecursiveCharacterTextSplitter` with legal-aware separator list), both **preserving exact character spans** (asserts chunks reconstruct the document); chunks + embeddings stored in **sqlite-vec**; OpenAI `text-embedding-3-large`; optional Cohere `rerank-english-v3.0` — [baseline.py](https://github.com/zeroentropy-ai/legalbenchrag/blob/master/legalbenchrag/methods/baseline.py)
- `methods/retrieval_strategies.py`: a Cartesian sweep over chunk strategy × chunk size × rerank on/off × `top_k ∈ {1,2,4,8,16,32,64}` (embedding_topk jumps to 300 when reranking) — a ready template for tuning retrieval — [retrieval_strategies.py](https://github.com/zeroentropy-ai/legalbenchrag/blob/master/legalbenchrag/methods/retrieval_strategies.py)
- `benchmark.py` reports avg recall/precision overall and per sub-benchmark (ContractNLI, CUAD, MAUD, PrivacyQA); `utils/ai.py` wraps embedding + rerank providers; `generate/` reconstructs benchmarks from source datasets using LLMs — [benchmark.py](https://github.com/zeroentropy-ai/legalbenchrag/blob/master/legalbenchrag/benchmark.py)

### Inferences (mapping to TraLuat + verdict)
- Directly serves TraLuat's **clause-level retrieval** and **effectivity-aware RAG eval**: adopt the character-span snippet model as TraLuat's own retrieval ground-truth format, reuse the span-preserving chunker (critical for exact clause citation back to source), and reuse the strategy-sweep harness to tune Vietnamese-legal retrieval. The precision/recall-at-character-level methodology is the main lesson.
- Small, pure-Python, async, framework-agnostic — trivially fits a FastAPI backend as an offline eval module. Datasets are US/English; the *harness and data model* transfer, the corpus does not.
- **FINAL VERDICT: [CLONE & STUDY — high learning value]** — small and directly minable; lift the span-based ground-truth model, span-tracked chunking, and the retrieval-tuning sweep for TraLuat's own eval. (License note: MIT code / CC BY 4.0 data — attribution.)

## eyecite — freelawproject/eyecite

### Takeaway
A mature, actively-maintained (v2.7.8, pushed 2026-11-01) BSD-2 pure-Python citation-extraction library, battle-tested on 55M+ US citations (CourtListener, Caselaw Access Project). The extraction DB is US-specific and NOT reusable for Vietnam, but the **4-stage pipeline architecture** (clean → tokenize → find → resolve → annotate) is an excellent blueprint for building a Vietnamese legal-citation extractor.

### Cited Findings
- 300 stars, BSD-2-Clause, published in JOSS (2021). Extracts full-case, short, id., supra, statutory, law-journal citations from US legal text — [README](https://github.com/freelawproject/eyecite)
- Four core functions, each a module: **Extraction** `find.py` (`get_citations()`), **Aggregation** `resolve.py` (resolves `supra`/`id.`/short cites to logical antecedents), **Annotation** `annotate.py` (wraps each citation with custom markup via a fast diffing algorithm — span-preserving), **Cleaning** `clean.py` (text preprocessing) — [README](https://github.com/freelawproject/eyecite)
- Clean module layout: `tokenizers.py`, `regexes.py`, `models.py` (citation dataclasses), `helpers.py`, `resolve.py`, `test_factories.py`, `py.typed` — small, typed, well-factored — [tree](https://github.com/freelawproject/eyecite/tree/main/eyecite)
- Dependencies reveal the design: `courts-db` + (separately) `reporters-db` = the US reporter/court knowledge base driving regexes; `pyahocorasick` (Aho-Corasick multi-pattern tokenizer for speed); `regex`; `fast-diff-match-patch` (powers annotation without corrupting offsets); `lxml` — [pyproject.toml](https://github.com/freelawproject/eyecite/blob/main/pyproject.toml)

### Inferences (mapping to TraLuat + verdict)
- Maps to TraLuat's **citation extraction** and **clause-level linking**: the separation of a *data-driven pattern DB* (reporters-db/courts-db) from the *engine* (find/resolve/annotate) is the key lesson — TraLuat would build a Vietnam equivalent (Luật/Nghị định/Thông tư/Điều/Khoản/Điểm patterns) and reuse the pipeline shape, the Aho-Corasick tokenizer approach, the id./supra antecedent-resolution model, and the span-preserving annotation (so citations link back to exact source offsets).
- Pure-Python library, drops into FastAPI cleanly. Only the US regex/DB content is non-transferable.
- **FINAL VERDICT: [CLONE & STUDY — high learning value]** (as an architecture/pattern reference) — study the clean→tokenize→find→resolve→annotate pipeline and the data-vs-engine split; rebuild the pattern DB for Vietnamese law rather than reusing the US one. (License note: BSD-2-Clause — attribution.)

## Indigo — laws-africa/indigo (+ Cobalt / Bluebell)

### Takeaway
A mature Django platform for managing, consolidating and publishing legislation in **Akoma Ntoso**, whose data model is a textbook implementation of the **FRBR Work/Expression** pattern with first-class amendments and **point-in-time consolidation** — i.e. exactly the bitemporal / effectivity-aware model TraLuat needs. Study the *data model and consolidation logic*, not the Django/HTML app shell. Note: the LICENSE is actually **LGPL-3.0**, not GPL-3.

### Cited Findings
- Canonical repo is `laws-africa/indigo` (`Code4SA/indigo` redirects there); active (pushed 2026-10-29), 78 stars. LICENSE text is the **GNU Lesser General Public License v3** ("LGPL-3.0"), which GitHub reports as NOASSERTION — [LICENSE](https://github.com/laws-africa/indigo/blob/main/LICENSE)
- Django app built on **Cobalt** (lightweight Python Akoma Ntoso library) and **Bluebell** (generic AKN 3 parser "supporting all hierarchical elements and multiple document types") + django-rest-framework. (Bluebell is the current parser; "Slaw" was the older Ruby parser, now superseded.) — [README](https://github.com/laws-africa/indigo)
- Django apps: `indigo_api` (models + REST), `indigo_app` (UI), `indigo_content_api`, `indigo_resolver` (FRBR-URI resolution), `indigo_social`, `indigo_za` (country specifics), `indigo_lib` — [tree](https://github.com/laws-africa/indigo)
- **Work/Expression data model** (`indigo_api/models/`): `works.py` defines `Work` = the abstract law keyed by **FRBR URI** (`cobalt.FrbrUri`), with lifecycle events `publication_date`, `main_commencement`/`commencement_date`, `repealed_date`/`repealed_by` (`cobalt.RepealEvent`), assent; `expressions()` returns point-in-time versions ordered by `expression_date`; `possible_expression_dates()` computes which dates are initial/amendment/consolidation — [works.py](https://github.com/laws-africa/indigo/blob/main/indigo_api/models/works.py)
- **Amendment** model (`amendments.py`): links `amending_work` → `amended_work` with a `date` ("Date on which the amendment comes into operation") and a `verb`; a `post_save` signal materializes a new document expression at that date; `update_date_for_related` cascades date changes to documents and tasks — [amendments.py](https://github.com/laws-africa/indigo/blob/main/indigo_api/models/amendments.py)
- **Document = Expression** (`documents.py`): each `Document` is an expression of a Work at a specific `expression_date` + `language`; `get_for_frbr_uri` supports point-in-time lookup (`expression_date__lte` then latest) and language fallback; `commencements_relevant_at_expression_date` and `all_commenceable_provisions(expression_date)` give **provision/clause-level commencement** (parts of a law effective at different dates) — [documents.py](https://github.com/laws-africa/indigo/blob/main/indigo_api/models/documents.py)
- Also `models/citations.py`, `models/places.py` (jurisdiction/locality), `models/tasks.py` (editorial workflow), `timeline.py` (commencement/repeal timeline rendering) — [tree](https://github.com/laws-africa/indigo)

### Inferences (mapping to TraLuat + verdict)
- This is the clearest real-world reference for TraLuat's **bitemporal / AKN data model and effectivity-aware retrieval**: separate the abstract law (Work, FRBR URI) from its point-in-time consolidated text (Expression at `expression_date`); model amendments as first-class relations carrying an operation date; derive "the law as it stood on date D" by selecting the latest expression ≤ D; support provision-level commencement so different Điều/Khoản can take effect on different dates. These patterns are framework-independent and map cleanly onto a FastAPI + SQLAlchemy schema.
- Adoption effort is "study & re-model," not clone: it is a full Django/HTML application (multi-app, bower/webpack frontend, django-rest-framework), so TraLuat would re-implement the Work/Expression/Amendment model and point-in-time query logic rather than run Indigo. Cobalt (AKN serialization) and Bluebell (AKN parser) are the more directly reusable Python libraries if TraLuat adopts Akoma Ntoso as its interchange format.
- **FINAL VERDICT: [CLONE & STUDY — high learning value]** — clone for the Work/Expression/Amendment data model, point-in-time consolidation, and provision-level commencement logic; re-model into FastAPI/SQLAlchemy rather than adopting the Django app. Evaluate Cobalt + Bluebell separately as AKN libs. (License note: LGPL-3.0 — weaker copyleft than GPL; using it/Cobalt/Bluebell as an unmodified library server-side does not force open-sourcing TraLuat, but modifications to Indigo/Cobalt/Bluebell themselves must be shared and dynamic-linking/replaceability obligations apply. None are AGPL, so the network-use trigger does not apply. Re-implementing the *patterns* from scratch carries no copyleft obligation. Revisit at commercialization.)

## usgpo/uslm — US Legislative Markup XML schema

### Takeaway
The official US Government **XSD schema** for legislative XML plus sample bills and review/user guides — public-domain/CC0, reference material only. An alternative/comparison point to Akoma Ntoso for modeling legislative structure; no code to reuse.

### Cited Findings
- Public domain under 17 U.S.C. 105, additionally waived worldwide via **CC0 1.0** — "copy, modify, distribute ... even for commercial purposes, all without asking permission" — [LICENSE.md](https://github.com/usgpo/uslm/blob/main/LICENSE.md)
- Contents are `USLM.xsd` (the schema), numerous review/user guides (PDF + Markdown, up to v2.1.x / CSS v2.40 dated 2026-09-04), and a large folder of real sample bill XML (`bill-version-samples-september-2024/`) — [tree / README](https://github.com/usgpo/uslm)
- `major.minor.point` versioning where minor = breaking change; actively maintained by the GPO / US Legislative Branch XML Working Group — [README](https://github.com/usgpo/uslm)

### Inferences (mapping to TraLuat + verdict)
- Relevance to TraLuat is as a *comparative schema study* for the AKN/legislative data model: how a national legislature models hierarchy (title/section/subsection), versions, and metadata. Akoma Ntoso (via Indigo/Cobalt) is the more internationally-standard choice and the better primary reference; USLM is a secondary comparison for schema-design ideas and effectivity/version attributes.
- No application, no Python, nothing to clone into a backend — it is a schema + samples.
- **FINAL VERDICT: [SKIM README/PAPER ONLY]** — read the XSD and a few sample bills as a comparative schema reference; prefer Akoma Ntoso as TraLuat's primary model. (License note: Public domain / CC0 — no obligations.)

## Gaps / caveats
- PAKTON README itself warns some components may be missing from the current push; confirm each module compiles/loads before depending on it.
- I inspected file trees + READMEs + key module source via `gh api` (not a full clone/run of each repo); runtime behavior, test pass rates, and exact PAKTON completeness were not executed.
- LegalBench-RAG is dormant (no commits since May 2025) — acceptable for a benchmark but it will not track new embedding/rerank APIs.
- Indigo license was reported by the task as GPL-3 but the actual LICENSE file is LGPL-3.0; treat the copyleft reach accordingly (and re-verify Cobalt/Bluebell licenses individually before any commercial reuse).
