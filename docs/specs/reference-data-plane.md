# TraLuat — Reference-Data Plane (lớp dữ liệu tham chiếu từ Lakehouse)

> **Pattern CHUNG cho mọi tính năng cần data tham chiếu** (toolbox, directory/map, đa ngữ, template…). Data **không** tự có trong engine — đội data xử lý ở **Lakehouse** rồi đẩy lên theo **schema + API contract**; TraLuat ingest → lưu đúng store → phục vụ qua tầng phù hợp.
> Tổng quát hoá pattern đã dựng cho template (`integration-adapters §8b`, W6 §1.2b). Phân biệt với luồng VBQPPL/bản án (đi qua `meta.json` + W1 stage 1–8) — **đây là luồng thứ 3: reference data**.

---

## 0. Nguyên tắc (mọi dataset tuân)
1. **Đội data sở hữu Lakehouse** (Delta/Iceberg): mỗi dataset = 1 bảng + version, đã chuẩn hoá.
2. **Mỗi dataset có SCHEMA riêng** (như `schemas/meta.schema.json`) = *hợp đồng output*, validate máy được.
3. **1 API contract chung** đẩy lên: **CDC event** (near-real-time) hoặc **scheduled sync** (corpus chậm) → **idempotent upsert** theo `(key, version)`.
4. **Ingestion adapter** (anti-corruption): Lakehouse schema → canonical; **ÉP `as_of`/`tenant`/provenance** tại adapter; không để schema Lakehouse đi sâu hơn.
5. **Chọn STORE theo bản chất dữ liệu** (xem §2). **Phục vụ qua đúng TẦNG** (xem §3).
6. **★ Moat injection:** dataset nào **suy từ luật** (thuế/lương/thời hiệu…) **BẮT BUỘC** mang `valid_from/valid_to + source_eid` → tiện ích vẫn **hiệu-lực-aware** (khác TVPL: calculator *có-nguồn-luật*).
7. **★ PII gate DÙNG CHUNG mọi luồng nạp (F5-fix):** quét PII + quarantine-by-default là **gate ở tầng adapter**, áp cho **CẢ 3 luồng** (meta.json Stage-1 ✓, template `integration-adapters §8b` ✓, **và reference-data-plane này** — vd danh bạ cán bộ FR-40 chứa dữ liệu cá nhân). Không luồng nào bỏ qua. *(RLS tenant đã có W5 §2.3 — đây là lớp PII, khác lớp tenant-isolation.)*

---

## 1. Kiến trúc (một hình)
```
┌─ ĐỘI DATA sở hữu ─────────────┐
│  LAKEHOUSE (Delta/Iceberg)    │  mỗi dataset: bảng + version
└──────────────┬────────────────┘
   ① SCHEMA per-dataset   ② API CONTRACT (CDC/scheduled)
               ▼
   ┌─ Ingestion Adapter ─┐  map→canonical · ép as_of/tenant/provenance · idempotent upsert (key,version)
   └──────────────┬───────┘
               ▼
   ┌─ TARGET STORE (theo §2) ─┐  Postgres bảng · pgvector+BM25 · PostGIS geo
   └──────────────┬───────────┘
               ▼
   phục vụ qua TẦNG (theo §3): RULE-base · ML/vector · Local model · LLM · SQL query
```

## 2. Chọn target store theo bản chất dữ liệu
| Bản chất | Store | Khi nào |
|---|---|---|
| Bảng tra cứu chính xác (thuế suất, lương vùng, mã HS/ngành, mức phạt) | **Postgres (bảng quan hệ)** | giá trị rời rạc, tra khớp khoá |
| Tra mờ / ngữ nghĩa (từ điển, template, cặp dịch) | **pgvector + BM25** | cần similarity |
| Không gian (VPLS, địa chỉ, bán kính "gần bạn") | **PostGIS** | truy vấn khoảng cách/geo |
| Suy từ luật (thời hiệu…) | **không lưu riêng — dùng W2 bitemporal** | cần tính theo luật@T |

