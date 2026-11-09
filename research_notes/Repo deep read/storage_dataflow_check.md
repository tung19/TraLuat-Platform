# Storage & Data-Flow Verification Pass

Verification date: 2026-11-05
Scope: How the 6 reference repos ACTUALLY process & store data, vs TraLuat's proposed storage design.
Method: READ-only source inspection. Nothing was built/run. Paths + line numbers cited.

TraLuat proposed storage design being checked:
- Postgres = single system-of-record, incl. bitemporal `unit_version` (valid_from/valid_to/tx_from/tx_to)
- pgvector for embeddings (clause-level chunks)
- Apache AGE (openCypher graph ON Postgres) for norm/linking graph
- Object storage (MinIO/S3) for raw PDF blobs
- Derived indexes (vector, graph) rebuildable from Postgres SoR
- Per-tenant isolation; shared read-only legal KB vs isolated client data

---

## 1. PAKTON (refs/PAKTON)

**3-store split: CONFIRMED.**

**(a) SQL metadata — SQLAlchemy on plain Postgres.**
- `PAKTON Framework/API/database/config.py:10-37` — SQLAlchemy `create_engine(DATABASE_URL)`, `declarative_base()`, session factory. `init_db()` (`:79-87`) does `Base.metadata.create_all` (dev); prod uses Alembic.
- Models are thin metadata tables, NOT document content:
  - `API/database/models/conversation.py:15-28` — `Conversation`: PK `thread_id` (String), FK `user_email`, `title`, `message_count`, timestamps.
  - `API/database/models/user.py` + `repositories/` (user_repository, conversation_repository).
- Postgres image = `postgres:15-alpine` (`API/docker-compose.yml:84`, `deployment/development/docker-compose.dev.yml`). **Plain Postgres — NO pgvector extension image, no vector column types anywhere.**

