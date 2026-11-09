# TraLuat — Thiết kế hiệu năng (performance)

> Gom 7 đòn bẩy tốc độ + lấp 3 mảnh thiếu, dựa trên deep-audit repo (`research_notes/Repo deep read/performance_storage_audit.md` + `performance_retrieval_audit.md`, file+line).
> Nguyên tắc: **pick-up cái repo giải được · đánh dấu net-new rõ · đặt SLO (không repo nào có).**

---

## 0. Kết luận audit (trước khi vào chi tiết)
- 🎯 **Materialized snapshot — Indigo ĐÃ giải** (one-row-per-date, không ghép) → **ADOPT store**; nhưng Indigo tạo thủ công → **auto-consolidator là net-new**.
- ⚠️ **Index — Indigo là PHẢN-ví-dụ** (không composite/GIN/GiST; **`expression_date` hot-path không index**) → **SKIP**, tự làm.
- ✅ **Cache / pagination / batching — ADOPT nhiều mẫu tốt** (Indigo render-cache tự-invalidate, legalbenchrag `ai.py` client, DRF pagination).
- ❌ **SLO/latency — không repo nào có** → net-new hoàn toàn.
- **ANN:** repo dùng brute-force O(N)/O(N²) → *cảnh báo, không template*; ta chọn **pgvector HNSW** (không ivfflat).

> **Audit lại đánh giá (đã sửa 3 chỗ nói quá/lẫn):** (1) HNSW *không* tự chịu được filter — cần `iterative_scan` + B-tree/partition + benchmark (§2); (2) snapshot chỉ cho document-level + hiển thị, *không* cho reconstruct cấp điều (đã O(1)) — chặn chi phí lưu (§1); (3) SLO Assistant `<5s` là aspirational vì verify-chain (§6). Phần repo-cited còn lại đã verify, giữ nguyên.

---

## 1. Materialized snapshot — "văn bản tại ngày T" đọc tức thì (ADOPT + auto-consolidator net-new)

**Vấn đề:** dựng `document_as_of` bằng ghép version qua cây = tốn mỗi lần đọc.
**Giải (từ Indigo `documents.py:368`, `works.py:685`):** lưu **snapshot hợp nhất, một row/ngày-mốc**, đọc = lấy row, *không ghép*.

```sql
consolidated_snapshot(
  id, frbr_uri, as_of_date DATE, lang,
  text, xml,                          -- văn bản đã hợp nhất tại as_of_date
  built_from_version_ids BIGINT[],    -- truy nguồn
  tx_from TIMESTAMPTZ, tx_to TIMESTAMPTZ,
  UNIQUE(frbr_uri, as_of_date, lang))
```
- **Đọc:** `document_as_of(uri, T)` → tra snapshot `as_of_date ≤ T` mới nhất; **fallback** ghép từ `unit_version` nếu chưa có snapshot (rồi lưu lại).
- ⚠️ **PHẠM VI (audit lại):** snapshot CHỈ cho **`document_as_of` (ghép nhiều điều) + hiển thị + nạp cả-văn-bản cho LLM**. `reconstruct_as_of` **cấp điều đã O(1)** (một row `unit_version`) → *không cần* snapshot; retrieval cũng chạy trên chunk `unit_version`, *không* qua snapshot. **Chặn chi phí lưu** (full text × ngày × ngôn ngữ dễ nổ): **dựng on-demand + cache (LRU/TTL)**, KHÔNG eager-materialize mọi date×doc.
- **★ Auto-consolidator (NET-NEW, Indigo làm tay):** pipeline nạp mỗi khi áp một `norm_relation` sửa đổi/bãi bỏ (W2 R3/R4) → sinh snapshot mới tại `effective_date`. Tự động, không editor.
- `possible_snapshot_dates(uri)` = tập `effective_date` của các sửa đổi (kiểu Indigo `possible_expression_dates`).

---

## 2. Chiến lược index (NET-NEW — SKIP Indigo)

Indigo *không* index trục thời gian → ta tự làm:
```sql
-- bitemporal hot-path (reconstruct_as_of)
CREATE INDEX ON unit_version (unit_id, lang, valid_from, valid_to)
  WHERE tx_to = 'infinity';                       -- partial: chỉ bản ghi đang tin
CREATE INDEX ON unit_version USING gist (daterange(valid_from, valid_to));  -- range @> T
-- snapshot
CREATE INDEX ON consolidated_snapshot (frbr_uri, lang, as_of_date DESC);
-- FTS (Indigo chỉ query-time, không GIN → ta thêm)
ALTER TABLE chunk ADD COLUMN tsv tsvector;         -- Postgres FTS tiếng Việt (unaccent)
CREATE INDEX ON chunk USING gin (tsv);
-- vector: pgvector HNSW (KHÔNG ivfflat)
CREATE INDEX ON chunk USING hnsw (embedding vector_cosine_ops);
-- lọc metadata: index (jurisdiction, doc_type), (tenant_id)
-- graph: index norm_relation (src_unit_id, relation_type), (dst_unit_id)
```
**HNSW làm default** (recall/latency tốt + **insert incremental**, hợp luồng nạp luật liên tục; ivfflat phải train lại khi dữ liệu đổi). **Pin `ef_search`; giữ brute-force làm recall-oracle.**