## 3. Tầng truy xuất (đúng tool cho đúng việc)
- **RULE-base** (tra bảng, deterministic): calculator, lookup mã, mức phạt — rẻ, chính xác, không model.
- **ML/vector**: từ điển, template, gợi ý mờ.
- **Local model**: trích/chuẩn hoá nhẹ nếu cần.
- **LLM (qua Gateway)**: phân tích sâu trên kết quả đã tra (vd giải thích vì sao mức phạt này).
- **SQL/geo query**: directory + bản đồ.

## 4. Map tính năng → dataset → store → tầng (bảng chốt)
| Tính năng | Dataset (Lakehouse) | Store | Tầng | as_of? |
|---|---|---|---|:--:|
| FR-35 thuế/lương/HS/ngành/phạt | bảng thuế suất · lương vùng · mã HS · mã ngành · mức phạt | Postgres | RULE | ✅ `valid_from/to`+eid |
| FR-35.12 từ điển | termbank định nghĩa | pgvector+bảng | ML+RULE | ✅ neo văn bản |
| ⚡FR-35.13 thời hiệu | — (suy từ W2) | W2 bitemporal | RULE+query | ✅ moat |
| FR-39 directory VPLS + map | danh bạ VPLS (tên/địa chỉ/geo/phone) | **PostGIS**+Postgres | geo+RULE | ⬜ snapshot |
| FR-40 danh bạ cán bộ khu vực | bảng liên hệ công khai | Postgres | RULE/query | ⬜ |
| FR-04+ đa ngữ VN-EN-ZH | cặp dịch + termbank 3 ngữ | pgvector + alignment(W2) | ML+LLM | ✅ neo điều–khoản |
| FR-34 template đơn | template (đã có) | pgvector TES | ML+LLM | — |

## 5. Mỗi dataset mới cần gì (checklist cho đội data)
- [ ] **Schema** riêng (`schemas/<dataset>.schema.json`) — trường + kiểu + bắt buộc + `valid_from/valid_to`/`source_eid` nếu suy-từ-luật.
- [ ] **Delivery:** bảng Lakehouse + chọn CDC hay scheduled; khoá nghiệp vụ + version.
- [ ] **Ingestion adapter** phía TraLuat (`adapters/<dataset>.py`): map→canonical, ép as_of/tenant, idempotent upsert, seam-test đối-kháng.
- [ ] **Store + tầng** đã chọn theo §2/§3.
- [ ] Validate mẫu 20–50 bản trước khi đổ đại trà (pattern giống handoff `meta.json`).

---

## 6. Hiệu suất — routing tầng · caching · batching · tối ưu (BẮT BUỘC consider)

### 6.1 Tier-routing (chọn tầng RẺ-NHẤT-ĐỦ-DÙNG trước)
> Nguyên tắc: đừng gọi LLM cho việc RULE làm được. Định tuyến theo bản chất truy vấn:
```
Query đến → phân loại:
 • tra khớp chính xác (calc param, directory, mã HS/ngành)      → RULE (SQL/bảng)   — KHÔNG model, cache cứng
 • tra mờ/ngữ nghĩa (từ điển, template, gợi ý)                   → ML/vector (bge-m3+BM25+RRF)
 • trích/chuẩn hoá nhẹ                                           → Local model
 • cần sinh văn bản / phân tích / giải thích                      → RAG flow → LLM (qua Gateway)
 • tính theo luật@T (thời hiệu, diff)                            → query bitemporal W2 (+RULE)
```
- **RAG flow** (chỉ khi SINH text, vd đơn FR-34, song ngữ FR-04, giải thích): `retrieve(as_of,tenant) → ground → generate chỉ-từ-cands → verify 3 cổng → abstain` (W3). **KHÔNG** dùng RAG/LLM cho lookup calculator (lãng phí + kém tất định).
- **Egress guard** (W5 §3.1b): data khách không ra Claude API; phân loại trước khi route lên LLM ngoài.

