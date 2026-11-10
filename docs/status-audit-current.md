# TraLuat — Status audit (hiện tại) · 65 commit · 201 test · 13 migration

> Kiểm kê thật trạng codebase vs 41 FR + 6 CN. ✅ xong (có test) · 🟡 một phần/khung · ❌ chưa.
> Cập nhật sau: WP1–7, ML thật, graph+Neo4j+GDS, geo PostGIS+UI, alerts, OTel, HSM.

## A. 15 layer / 5 plane
| Layer | Trạng thái | Bằng chứng |
|---|---|---|
| L1 Acquisition | ✅ khung | `w1/acquisition` license-gate (chặn aggregator) + provenance + dedup |
| L2 Ingestion | ✅ | `w1/{structure,metadata,relations,source}` · OCR dòng (`ocr_vietocr`) + **full-page port** (`ocr_detect`: GridLineDetector/Paddle lazy/FullPageOCR) |
| L3 Canonical bitemporal | ✅ **moat #1** | `w2/{bitemporal,repo,models}` reconstruct_as_of · effect_status · materialize-gate · GiST no-overlap |
| L4 Index | ✅ | `Chunk` pgvector HNSW + FTS · `w3/indexer` embed-lô · push-down SQL |
| L5 Retrieval | ✅ | `w3/retrieval` hybrid BM25+dense+RRF (bge-m3 thật) · keep-and-mark · multihop |
| L6 Grounding | ✅ | `w3/grounding` gate1/2/3b + NLI (XNLI thật) · R1 abstain · orchestrator |
| L7 Model runtime | ✅ / 🟡 | `w3/gateway` router model-tier · bge-m3/XNLI/VietOCR thật · 🟡 **vLLM local ❌ (chờ GPU)** |
| L8 Reasoning | ✅ | `w4` Auditor hard-gate · Researcher→Adjudicator · multi-role · durable checkpoint |
| L9 Workflow | ✅ logic / 🟡 API | `w6/workflows` Review·ComplianceDiff·PetitionDraft·Judgment (có test) — **chưa expose REST** |
| L10 JurisdictionPack | ✅ | `w6/jurisdiction` rank/roles theo vùng, portability |
| L11 API | ✅ / 🟡 | `w5/api` /analyze·/review·/graph·/directory·/alerts·/metrics·/health + JWT+RBAC · 🟡 thiếu endpoint lookup/draft/diff/judgment |
| L12 Experience | ✅ | `/`(analyze) · `/graph`(Cytoscape) · `/review` · **`/directory`(Leaflet bấm toạ độ)** · 🟡 React/song-ngữ đầy đủ ❌ |
| L13 Governance | ✅ | audit write-ahead · eval-gate (loader+gate CI) · nhãn AI · HITL |
| L14 Knowledge-Ops | ✅ khung | `knowledge_ops` queue+approve→materialize+post-hook · 🟡 gold data (chuyên gia) ❌ |
| P1 Infra | ✅ | compose (pg **gộp pgvector+PostGIS** / rmq / redis / neo4j+GDS / prom / grafana) · CI |
| P2 Tenancy | ✅ | FORCE RLS + non-owner role + IDOR (task) — test no-fail-open |
| P3 Security | ✅ | EgressPolicy residency · KMS envelope+crypto-shred · **HSM/cloud KMS port** (Aws/Vault/Remote) |
| P4 Observability | ✅ | `/metrics` Prometheus + **OTel tracing** (`w5/tracing` span, optional) + compose prom/grafana |

## B. 41 FR — trạng thái
**MOAT (10):**
- FR-01 văn-bản@T ✅ · FR-02 omission ✅(ReviewService) · FR-03 judgment ✅ logic / 🟡 no-endpoint
- FR-04 song ngữ: **EN ✅** (retrieval cross-lingual + termbank VN-EN-ZH) · ZH 🔵 defer-theo-spec
- FR-05 citation verifier 3-cổng+abstain ✅ · FR-06 đa-vai ✅ · FR-07 LAW-TRUE ✅
- FR-08 ComplianceAdvisory 🟡 (nhóm-2, chưa làm) · FR-09 alert ✅ (subscribe→materialize→fan-out)
- FR-41 cross-doc conflict: **resolution ✅** (lex superior/posterior/abstain + số) · detection 🟡 (semantic port có stub, model thật defer)

**PARITY (9):** FR-10 hybrid retrieval ✅ · FR-11 Q&A grounded ✅ logic (`service.lookup`) / 🟡 no-endpoint · FR-12 eId ✅ · FR-13 graph ✅ · FR-14 **tóm tắt ❌** · FR-15 soạn HĐ ✅ logic / 🟡 no-endpoint · FR-16 review ✅ · FR-17 RLS ✅ · FR-18 UI song-ngữ 🟡

