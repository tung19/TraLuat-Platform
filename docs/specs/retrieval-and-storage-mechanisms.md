# TraLuat — Cơ chế Lưu trữ & Truy xuất: audit repo + verdict đem về

> Deep-audit code thật: (A) data pipeline + storage + local/cloud; (B) cơ chế/thuật toán/model truy xuất ở mọi điểm. Mỗi cơ chế có verdict **ADOPT / ADAPT / SKIP**.
> Nguồn: `research_notes/Repo deep read/pipeline_storage_audit.md` + `retrieval_mechanisms_audit.md` (file+line). Đọc kèm `specs/stack-db-and-models.md`, `specs/deployment-infrastructure.md`.

---

## 0. Phát hiện chịu lực (quyết định mọi thứ dưới)

**6/7 repo truy xuất GLOBAL, không filter** — vector query không nhận predicate metadata, cache không key theo tenant (legalbenchrag `baseline.py:202`; PAKTON `vectordb.py:164` không truyền `filter=`; LegalGraphRAG `graph_db.py:145`). **Chỉ Indigo** scope theo **point-in-time + jurisdiction** natively (`expression_date` ≈ as_of; `country/locality` ≈ tenant — `utils.py:50`, `views/works.py:712`).
→ **Thuật toán truy xuất tái dùng được; nhưng predicate `as_of` + `tenant` là net-new ta phải thêm vào mọi truy vấn — trừ Indigo là template kiến trúc.**

---

## PHẦN A — DATA PIPELINE + STORAGE + LOCAL/CLOUD

### A.1 Posture từng repo
| Repo | Pipeline | Storage | Local/Cloud |
|---|---|---|---|
| **Indigo** ★ | `docpipe` stage có thứ tự; bulk import; idempotency natural-key `frbr_uri` | Postgres (AKN XML) + **Attachment giữ blob gốc** | **chuyển FileSystem⇄S3 bằng flag** (S3-API → MinIO-VN) |
| PAKTON | Celery+Redis, task retry, warm worker | Postgres(metadata)+checkpointer; **vứt blob** (tempfile→xoá); reindex wipe-replace | Chroma-local ⇄ Pinecone-cloud; **Supabase cloud** auth |
| legalbenchrag | script | sqlite-vec (xoá+dựng mỗi lần) + diskcache md5 | all-local, disposable |
| LegalGraphRAG | `run.py` multiprocessing pool | **1 pickle** (fragile); auto_build/save | local (Ollama/vLLM) |
| LeSICiN | script | JSONL+pickle+torch_sparse | local, prototype |
| eyecite | — | **stateless** (đúng cho component parsing) | none |
| claude-for-legal | — | **connector MCP cloud ngoại** (Ironclad/DocuSign/Drive) | ⚠️ anti-pattern residency |

### A.2 Verdict đem về
| Cơ chế | Verdict | Lấy từ / làm gì |
|---|---|---|
| Orchestration pipeline | **ADAPT** | PAKTON Celery backbone + Indigo stage khai báo có thứ tự (ta dùng Temporal) |
| Upload / dedup / provenance | **ADAPT + BUILD** | Indigo idempotency natural-key `frbr_uri` + **THÊM SHA-256 blob hash** (không repo nào làm) |
| Blob gốc | **ADOPT** | Indigo S3-switch → **MinIO tại VN, GIỮ raw** (PAKTON vứt — đừng) |
| Derived-index persistence | **ADOPT nguyên tắc / ADAPT impl** | disposable+rebuild từ SoR (mọi repo), nhưng **incremental per-version**, không wipe/không single-pickle |
| Local⇄cloud switch | **ADOPT** | Indigo blob-switch + pgvector (luôn local) → local-first hơn PAKTON |
| Backup / migration | **ADOPT** | Alembic (PAKTON) + audit kiểu reversion (Indigo) |
| Resume / checkpoint nạp | **ADAPT + BUILD** | Celery retry + skip-if-exists + **status-ledger per-doc/per-stage trên Postgres** (net-new — không repo nào có resume thật) |

**Residency NĐ 356/2025:** Indigo blob-switch + pgvector local + Ollama/vLLM local = **full residency VN**. **Tránh** Supabase/Pinecone/cloud-MCP.

---

## PHẦN B — CƠ CHẾ TRUY XUẤT (mọi điểm)