### 6.2 Caching (nhiều lớp — key PHẢI gồm hiệu lực)
> 🔴 **Bất biến: cache key = f(inputs, `as_of`, `law_version`/`dataset_version`, `tenant`).** Thiếu as_of/version → phục vụ kết quả **sai hiệu lực**; thiếu tenant → **rò chéo tenant**.
> 🌐 **Đa ngữ — tách 2 cache (ng.tắc #14):** **(a) legal-conclusion cache** (**language-neutral ≠ tenant-neutral**: key = base invariant **vẫn gồm tenant/as_of/version**, chỉ BỎ chiều ngôn ngữ; kết luận có input tenant → vẫn keyed theo tenant; chỉ kết luận **luật-công-khai thuần** mới tenant-neutral) · **(b) translation/presentation cache** (key **+language**). → suy luận **1 lần**, chỉ render lại EN/ZH.
| Lớp | Cache gì | Invalidate khi |
|---|---|---|
| **Result cache** | kết quả calc tất định (diskcache content-hash) | `dataset_version`/`law_version` bump (W1→W2 có `norm_relation` mới) |
| **Reference-table hot cache** | bảng nóng (thuế/lương vùng) trong Redis — ★ C4-fix: **version-stamp trong KEY** (`dataset_version`/`law_version`) + **TTL backstop** → purge sót cũng tự lành (không chỉ active-invalidate) | upsert dataset version + TTL |
| **Embedding/rerank/LLM cache** | content-hash (pattern legalbenchrag) | đổi model/prompt version |
| **Geo cache** | truy vấn "gần bạn" theo geohash | cập nhật directory |

### 6.3 Batching
- **Ingest:** batch upsert từ Lakehouse (idempotent theo key+version).
- **Embedding:** embed template/từ điển **lúc ingest theo lô**, không per-query.
- **Alignment song ngữ:** căn chỉnh thuật ngữ **offline theo lô**, không per-request.
- **LLM:** gộp request khi có thể; precompute phần tĩnh.

### 6.4 Tối ưu (đẩy việc xuống tầng rẻ)
- **Push-down filter:** lọc `as_of`+`tenant`+geo **trong SQL** TRƯỚC khi vector/LLM (giảm candidate).
- **Materialize/precompute:** bảng param calc materialized; snapshot graph bound-hop (xem `performance.md`); alignment precomputed.
- **Index:** partition/index theo `as_of`; PostGIS KNN (`<->`) cho geo; HNSW pgvector.
- Chi tiết SLO/index/snapshot: **`docs/specs/performance.md`** + **`retrieval-and-storage-mechanisms.md`** (đừng lặp — spec này chỉ nối).

## 7. Steal-list (đã search — `competitive-landscape.md §5–6`)
| Tính năng | Học từ | Chế độ | Tự build (greenfield) |
|---|---|---|---|
| FR-35 calc neo-luật | **OpenFisca** (dated-parameter + reference + as-of) | học pattern, **tự viết** (AGPL + VN-specific) | **dated-LOGIC** (công thức theo ngày) — OpenFisca không có |
| ⚡FR-35.13 thời hiệu | docassemble (interview logic) | học | **tính theo luật tố tụng@T, neo điều** — greenfield cả OSS+TM |
| FR-39 map | PostGIS `ST_DWithin`/KNN + OSM/Nominatim + Leaflet/MapLibre | wire-as-lib | data-freshness VN |
| FR-40 danh bạ | **My-Reps (MIT)** geocode→đa-giác→bảng | port | roster + freshness VN |
| FR-04+ đa ngữ | **Akoma/ELI** (neo), **VLQA** (đích VN), multi-agent map concept, data TQ (MIT) | học/port | term-bank concept VN-EN-ZH + alignment điều-khoản |

---

## 8. Luật mới → trigger + auto-update (tách DATA-auto vs RULE-human)

### 8.1 Ranh giới (ai chịu gì)
| Việc | Ai |
|---|---|
| Watch nguồn chính thống, phát hiện luật mới, crawl/API | **ĐỘI DATA** (họ đẩy lên) |
| Chuẩn hoá + đẩy theo contract (kèm **tín hiệu thay đổi**) | **ĐỘI DATA** |
| Nhận → bitemporal append · phân loại tác động · propagate | **SYSTEM** |
| Rà rule đổi | **PHÁP CHẾ** |
> **System KHÔNG crawl.** Nhưng 2 thứ vẫn là của system (đừng rơi khe): **(a) contract phải có tín hiệu thay đổi** (new/amend/repeal + ngày hiệu lực + target bị sửa); **(b) staleng guard ở CỬA NHẬN** — không nhận update quá N ngày từ nguồn đáng-lẽ-có → **BÁO ĐỘNG (fail-loud)**, không im (im = serve luật cũ). *(trust-but-verify, không phải tự crawl)*

### 8.2 Hai loại update — KHÁC HẲN
| | **DATA** (VB mới/sửa) | **RULE** (meta-rule đổi) |
|---|---|---|
| Ví dụ | NĐ mới, TT sửa Điều X | Luật Ban hành VBQPPL đổi thang bậc; đổi hồi tố |
| Xử lý | **AUTO-propagate** | **AUTO-DETECT → HUMAN duyệt** (không auto-rewrite rule) |

### 8.3 Pipeline
```
Data đẩy (contract có change-signal)
 → ① bitemporal APPEND (version mới, KHÔNG ghi đè — W2)
 → ② phân loại tác động:
    (a) DATA-only → AUTO: refresh index · alert FR-09 · ComplianceDiff · invalidate cache
    (b) RULE-affecting → FLAG hàng đợi pháp chế (legal-rule-base §5)
 → ③ audit trail
```
- **Phát hiện RULE-impact qua `source_eid`:** VB mới amend/repeal một `source_eid` rule base đang dùng → auto-flag rule đó. *(không bắt được luật net-new → cần human re-review định kỳ, legal-rule-base §5)*

### 8.4 v1 vs Phase-2 (đừng build quái vật)
| | v1 (an toàn, thủ công) | Phase-2 (auto) |
|---|---|---|
| Nhận + append | ✅ bitemporal | — |
| Phân loại data/rule | thủ công/flag | impact-classifier **fail-safe→human** |
| Cache invalidate | **rộng tay** (an toàn) | dependency-aware (theo norm_relation) |
| Hồi tố re-eval vụ cũ | flag thủ công | auto re-eval |
| Staleng guard | ✅ báo động | — |
> **v1 = nạp (do data đẩy) + bitemporal append + người rà rule + báo-động-stale.** Auto-classifier/invalidation/hồi-tố-ngược = Phase-2. *Auto mà sai = nhân lỗi, nguy hơn thủ công.*

### 8.5 Bất biến
1. **Bitemporal = APPEND, không ghi đè** — bản cũ vẫn truy được (văn bản tại ngày T).
2. **Rule đổi = human-gated**, không auto-rewrite từ text thô.
3. **Cache invalidate theo `law_version`** (§6.2); v1 rộng tay, Phase-2 theo phụ thuộc.

---

> Một câu: **mọi tính năng = (data ở Lakehouse theo schema+contract) → adapter ép as_of/tenant → store đúng loại → phục vụ đúng tầng (rẻ-nhất-đủ-dùng) → cache theo key-có-hiệu-lực → batch/precompute.** Không tính năng nào "tự có data"; dataset suy-từ-luật luôn hiệu-lực-aware; cache key luôn gồm as_of+version+tenant; **luật mới = DATA auto-append / RULE human-duyệt.**
