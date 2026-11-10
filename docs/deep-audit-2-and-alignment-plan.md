# TraLuat — Deep Audit #2 (code ↔ kiến trúc) + Plan căn chỉnh

> Audit độc lập 2 nhánh (data/retrieval plane · reasoning/serving plane) đối chiếu code đã-implement với specs + `layered-architecture.md` (15 layer / 5 plane). Mục tiêu: không chỉ "thiếu gì" mà **"chỗ nào lệch thiết kế"**, rồi xếp thứ tự code lại cho khớp kiến trúc.
> Trạng thái code: 121 test xanh, lõi thuật toán (bitemporal · grounding gates · hard-gate narrowing · egress fail-closed · portability) **đúng hình**. Lệch nằm ở **lớp nền/enforcement/serving** và **persistence của L4**.

---

## 0. Kết luận 1 dòng
Thuật toán lõi **đúng**; nhưng (a) **L4 index chưa persist** (recompute+embed mỗi query, không vector store), (b) **as_of/tenant chưa là push-down predicate**, (c) **tenant-isolation chưa enforce ở SQL** (RLS là helper chết), (d) **"intelligence thật" còn stub** (element-judge keyword, không model-router), (e) **serving async/observability/governance substrate ~0**. Căn chỉnh = dựng đúng các lớp nền này, không viết lại thuật toán.

---

## 1. Bug correctness (sửa TRƯỚC — rẻ, không rework, khớp code hiện có)

| ID | Vấn đề | Sửa |
|---|---|---|
| **B1** | `known_as_of` không pin xuyên `retrieve→ground` (mặc định `now()` mỗi call) → tx-time có thể lệch giữa chunk và gate2 trong 1 request | Pin 1 `known_as_of` đầu request, truyền xuyên retrieve/citable_text/ground |
| **B2** | Numeric-divergence so sánh **set** (`qa[u]!=qb[u]`): `{30}` vs `{15,30}` bị cờ dù trùng; `diverge[0]` tuỳ tiện | So "giá trị vô hướng khác nhau rời nhau", bỏ khi giao nhau; giữ mọi đơn vị lệch, ghi rõ |
| **B3** | Citation anchor hard-code `as_of` (gateway + orchestrator) → câu đa-mốc/lex-mitior verify sai anchor → abstain oan | Thread anchor theo `as_of_map`; verify mỗi citation tại anchor của nó |
| **B4** | Resume debate **mất chunk context** (pool nạp lại từ W2 nhưng không thêm vào `chunk_all`) → adjudicate mỏng hơn, khác kết quả | Resume: build lại chunk cho pool eids (từ L4 index) trước adjudicate |
| **B5** | `local_available` là field request (client điều khiển circuit-breaker) | Lấy từ **health-probe interface** (gateway `.healthy()`), không từ body |
| **B6** | multi_role trả `audit_trail=[]` (chỉ ở transcript) → hợp đồng `Adjudication` lệch giữa 2 mode | Populate `audit_trail` từ transcript cho debate mode |
| **B7 (latent)** | Gate3 version-match so `art.text` (span) vs full unit text — hiện ĐÚNG vì span==unit, **sẽ sai** khi có sub-span chunk | So theo `version_date`/`valid_from` thay vì string-identity khi dựng span-preserving chunker (Phase D) |

---

## 2. Lệch kiến trúc (structural — xếp theo đòn bẩy × phụ thuộc)

### Phase D — DATA PLANE L4 (nền của M1/M2/M3/M6/M7 data-side) ★ đòn bẩy cao nhất
Bất biến kiến trúc: **L3 canonical = nguồn sự thật; L4 = index phái sinh PERSISTED, rebuild được từ L3** (layered §3-4). Hiện L4 không tồn tại.
- **D1** `docker-compose`: đổi `postgres:16` → `pgvector/pgvector:pg16`; enable `vector` + `pg_trgm`.
- **D2** Bảng `chunk` (L4): `unit_id, eid, lang, struct_header, span_text, char_from/char_to, embedding vector(1024), valid_from/valid_to (denormalized từ L3), namespace ('kb'|'tenant:<id>'), model_version, source_version`. **HNSW** index trên embedding; **tsvector** (FTS tiếng Việt) + GIN; index `(namespace, valid_from, valid_to)`.
- **D3** **Embed lúc ingest theo lô** (reference-data-plane §6.3) — `reindex(doc)` chạy sau `load_to_w2`/materialize; idempotent upsert theo `(eid, lang, source_version)`; rebuildable từ L3.
- **D4** `retrieve` đọc L4: **push-down SQL** `as_of ∈ [valid_from,valid_to) AND namespace IN ('kb', tenant)` TRƯỚC, rồi **hybrid** pgvector ANN (`<=>`) + BM25 (`ts_rank_cd`) → **RRF** (c≈60) → **rerank** (port `Reranker`, bge-reranker). Keep-and-mark effect_status vẫn giữ.
- **D5** Cache: embedding/rerank cache key = `(content_hash, model_version)`; result cache key = `f(inputs, as_of, source_version, tenant)` (§6.2 bất biến).
- **D6** W1 idempotent (M7): thêm `source_hash` (sha256) + skip/upsert thay vì raise trùng `frbr_uri`.
- *Fix kèm:* B1 (pin known_as_of), B7 (span-offset + zero-drift assert `"".join==content`).