### B.1 Verdict từng cơ chế
| Cơ chế | Verdict | Chi tiết (file+line) |
|---|---|---|
| **Chunking** | **ADOPT + ADAPT** | ADOPT RCTS giữ-span của legalbenchrag (`baseline.py:91-134`, assert `join==content`); ADAPT ý structural của PAKTON nhưng **thay LLM-parser bằng splitter VN tất định** (Điều/Khoản/Điểm) |
| **Embedding** | **ADOPT bge-m3 local** (Ollama, 1024-d, đa ngữ/VN) | từ LegalGraphRAG `embedding.py:5`; **SKIP** text-embedding-3-large (API + rời infra = residency) |
| **Vector search** | **ADOPT pgvector + filter-trong-cùng-query** | mô phỏng sqlite-vec vec0 (`baseline.py:169-213`); SKIP NetworkX/numpy brute-force + Pinecone |
| **Sparse/lexical** | **ADOPT Postgres FTS** (`ts_rank_cd`+headline+language) của Indigo | 2 BM25 kia English-tokenized (PAKTON `bm25.py:64 query.split()`; L-MARS English stopwords) → **under-retrieve tiếng Việt**; nếu muốn BM25 → ADAPT rank_bm25 + analyzer VN (pyvi/underthesea + unaccent) |
| **Fusion** | **ADOPT weighted RRF** (hand-roll) | PAKTON EnsembleRetriever 0.5/0.5 (`hybrid.py:152`); **đừng** copy fetch-all-docs (`:147`) |
| **Reranking** | **ADOPT bge-reranker-v2-m3 local + wide-then-narrow** | PAKTON flag-reranker; legalbenchrag `embedding_topk=300→rerank_topk`; SKIP Cohere (English+API) |
| **Graph retrieval** | **ADAPT concept/charge-anchored + typed multi-hop** | LegalGraphRAG `R=R_sem∪R_com∪R_chg`, PageRank/community, kNN SIMILAR_TO — nhưng trên **graph bền + dated**, không NetworkX in-mem; bỏ LLM-mỗi-bước. **SKIP code LeSICiN** (HAN+MAGNN train, IPC — chỉ giữ *ý tưởng* inductive cho phase sau) |
| **Query understanding** | **ADOPT + ADAPT** | PAKTON LLM rewrite+tool-select (`query_extractor.py:45`); ADAPT facet-extraction của LegalGraphRAG thành **parser facet VN + `as_of_date`**; ADOPT **temporal-routing L-MARS** (`router.py:102 _temporally_invalid`) + abstain gate (`aggregator.py:42` conf≥0.6) |
| **Caching** | **ADOPT diskcache content-hash** | legalbenchrag (`ai.py:371`) + digest guard; **CRITICAL: key của result/rerank cache phải gồm `tenant + as_of`** (embedding cache chia sẻ được) |
| **Linking/matching** | **ADOPT eyecite-style VN citation linker** | Aho-Corasick prefilter + resolve antecedent/id./supra (`resolve.py:63-227`) → quy "Điều này / nêu trên" về canonical ID để hop/effectivity chạy trên **ID, không phải chuỗi**; thay reporters_db bằng pattern VN |

### B.2 Local/đa-ngữ THẮNG vs API/residency RỦI RO
- **Thắng (local, đa ngữ, tất định):** bge-m3 (embed), bge-reranker-v2-m3, Postgres FTS, Aho-Corasick, RRF.
- **Rủi ro (API + rời infra):** OpenAI embeddings, Cohere rerank → **SKIP** (residency + chi phí).
- **Ranh giới tất định:** LLM chỉ ở **query-understanding + rerank vài-cuối**, **không** chấm điểm bulk.

---

## C. Stack truy xuất khuyến nghị cho TraLuat (8 bước)
```
1. Chunk: splitter VN tất định (Điều/Khoản/Điểm) + giữ span chính xác
2. Embed: bge-m3 local (Ollama), 1024-d
3. Search: Postgres pgvector + FTS, với as_of + tenant trong MỆNH ĐỀ WHERE   ← net-new, mọi repo thiếu
4. Fusion: weighted RRF (hand-roll), c≈60
5. Rerank: bge-reranker-v2-m3 local, wide(300)-then-narrow
6. (Phase 2) Graph: reference graph bền + dated, concept-anchored hops, không LLM-mỗi-bước
7. Query: LLM rewrite + facet/as_of parser + VN citation linker (eyecite-style) + temporal re-search/abstain (L-MARS)
8. Cache: diskcache content-hash; key result/rerank GỒM tenant+as_of; embedding cache chia sẻ
```

> **Một dòng:** thuật toán truy xuất gần như lấy sẵn được (RCTS chunk · bge-m3 · pgvector · RRF · bge-reranker · FTS · Aho-Corasick) — **phần phải tự làm là nhét `as_of` + `tenant` vào MỌI truy vấn/cache** (chỉ Indigo làm, 6/7 repo bỏ trống) và **dựng splitter + citation-linker + FTS cho tiếng Việt** (các BM25 của repo tokenize kiểu English → hỏng với VN). Storage: **local-first theo Indigo (blob-switch→MinIO-VN) + pgvector**, tránh cloud ngoại.
