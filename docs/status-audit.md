# TraLuat — Status audit (làm rồi / chưa) · 52 commit · 169 test · 10 migration

> Kiểm kê thật trạng codebase vs specs/15-layer/41 FR. ✅ xong (có test) · 🟡 một phần/khung · ❌ chưa.

## A. 15 layer / 5 plane
| Layer | Trạng thái | Bằng chứng |
|---|---|---|
| **L1 Acquisition** | ✅ khung | `w1/acquisition` — license gate (chặn aggregator ToS) + provenance + dedup |
| **L2 Ingestion** | ✅ | `w1/{structure,metadata,relations,source}` · OCR line-level (`ocr_vietocr`) · 🟡 full-page detector ❌ |
| **L3 Canonical bitemporal** | ✅ moat #1 | `w2/{bitemporal,repo,models}` — reconstruct_as_of · effect_status · materialize gate · GiST no-overlap |
| **L4 Index** | ✅ | `w2/models.Chunk` pgvector HNSW + FTS · `w3/indexer` embed-theo-lô · push-down SQL |
| **L5 Retrieval** | ✅ | `w3/retrieval` hybrid BM25+dense+RRF (bge-m3 thật) · keep-and-mark · multihop graph |
| **L6 Grounding** | ✅ | `w3/grounding` gate1/2/3b + NLI (XNLI thật) · R1 abstain · `orchestrator` |
| **L7 Model runtime** | ✅ | `w3/gateway` (Claude + router model-tier) · bge-m3/XNLI/VietOCR thật · 🟡 vLLM local ❌(chờ GPU) |
| **L8 Reasoning** | ✅ | `w4` Auditor hard-gate · Researcher→Adjudicator · multi-role · checkpoint |
| **L9 Workflow** | 🟡 | `w6/workflows` ComplianceDiff·Judgment·Review ✅ · Draft/Assistant/Petition ❌ |
| **L10 JurisdictionPack** | ✅ | `w6/jurisdiction` — rank/roles theo vùng, portability |
| **L11 API** | ✅ | `w5/api` /analyze·/lookup·/graph·/metrics·/health + JWT+RBAC |
| **L12 Experience** | 🟡 | `/` form + `/graph` Cytoscape viz · 🟡 review-UI/song-ngữ đầy đủ ❌ |
| **L13 Governance** | ✅ | audit write-ahead · eval-gate (CI) · nhãn AI · HITL (`knowledge_ops`) |
| **L14 Knowledge-Ops** | ✅ khung | `knowledge_ops` queue + approve→materialize + gold export · 🟡 gold data (chuyên gia) ❌ |
| **P1 Infra** | ✅ | docker-compose (pg/rmq/redis/neo4j/prom/grafana) · CI |
| **P2 Tenancy** | ✅ | FORCE RLS + non-owner role + IDOR (task) — test no-fail-open |
| **P3 Security** | ✅ | EgressPolicy residency · KMS envelope (crypto-shred) · 🟡 HSM thật ❌ |
| **P4 Observability** | 🟡 | `/metrics` Prometheus + compose prom/grafana · 🟡 OTel trace ❌ |

## B. Năng lực moat (có test)
✅ Bitemporal "văn bản tại ngày T" · effect_status keep-and-mark · materialize gate · resolve_conflict (lex superior/posterior/abstain) · **FR-41 conflict detect** (số) · grounding cite-or-abstain · Auditor element-wise (NLI thật) · reasoner đa vai · **đồ thị tri thức** (CTE + Neo4j + GDS PageRank/Louvain + viz Cytoscape) · tenancy RLS · egress residency · KMS.

## C. 3 model ML THẬT (chạy M5)
✅ bge-m3 (dense retrieval) · XNLI mDeBERTa (gate3 + element-judge) · VietOCR (OCR dòng). ❌ Vintern (incompat transformers 5) · legal-NLI fine-tune · local LLM (Qwen).

## D. 41 FR — theo nhóm
- ✅ **Engine/moat:** grounding·bitemporal·omission(ReviewService)·conflict(FR-41)·compliance-diff(FR-36)·graph(FR-37)·judgment-analysis.
- 🟡 **FR-09 alert luật mới:** phát hiện+queue+materialize ✅ · *gửi thông báo* ❌.
- 🟡 **FR-35 toolbox (14 calc):** data-plane `reference_value` hiệu-lực-aware ✅ · *14 calculator cụ thể* ❌.
- ❌ **FR-34 soạn đơn** (template/TES learning) · **FR-38 biểu mẫu** · **FR-39 danh bạ LS+map (PostGIS)** · **FR-40 danh bạ cơ quan** · **tam ngữ VN-EN-ZH** (mới có lang param, chưa dual-index cross-lingual).

## E. Chưa làm / giới hạn (tổng hợp)
- **Cần input ngoài:** API key (Claude thật) · gold moat (chuyên gia label) · `authority_rank` 2025 (primary-text, đang provisional) · 20–50 meta.json thật · nguồn chính thức (L1 connector thật).
- **Cần stack chạy:** Celery worker (code ✅, broker chạy) · OTel backend · vLLM local (GPU).
- **Chưa code:** OCR full-page detector · FR-34/38/39/40 · tam ngữ · frontend đầy đủ (review-UI/song-ngữ) · PostGIS geo · HSM.
- **Known-limitation (audit Round 5–8):** chunk L4 tenant app-level (chưa RLS) · lookup query-trust · D6 frbr-dedup · reviewer-sign · ref non-overlap · metrics escape · asgi prod-wiring · Neo4j projection consistency-window (đã document).

## F. Chất lượng
169 test (pure + PG + 3 model + Neo4j/GDS) · 8 vòng review tìm+sửa **6 bug thật** (egress dead-route · stale-chunk · IDOR-superuser · numeric-divergence · LicenseGate-lstrip · PII-false-positive) · CI gate (.github) · ADR-0001 (graph engine).