**DATA/PIPELINE (7):** FR-19 ingest+dedup ✅ · FR-20 OCR+parse ✅ (port full-page) · FR-21 metadata ✅ · FR-22 quan hệ ✅ · FR-23 citation-engine ✅ · FR-24 giải xung đột ✅ · FR-25 chunking ✅

**PLATFORM/GOV (5):** FR-26 JurisdictionPack ✅ · FR-27 eval-gate ✅ (🟡 gold data chuyên gia) · FR-28 observability ✅ · FR-29 knowledge-ops ✅ · FR-30 gateway phân-tầng+egress ✅

**BACKLOG/DEFER:** FR-31 vai mở rộng ❌ defer · FR-32 loophole ❌ defer · FR-33 change-propagation ❌ defer · FR-34 đơn-từ ✅ logic (PetitionDraft) / 🟡 no-endpoint

**GIỮ CHÂN/TIỆN ÍCH (FR-35…40):**
- FR-35 toolbox: **4/14** calculator ✅ (35.1 TNCN, 35.7 lương vùng, 35.11 phạt GT, lệ phí) · **⚡35.13 thời hiệu tố tụng (moat-item) ❌** · 35.2–35.6/35.8–35.10/35.12/35.14 ❌
- FR-36 doc-compare 2-ngày-bất-kỳ ✅ logic (`ComplianceDiffService.diff`) / 🟡 no-endpoint
- FR-37 effectivity-graph viz ✅ (`/graph` time-travel) · FR-38 forms ✅ (template store)
- FR-39 directory+map ✅ (PostGIS nearby + `/directory` Leaflet + seed 13 cơ quan) · FR-40 danh bạ công ✅ (cùng bảng)

## C. 6 CN (ràng buộc cứng)
CN-01 residency+egress fail-closed ✅ · CN-02 nhãn AI ✅ · CN-03 high-risk HITL+log ✅ · CN-04 án lệ ràng buộc 🟡(effect_status có, chưa rule án-lệ riêng) · CN-05 nguồn hợp-pháp+ẩn-danh ✅(license-gate) · CN-06 key-per-tenant+zero-retention ✅

## D. 3 model ML THẬT (M5 MPS)
bge-m3 (1024d dense cross-lingual) · XNLI mDeBERTa (NLI + element-judge) · VietOCR (OCR dòng VN) — tất cả optional dep, lazy, importorskip.

## E. Khoảng trống plannable (code được ngay, KHÔNG chờ ngoài)
1. ✅ **ĐÃ XONG — API expose L9**: `POST /lookup` (FR-11) · `POST /draft` (FR-34/15, client→local, R2 no-failover) · `GET /compare` (FR-36 doc-diff T1↔T2) · `POST /judgment` (FR-03, CN-03 HITL). + trang `/tools` (3 form) + RBAC + test (7). 208 passing.
2. ✅ **ĐÃ XONG — ⚡FR-35.13 thời hiệu tố tụng** (moat-item) + **35.14 lịch/đếm ngày** (nền): `w1/calendar_vn` (add_period ngày/tháng/năm kẹp-cuối-tháng, next_business_day lùi ngày nghỉ) + `w1/deadlines` (compute_deadline neo điều luật, hiệu-lực-aware, lùi lễ từ reference) + `@calculator("thoi_hieu")` + `GET /deadline` + form `/tools` + seed 7 loại thời hạn + lễ. Test 14 (7 calendar + 7 deadline). **Âm-dương đầy đủ = defer** (cần ephemeris) — ngày lễ âm lấy từ reference-data `ngay_nghi`.
3. **FR-14 tóm tắt** VB/vụ việc (grounded, cite-or-abstain).
4. **FR-35 thêm calculator** dùng-nhiều: 35.6 gross↔net, 35.2 GTGT, 35.9 làm thêm giờ.
5. **FR-41 detection** (semantic conflict) — port có stub, cần model/heuristic thật.
6. **UI song-ngữ** (FR-18) + React nếu cần UX sâu.

## F. Chặn bởi NGOÀI (không code được thêm)
- vLLM local (cần GPU) · API key Claude thật · **gold moat set** (chuyên gia label) · **data thật** (thuế/lương/phạt/toạ độ danh bạ/template) · `authority_rank` 2025 (primary-text) · 20–50 `meta.json` thật · Paddle/CRAFT model (full-page OCR) · AWS KMS/Vault + boto3/hvac · OTel collector/Jaeger.