⚠️ **ĐÍNH CHÍNH (audit lại):** HNSW **KHÔNG tự "chịu được filter"**. Khi post-filter chọn lọc (`tenant`+`as_of`), *cả* HNSW lẫn ivfflat **under-retrieve** (lọc áp *sau* một pass ANN → có thể còn < LIMIT). Phải:
1. Bật **`hnsw.iterative_scan = relaxed_order`** (pgvector **≥ 0.8** — *xác nhận version*), cân `hnsw.max_scan_tuples` (mặc định ~20k; cao hơn → recall tốt hơn nhưng chậm hơn).
2. Filter **rất chọn lọc** → **B-tree trên cột filter để thu hẹp TRƯỚC** ANN, hoặc **partition theo `tenant`/`jurisdiction`**.
3. **BENCHMARK** cấu hình này (recall@k vs latency) — coi là *phải đo*, không "đã giải". ([pgvector filtering](https://www.crunchydata.com/blog/hybrid-vector-search))

---

## 3. Các tầng cache (ADOPT)
| Cache | Key | Nguồn | Lưu ý ★ |
|---|---|---|---|
| Embedding | content-hash (md5 text) | legalbenchrag `ai.py:371` | **chia sẻ** (text luật công) |
| Kết quả retrieval / rerank | **hash(query) + `tenant` + `as_of`** | net-new | **BẮT BUỘC gồm tenant+as_of** (nếu không → rò + sai hiệu lực) |
| Snapshot / render | `id + updated_at` (tự-invalidate) | Indigo `renderers.py:178` | self-invalidating, khỏi purge thủ công |
| Config/thẩm quyền/đơn vị HC | in-mem + **version-counter cross-process** | Indigo `places.py:71` | ADOPT nguyên |
| Graph build / pagerank | precompute → persist (incremental, không single-pickle) | ADAPT LegalGraphRAG | per-version, không wipe |

**Tách "rebuild index rẻ / cache embedding đắt"** (legalbenchrag): rebuild chỉ mục nhanh được vì embedding đã cache — ADOPT.

---

## 4. Hiệu năng truy xuất/compute
- **ANN:** HNSW + **filter `as_of`+`tenant` trong cùng query** (net-new — 6/7 repo truy xuất global). `ann_topk → rerank_topk → giới hạn token context` (legalbenchrag `retrieval_strategies.py:30`); reranker **opt-in**, **`use_fp16`** local (PAKTON `config.researcher.yaml`).
- **Prefilter rẻ trước đắt:** Aho-Corasick (eyecite `tokenizers.py:451`) cho **citation-linker VN** (literal scan gate regex đắt). ADOPT cho detector, không cho vector search.
- **★ Bound-hop guard (NET-NEW):** `max_hops · max_fanout · sample≤k từ adjacency precomputed · timeout`. Lấy *kỷ luật* LeSICiN (`data_helper.py:158` num_neighbors=1, sample=8, đọc adjacency dựng sẵn) — **SKIP** full-scan/unbounded của LegalGraphRAG (`ontology_graph.py:255` quét O(N)).
- **Batching/concurrency:** ADOPT **`ai.py` làm template client** (batch 2048 · per-provider Semaphore · pacing `max(60/rpm, tokens/tpm)` · backoff `min(2^i,5)` · diskcache) — adapt sang **bge-m3/vLLM local**. Ingest: **build-once + parallel worker** (LegalGraphRAG `run.py:155`). Serving: async. **SKIP** PAKTON per-query refetch toàn corpus BM25 (`hybrid.py:147` k=10000) + embed một-cái-một (LegalGraphRAG).
- **Precompute split (ADOPT nguyên tắc):** *offline* = chunk embedding · graph build · pagerank/community · snapshot · applicability_condition; *per-query* = chỉ query-embedding + AC-scan + ANN + rerank + bound-hop.

---

## 5. Pagination / throughput (ADOPT)
- **Pagination** + **defer cột nặng** (`no_xml`/text) + **select_related/prefetch** chống N+1 (Indigo `documents.py:59-75`, DRF page_size 500/search 20).
- **Warm worker per-process** + **SQLAlchemy pool** `pre_ping, size 10, overflow 20` (PAKTON `database/config.py:25`), task retry (`tasks.py:49`).

---

## 6. SLO mục tiêu (NET-NEW — đề xuất để đội có đích, hiệu chỉnh sau)
| Thao tác | p50 | p95 | Ghi chú |
|---|---|---|---|
| `reconstruct_as_of` (từ snapshot) | <15ms | **<50ms** | tra row, không ghép |
| `in_force` / citation tồn tại (rule) | <5ms | <20ms | index bitemporal |
| Retrieval (ANN+FTS+RRF+rerank) | <200ms | **<500ms** | HNSW + local reranker fp16 |
| Multi-hop graph (bounded) | <100ms | <300ms | max_hops=3, fanout cap |
| Assistant end-to-end (LLM-bound) | <2s | **<5s** | phần lớn là LLM; cache prompt |
| Review một hợp đồng (async) | — | <60s | nền, SSE báo tiến trình |
| Judgment Analysis (async) | — | vài phút | nền, HITL |
| Ingest throughput | — | — | đặt mục tiêu docs/giờ sau khi đo OCR |

⚠️ **Audit lại:** Assistant `<5s` là **aspirational** — chuỗi grounding+verify (generate + verify 6-lớp + cross-provider) nhiều lần gọi LLM, p95 thực có thể cao hơn; **verify-chain là chi phí chính**. Phải **đo**, và cân nhắc verify song song / verify một lượt cho câu đơn giản.

---

## 7. Tổng hợp ADOPT / net-new / cảnh báo
- **ADOPT:** snapshot-row-per-date (Indigo) · cache tự-invalidate + content-hash + version-counter · pagination/defer/prefetch · `ai.py` client (batch/pacing/backoff) · wide-then-narrow · precompute split · Aho-Corasick cho citation.
- **NET-NEW (repo không có):** ① filter `tenant`+`as_of` trong ANN query (→ chọn HNSW) · ② **auto-consolidator** snapshot từ sửa đổi · ③ index bitemporal (composite+GiST+GIN) · ④ bound-hop guard · ⑤ cache key gồm tenant+as_of · ⑥ incremental per-version rebuild · ⑦ **SLO**.
- **CẢNH BÁO đừng copy:** brute-force O(N)/O(N²) (sqlite-vec/numpy) · per-insert full-array rebuild · full-nodes-scan traversal · PAKTON per-query whole-corpus BM25 · embed một-cái-một · Indigo thiếu index trục thời gian.

> **Một dòng:** repo cho ta **snapshot-row (mảnh nặng nhất) + mọi mẫu cache/pagination/batching**; ta tự làm **index bitemporal · auto-consolidator · filter-trong-ANN · bound-hop · SLO** — và tránh mọi chỗ repo làm ngây thơ (brute-force/unbounded).

---

## 8. ★ Bảo toàn ĐÚNG-ĐẮN khi tối ưu (nguyên tắc #15 — "được chậm, không được sai")
> Mọi đòn bẩy §1–§5 phải không-đổi-đáp-án. Chia **2 lớp**, mỗi lớp một cách bảo chứng:

**(A) Tối ưu TƯƠNG-ĐƯƠNG — phải identical:** snapshot (§1), cache (§3), index (§2), batching/precompute (§4), pagination (§5).
- **Bảo chứng:** kết quả = đường-không-tối-ưu, **byte-identical**.
- **CI:** chạy **parallel-path** (vd `document_as_of` từ snapshot vs ghép trực tiếp; cache-hit vs recompute) trên gold → **lệch = fail**.
- **Cache key gồm MỌI input ảnh hưởng output** (query·cands·as_of·law_version·tenant·model+prompt version) — thiếu 1 = serve stale sai. (Redis version-stamp+TTL §3.)

**(B) Tối ưu XẤP-XỈ — recall<100% by design:** ANN/HNSW (§2), bound-hop (§4), top_k/wide-then-narrow (§4), reranker opt-in.
- **Bảo chứng:** KHÔNG identical được → **offline-calibrate recall-floor vs brute-force oracle** (oracle đã có §2); chọn `ef_search`/`iterative_scan`/`max_scan_tuples`/hop-cap/top_k sao cho **recall@k ≥ floor** trên gold.
- **CI:** đo **recall@k ≥ floor vs oracle** (không phải identical). Hop-cap **phải ĐO** trên gold (governing-norm luật thường 1–2 hop nhưng đừng giả định).
- **Runtime:** không có ground-truth → **không gate theo recall thật**; dựa **sufficiency floor (R1, W3 §2) + abstain** (proxy coverage + score-gap). **Cấm miss âm thầm.**

**Cổng runtime (thật):** **no-skip-rerank / no-downgrade ở ca HIGH-STAKES** (Judgment/omission/conflict — risk-class QĐ 33). Đòn bẩy tốc độ (skip rerank, hop-cap chặt, top_k nhỏ) **chỉ cho ca rẻ**, không cho ca nặng.

> Một câu: **(A) chứng minh identical; (B) chứng minh recall≥floor + runtime abstain; high-stakes không downgrade.** SLO (§6) là mục tiêu tốc độ — **đúng-đắn là ràng buộc cứng đứng trên SLO.**