**(b) LangGraph checkpointer — AsyncPostgresSaver. CONFIRMED.**
- `Archivist/src/Archivist/agent.py:14` imports `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`.
- `agent.py:118-137` `_setup_postgres_checkpointer()`: `AsyncPostgresSaver.from_conn_string(DATABASE_URL)` + `await checkpointer.setup()` (auto-creates LangGraph's own checkpoint tables). Falls back to no-persistence on failure (`:136`). `MemorySaver` used as default/fallback (`agent.py:12,145`; `graph/builder.py:14,109`). Researcher/Interrogator agents use `MemorySaver` only (`Researcher/.../agent.py:13,119`).
- docker-compose comment: Postgres is "for persistence of the conversations of the Archivist" (`API/docker-compose.yml:79`). So one Postgres instance serves BOTH the SQLAlchemy metadata tables AND the LangGraph checkpoint tables.

**(c) Vector store — DEDICATED, selectable Pinecone OR ChromaDB. CRUCIAL finding.**
- `Archivist/src/Archivist/indexers/vectordb.py:1-8` docstring: "Supports both Pinecone and ChromaDB". `:32-55` selects via config `indexers.vectordb.use_vector_store` ("pinecone" | "chroma").
  - Pinecone branch `:63-77` (`langchain_pinecone.PineconeVectorStore`, remote managed service).
  - Chroma branch `:79-103` (`langchain_chroma.Chroma`, `persist_directory` default `/chroma_db`).
- Config default = chroma: `Archivist/.../config.example.yaml:14-30` (`use_vector_store: "chroma"`, persist_directory `/chroma_db`, HNSW params).
- Chroma persisted to a **Docker volume `chroma_data:/chroma_db`** (`API/docker-compose.yml:48,82,96`), i.e. a separate on-disk store, NOT Postgres.
- Indexing: `index()` `:110-138` upserts LangChain `Document` objects (embedded via OpenAI `text-embedding-3-large`, `:42-46`). Chunks keyed by the vector store's own auto IDs; `delete_all()` wipes on each re-index (`:121,140-166`).
- **=> PAKTON does NOT use pgvector. It uses a dedicated vector DB (Chroma on disk, or Pinecone SaaS).**

**(d) Graph — via LightRAG (optional), NOT Apache AGE.**
- `Archivist/src/Archivist/indexers/lightrag.py:21-53` — `LightRAGIndexer` POSTs documents to an external LightRAG server (`base_url` default `http://localhost:9621`, `config.example.yaml:32-35`). LightRAG internally builds its own knowledge-graph + vector storage; PAKTON treats it as a black-box HTTP service (upload/delete/poll — `:104-233`). No graph stored in Postgres; no AGE/Cypher.

**How documents/chunks are keyed/stored:** raw conversation metadata in Postgres (keyed by `thread_id`); agent state/messages in LangGraph checkpoint tables (keyed by `thread_id`); embedded chunks in Chroma/Pinecone (dedicated); optional graph inside LightRAG service. **Four physical stores, none of them pgvector or AGE.**

---

## 2. Indigo (refs/indigo)

**Storage: Django ORM on plain Postgres 13. AKN XML stored WHOLE in a text column. Relational FKs only — no graph DB, no vectors.**

- DB config: `indigo/settings.py:184-195` via `dj_database_url`; `docker-compose.yml:12,15` `DATABASE_URL=postgres://...`, image `postgres:13` (plain — no pgvector/neo4j). No `pgvector`/`neo4j`/`VectorField`/`cypher`/embedding references anywhere in the codebase (grep clean).

**Document body = AKN XML in ONE column (not decomposed into rows). CONFIRMED.**
- `indigo_api/models/documents.py:368-369` — `document_xml = models.TextField(...)` with docstring *"Raw XML content of the entire document"*.
- `content` property (`:413-418`) aliases `document_xml`; `:560` serializes the parsed `doc` back to XML into that one column. Structure (TOC, provisions) is parsed in-memory from the XML on demand (`:190-206`, `table_of_contents`), NOT persisted as rows.

**Work / Expression / Amendment = relational tables + FKs (FRBR model).**
- `Work` (`indigo_api/models/works.py:470-578`): `frbr_uri` unique CharField (`:503`), FKs to Country/Locality, self-FKs `repealed_by` (`:532`) and `parent_work` (`:542`), `main_commencement` FK (`:568`), M2M `taxonomy_topics` (`:554`). FRBR fields are flat columns (doctype/subtype/date/number).
- `Document` = an Expression: FK `work` (`documents.py:346`), `frbr_uri` + `expression_date` (`:355,373`) + `language` FK (`:362`). One row per (work, language, expression_date). `get_for_frbr_uri` resolves expression by date/language (`:94-143`).
- `Amendment` (`indigo_api/models/amendments.py:19-38`): FKs `amended_work` + `amending_work` + `date` + `verb`. **The amendment "graph" is pure relational join rows**, traversed in Python (`:46-74`), not a graph engine.

**Versioning model vs TraLuat bitemporal:** Indigo versions by **Expression (one Document row per expression_date)** — a valid-time-ish point-in-time model, plus django-reversion edit history (SQL partition query seen at `documents.py:702`). It is **single-timeline, NOT bitemporal** (no transaction-time dimension, no `tx_from/tx_to`). No `unit_version`-style clause-level temporal table.

---

## 3. legalbenchrag (refs/legalbenchrag)

**Vector store = sqlite-vec (NOT pgvector). diskcache content-hash cache. CONFIRMED.**

- sqlite-vec: `legalbenchrag/methods/baseline.py:6` `import sqlite_vec`; `:160-171` opens `./data/cache/baseline.db` (sqlite3), `sqlite_vec.load()`, creates `CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[N])`. DB file is **deleted and rebuilt on each sync** (`:161-162`).
- Insert/query: `:173-181` `INSERT INTO vec_items(rowid, embedding)`; `:202-213` `WHERE embedding MATCH ? ORDER BY distance ASC LIMIT ?` (kNN). Optional rerank `:218-229`.
- diskcache content-hash cache: `legalbenchrag/utils/ai.py:11` `import diskcache as dc`; `:122` `cache = dc.Cache("./data/cache/ai_cache.db")`; cache key = `"{company}||{model}||{type}||{md5(text)}"` (`:374`, md5 via `hashlib` `:2,207,539`). Caches embeddings/LLM calls keyed by content hash.

**How spans/chunks are persisted:** Only the **embedding vectors** are persisted in sqlite-vec, keyed by integer `rowid`. The chunk metadata — `EmbeddingInfo(document_id, span, embedding)` — is held in an **in-memory Python list `self.embedding_infos`** (`baseline.py:182-189`), index-aligned to `rowid` (`:214-215`). Spans are character-offset ranges into source documents. So: no relational store, no Postgres; ephemeral sqlite + in-memory list, rebuilt per run.

---

## 4. LeSICiN (refs/LeSICiN)

**Heterogeneous graph = file-based (JSON edge files) → in-memory torch_sparse tensors. NOT a graph database. CONFIRMED.**

- Graph built in `helper.py:28-64` `generate_graph(...)`: combines label tree + fact-section citation network into `torch_sparse.SparseTensor(row, col, sparse_sizes)` adjacency matrices keyed by edge-type tuple (`:57-62`). `import torch_sparse` `:2`.
- Source graph is **JSON files on disk** (`configs/data_path.json`): `label_tree.json`, `citation_network.json`, `schemas.json`, `type_map.json`. Node/text data = `.jsonl` (`secs/train/dev/test.jsonl`).
- Caches = **pickle** (`cache/*.pkl`); trained model = `saved/best_model.pt`.
- Metapaths sampled directly off the in-memory adjacency (`data_helper.py:146-158`). No Neo4j/networkx-server/SQL — grep confirms only torch_sparse + file I/O. The "graph" is tensors in RAM derived from JSON.

---

## 5. LegalGraphRAG (refs/LegalGraphRAG)

**4-layer knowledge graph = in-memory NetworkX, persisted to ONE pickle file. NOT Neo4j, NOT pgvector, NOT any graph DB server. CONFIRMED.**

- `core/graph_construct/graph_db.py:1,10-11` — explicit: *"In-memory graph database implementation based on NetworkX"*. `InMemoryGraphDB` is a singleton (`:13-19`) wrapping `nx.MultiDiGraph()` (`:26`).
- Nodes typed Cases/Laws/Crimes/Cluster (`:33-46`); 4 graph-construct modules = the layers: `fact_graph.py`, `ontology_graph.py`, `feature_graph.py`, `rule_graph.py`.
- **Vectors also in-memory**: embeddings kept as numpy arrays in per-type dicts (`:33-46,78-80`); similarity = brute-force cosine loop (`find_similar_nodes`, `:145-174`, `scipy.spatial.distance.cosine`). No vector index engine.
- Graph algorithms via NetworkX: pagerank (`:179`), degree centrality (`:184-189`), Louvain communities (`:191-206`).
- **Persistence = a single pickle file**: `save()`/`load()` `pickle.dump/load` (`:208-240`); path `graph_db_path=./outputs/main_experiment/qwen3_graph_db.pkl` (`env.example`). `auto_save=True` on exit, `auto_build=True` if missing. Multiprocessing workers reload the graph from that pickle.
- `requirements.txt`: `networkx>=3.0` only. No neo4j/faiss/chroma/sqlite.

---

## 6. L-MARS (refs/L-MARS)

**Essentially STATELESS over external + offline search. No database, no vector store, no persistence layer. CONFIRMED.**

- Tools (`lmars/tools/`): `courtlistener_tool`, `tavily_search_tool`, `serper_search_tool` (external web/legal search APIs) + `offline_rag_tool`.
- Offline RAG = **ephemeral in-memory BM25 index** (`lmars/tools/offline_rag_tool.py:13-70` BM25 class; `:154-157,248-253,325-329` builds/rebuilds index from local JSON docs at runtime). **No embeddings, no vector DB** — lexical BM25 only.
- Run state = in-memory only: `workflow.py:98-170` keeps a `search_history: list[str]` per invocation; nothing written to disk/db. grep for sqlite/postgres/chroma/faiss/redis/pickle/checkpoint across `lmars/` = clean.
- => L-MARS persists nothing of its own; it orchestrates LLM agents over live search + a rebuilt-each-time local index.

---

## MATCH ASSESSMENT

Legend: ✅ validates · ⚠️ partial/related · ❌ diverges · — n/a

| TraLuat choice | PAKTON | Indigo | legalbenchrag | LeSICiN | LegalGraphRAG | L-MARS | Verdict |
|---|---|---|---|---|---|---|---|
| **Postgres as SoR** | ⚠️ metadata + LangGraph checkpoint only (not docs/chunks) | ✅ true SoR (all legislation in PG) | ❌ none | ❌ none | ❌ none | ❌ none | Only **Indigo** validates PG-as-SoR. PAKTON uses PG narrowly. |
| **pgvector for embeddings** | ❌ Pinecone/Chroma (dedicated) | — no vectors | ❌ sqlite-vec | — torch tensors | ❌ in-mem numpy | — BM25, no vectors | **NO repo uses pgvector.** Universal divergence. |
| **Apache AGE (graph on PG)** | ❌ LightRAG service | ❌ relational FKs | — | ❌ file/tensor graph | ❌ in-mem NetworkX+pickle | — | **NO repo uses AGE or any graph-on-Postgres.** |
| **Object storage (MinIO/S3) for blobs** | ❌ (volume/temp files) | ❌ XML in PG column | ❌ local files | ❌ local files | ❌ local files | ❌ | **No repo uses S3/MinIO.** All use PG column or local FS. |
| **Derived indexes rebuildable from SoR** | ⚠️ vector re-indexed via `delete_all`+reindex, but source is uploads not a PG SoR | ⚠️ XML re-parsed to TOC on demand (TOC is derived) | ✅ sqlite-vec wiped+rebuilt every run | ✅ adjacency rebuilt from JSON (cached as pkl) | ✅ graph auto-built from source JSON if pickle missing | ✅ BM25 rebuilt each run | **Pattern strongly validated** — but everywhere the SoR is files/JSON, not Postgres. |
| **Per-tenant isolation (shared KB vs client data)** | ⚠️ per-user rows (user_email FK), single shared DB; no tenant boundary | ❌ single shared corpus, role perms only | ❌ | ❌ | ❌ | ❌ | **No repo implements multi-tenant isolation.** PAKTON has per-user scoping only. |
| **Bitemporal `unit_version` (valid+tx time)** | ❌ | ⚠️ expression-per-date = single-timeline valid-time; django-reversion edit log; NOT bitemporal | ❌ | ❌ | ❌ | ❌ | **No repo is bitemporal.** Indigo is the closest (point-in-time by expression_date) but single-timeline. |

### Divergence analysis — consolidation vs risk

1. **pgvector instead of a dedicated vector DB (Pinecone/Chroma/sqlite-vec):** Every repo that does vector search uses a *dedicated* store (PAKTON Chroma/Pinecone, legalbenchrag sqlite-vec) or in-memory numpy (LegalGraphRAG). None co-locate vectors in Postgres. TraLuat's pgvector choice is a **reasoned consolidation** (one DB engine, transactional consistency with the SoR, fewer moving parts) and is well-proven at the clause-chunk scale these repos operate at. **Low risk**, with the caveat that none of these references stress-tested pgvector at large scale — recall/latency at corpus scale is unvalidated by this set.

2. **Apache AGE instead of a graph DB / file graph:** The graph repos split cleanly — LeSICiN (torch_sparse tensors from JSON) and LegalGraphRAG (NetworkX + pickle) are **research-grade in-memory/file graphs**, not production graph stores; PAKTON offloads to LightRAG; Indigo encodes its citation/amendment "graph" as **plain relational FKs** and never needed a graph engine. This is the biggest design decision. Two readings:
   - Consolidation upside: AGE keeps graph *in* Postgres (one SoR, one backup/restore story, rebuildable). Reasonable.
   - **Risk flag:** (a) NO reference repo validates AGE specifically — it is the least externally-validated TraLuat component here; AGE is less mature/less widely operated than Neo4j. (b) Indigo's evidence suggests a legal norm/amendment graph is expressible as relational FKs *without* any graph engine — so AGE may be **over-engineering** unless TraLuat's graph queries are genuinely multi-hop/variable-length (openCypher territory). Recommend confirming the query patterns justify AGE over plain FK joins / recursive CTEs.

3. **Object storage (MinIO/S3) for raw PDFs:** No repo does this (Indigo stores XML in-column; others use local FS). This is **standard architecture, low risk** — the repos simply don't deal with PDF blob lifecycle, so this is unvalidated-but-uncontroversial. It is a sound consolidation (keep large blobs out of the relational row).

4. **Rebuildable derived indexes:** **This is the one principle the repos broadly endorse.** legalbenchrag wipes+rebuilds sqlite-vec every run; LeSICiN rebuilds adjacency from JSON; LegalGraphRAG auto-builds the graph from source if the pickle is absent; PAKTON re-indexes the vector store. The universal pattern is "derived stores are disposable, source is authoritative." TraLuat's version is *stronger* (source = Postgres SoR rather than loose JSON/files), which is an improvement, not a divergence. **Validated.**

5. **Bitemporal versioning:** **No repo is bitemporal.** Indigo — the only mature legislation system here — uses a *single-timeline* valid-time model (one Expression row per `expression_date`) plus a separate edit-history log (django-reversion). This is a **risk/novelty flag**: TraLuat's `unit_version` with both valid-time and transaction-time is more ambitious than any reference. It is defensible for a legal platform (you must answer "what did the law say on date X, as we knew it on date Y"), but it is **unvalidated by these repos** and carries real modeling/query complexity. Indigo's simpler expression-per-date model is the proven fallback if bitemporality proves too costly.

6. **Multi-tenant isolation:** **No repo implements it.** PAKTON scopes rows by `user_email`; others are single shared corpora. TraLuat's shared-KB-vs-isolated-client-data split is **unvalidated here and is net-new risk** — none of these references inform the isolation mechanism (schema-per-tenant / RLS / separate DBs). Must be designed from first principles, not borrowed.

### Bottom line
- **Validated by the repos:** rebuildable derived indexes (strong); Postgres-as-SoR (Indigo only); keeping a legal graph expressible relationally (Indigo — a caution against over-using AGE).
- **Diverges but as reasonable consolidation (low risk):** pgvector (vs dedicated vector DB), object storage for blobs. Rationale = fewer moving parts; the references use more stores, not fewer, largely because they are research prototypes.
- **Diverges AND carries real risk (least validated):** Apache AGE (no repo uses it; Indigo suggests FKs may suffice), bitemporal `unit_version` (no repo does bitemporal; Indigo does single-timeline), multi-tenant isolation (no repo does it). These three are TraLuat's genuinely novel bets and should be justified/prototyped independently of this reference set.