### Phase T — TENANCY SUBSTRATE L2/P2/P3 (M1-B CRITICAL)
Bất biến: cô lập tenant là **yêu cầu pháp lý** (NĐ 356), phải ở **DB layer**, không app-layer.
- **T1** Bảng `tenant(id, slug, status, isolation_mode, residency_region, retention_mode, kms_key_id)` + `tenant_user(tenant_id, email, role)`; thêm cột `tenant_id NOT NULL` lên bảng khách (`conversations`, `analysis_task`, `audit_log`, chunk-client).
- **T2** Migration áp `rls.rls_ddl` thật: `ENABLE`+`FORCE ROW LEVEL SECURITY` + policy default-deny; **app role NON-OWNER** (sửa docker-compose tạo role `traluat_app` không BYPASSRLS). `get_tenant_db_session` gọi `set_tenant`. **Acceptance test fail-open**: query không `SET` → 0 dòng.
- **T3** `audit_log` **bảng thật append-only** (role chỉ INSERT) thay in-memory; giữ ≥5 năm; ghi route/egress (C5).
- **T4** `tenant.status != active` gate ở `auth`; `retention_mode='zero'` → tắt persist (đọc field đang bị bỏ quên).

### Phase I — INTELLIGENCE THẬT (M4, M5-B, M3-B)
- **I1** `LLMElementJudge(ElementJudge)` qua gateway: 1 call/yếu tố, structured `{satisfied, span}`, temp=0, neo span; bất đồng cross-provider/thấp → HITL. Gate 2 hết là keyword-stub. *(dùng XNLI đã có cho sơ bộ, LLM cho subsumption nặng.)*
- **I2** Model-tier router (stack §5): `gateway.generate(node)` chọn model/effort theo node (Sonnet bulk Review vs Opus hard/Judgment; local vLLM/Qwen cho sensitive). Verifier **khác họ** (answerer≠verifier, F4).
- **I3** EgressPolicy per-segment (M3-B): tag provenance **tại điểm nhập** (origin KB vs upload), không bool `client_data`; `case.facts` luôn tagged.

### Phase S — SERVING SUBSTRATE L7/L11 (M2-B, M6-A/B, M5-A)
- **S1** Async: Celery + RabbitMQ + Redis vào compose; `/analyze` → enqueue → `202 + task_id`; `/tasks/{id}` (IDOR check theo tenant, C6); SSE; header `X-AI-Generated`/`X-Trace-Id`; wire **multi_role mode + PostgresCheckpointer** qua API (hiện dead).
- **S2** Observability: OTel trace + `/metrics` + token/cost theo tenant.
- **S3** Reference-data plane (M5-A, luồng 3): `adapters/<dataset>.py` (Lakehouse→canonical, ép as_of/tenant/provenance, idempotent `(key,version)` upsert, **PII gate**); reference tables (thuế/lương/phạt RULE) + PostGIS (FR-39) + termbank (pgvector); **tier-routing** RULE→ML→LLM (§6.1). Đổi tên `w1/source.py` cho đúng luồng 1.

### Phase P — PRODUCT / GOVERNANCE (sau khi nền vững)
- **P1** W6 workflow services: Review/Draft/Assistant/JudgmentAnalysis/ComplianceDiff/PetitionDraft + `DocumentTypePack`/`TemplateExemplarStore`; role prompt thật (bỏ `query_focus` stub).
- **P2** Precedent store (W4 §2) — `verified_precedents` hiện hard-wire `[]`; dựng bảng + `match_precedents` + nuôi `prune_unsupported`.
- **P3** W7 Experience: UI rà soát/song ngữ/điều hướng trích dẫn (click điều → văn bản tại ngày T); HITL console.
- **P4** Governance: eval-gate vào **CI thật** (`.github/workflows`) + perf §8 (parallel-path byte-identical · recall@k vs brute-force oracle); L14 knowledge-ops (gold annotation); L1 Acquisition gate (license/provenance, chống aggregator); KMS envelope encryption (P3).

---

## 3. Thứ tự đề xuất (dependency-ordered)
```
B1–B6 (bug, 1 lượt)  →  Phase D (L4 index: pgvector+hybrid+push-down)  →  Phase T (RLS+tenant tables)
   →  Phase I (LLM element-judge + model-router + egress intake)  →  Phase S (async+obs+ref-data)  →  Phase P (product/gov)
```
**Vì sao D trước T trước I:** D là nền mọi retrieval đúng-kiến-trúc + sửa luôn perf; T là ship-blocker pháp lý; I cần D (retrieve thật) + T (tenant guard thật) để cross-provider/egress có nghĩa. P là mặt tiền, làm sau cùng.

**Giữ bất biến khi code:** L4 luôn rebuild từ L3 (không thành nguồn-sự-thật-thứ-2); mọi đường ra qua L6 verify + L13 governance; cache key luôn gồm `as_of/version/tenant`; stub→thật chỉ đổi impl của port.
