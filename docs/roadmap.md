# TraLuat — Roadmap

> Lộ trình từ nền móng đến tầm nhìn "nuốt trọn thị trường + thẩm định bản án".
> Đọc kèm: `docs/architecture.md`.
> Trạng thái: bản thảo định hướng. Các mốc được sắp theo **phụ thuộc**, không theo lịch — calendar phụ thuộc quy mô đội/ngân sách, sẽ hiệu chỉnh sau.

---

## Nguyên tắc roadmap

1. **Dependency-ordered, không calendar-ordered.** Mỗi phase mở khoá phase sau. Nhảy cóc = xây trên móng rỗng.
2. **Mỗi phase có GATE ra bằng số.** Đặc biệt: không xây reasoning/đa vai khi grounding chưa qua benchmark. Benchmark là cửa, không phải báo cáo cuối.
3. **Hẹp mà sâu trước, rộng sau.** Lát FDI (đầu tư/lao động/thuế) + vài loại hợp đồng, làm cho đúng tới từng điều–khoản; rồi mới mở rộng diện.
4. **Verify-first.** Ba việc xác minh pháp lý/nguồn phải xong *trước* khi code chạm dữ liệu thật (xem cuối tài liệu).
5. **Moat trước, mặt tiền sau.** Dồn người giỏi nhất vào tầng 1–2 (data/grounding). Tầng workflow fork được từ Claude for Legal.
6. **★ Model đủ-tốt, KHÔNG đua model.** Thắng bằng **data bitemporal + grounding + rule base**, không bằng model to (general+RAG ≈ legal-LLM — đã verify). Giai đoạn đầu **dùng Claude API, KHÔNG train gì**; self-host/fine-tune chỉ khi benchmark/residency đòi. *(stack-db §5, legal-rule-base)*

---

## Bản đồ phase (tổng quan)

```
Phase 0  Nền dữ liệu hiệu lực        ──►  moat #1 sống
Phase 1  MVP: Review + grounding      ──►  bán được "việc đã xong" đầu tiên
Phase 2  Song ngữ + Trust hardening   ──►  đủ chuẩn cho khách FDI thật + tuân thủ
Phase 3  Judgment & Precedent engine  ──►  năng lực không ai có
Phase 4  Reasoner đa vai              ──►  "tòa án trong máy"
Phase 5  Diện rộng + Portability      ──►  nuốt thị trường + nước thứ 2 (ASEAN)
```

---

## ★ NÊN LÀM NGAY (bước kế tiếp cụ thể — dependency-ordered)

> 🧭 **ĐÂY LÀ ORDER-LIST MASTER.** Khi 3 nguồn nói về thứ tự, ưu tiên: **cái này > `CONTRIBUTING` build-order (chi tiết mỗi mảng) > `spec-audit-fixes` ship-order (chi tiết sửa lỗi).** Phân vân thì theo mục này.
> Chắt từ quyết định session này. Làm đúng thứ tự, mỗi cái mở khóa cái sau.
1. **Khóa data vào** — đội data gửi **20–50 mẫu `meta.json` thật (gồm ca khó)** → validate → **chốt W1 mapping**. *(contract đã giao: `TraLuat-data-handoff.zip`)*
2. **Khóa rule base** — **pull primary-text** chốt `authority_rank` 4 thời kỳ (80/2015 · 63/2020 · 64/2025 · 87/2025) + Đ.55/Đ.156/Đ.58 → gỡ cờ "chưa official" trong `legal-rule-base.md`.
3. **Xây lõi #1 (W1+W2+W5 song song → W3)** — acceptance xanh ĐẦU TIÊN = **"văn bản tại ngày T"** (W2 §8). Model: **Claude API + bge-m3/VN embed, KHÔNG train.**
4. **Dựng eval harness SỚM** — LegalBench-RAG method + **tự build gold set effectivity/omission/conflict** (moat eval) + VLegal-Bench baseline. *(W3 §4)*
5. **Beachhead mỏng** = FDI compliance/contract review trên lõi #1 — 1 lĩnh vực, bán được.
6. **Nâng cấp SAU, chỉ khi có số/cầu:** Qwen2.5-32B self-host (residency) · fine-tune domain (nếu conflict/omission chưa đạt) · tiện ích/directory · đa ngữ ZH.

**KHÔNG làm sớm:** đua model to/train LLM · kho+cộng đồng (sân TVPL) · tiện ích/ZH trước lõi · chờ "hoàn hảo" (CMC/LuatVietnam đang xây AI — cắm cờ #1 trước).

**★ Ship-blocker từ CHAOS validation (Round-3) — fail-OPEN phải đóng TRƯỚC go-live:**
- **R1 Sufficiency floor runtime** (thiếu luật khống chế = trả sai qua hết cổng) — lỗ nguy nhất, đúng cái platform hứa ngăn. Spec xong (W3 §2), **impl = ship-blocker**.
- **R2 Egress circuit-breaker** (local down → cấm failover Claude) + **R3 query-time pending-repeal caveat**. Spec xong, impl trước khi nhận tenant/dữ liệu thật.
- **Đã fix + gửi lại đội data:** S1 null-anonymization · S2 ngày rác · S3 NFC (schema+validator trong `TraLuat-data-handoff.zip`).

**IOU có cổng (từ audit Round-2+3 `spec-audit-fixes.md`) — chưa fix bằng spec, cần build + data:**
- **Misuse/defensive-only policy** (X3) · **2nd local model** (cross-provider cho tenant residency, F4) · **zero-retention tmpfs+reaper** (X5) · **TES provenance gate** (X7).
- **Conflict DETECTION** (model + gold-set) → cổng: trước khi bật FR-41 "tự tìm xung đột" (v1 chỉ "giải cái đã-flag").
- **Gold eval set effectivity/omission/conflict** (chuyên gia label) → cổng: feature nào chưa có gold tương ứng = **experimental**, không go-live.
- **Model local THỨ-2 khác họ** (cross-provider cho tenant residency) → cổng: trước khi nhận tenant nhạy cảm cao cho Judgment/đa-vai.
- **Dataset quan hệ sửa đổi/bãi bỏ** (recall-gated) → cổng: trước khi tin effectivity tự động ở scale.

---

## ✅ ĐÃ IMPLEMENT (lát dọc W1→W2→W3, 13 commit, 48 test xanh)

> Trạng thái code tới commit `d777103`. Lõi `src/traluat/` + `tests/`. DB: Postgres 16 qua docker-compose (`traluat-pg:5433`), bất biến do GiST EXCLUDE gác.

**W2 — Bitemporal "văn bản tại ngày T" (moat #1) — XONG lõi.**
- `reconstruct_as_of` · `document_as_of` (ghép cây theo parent_id) · `effect_status` enum (in_force·expired_citable·transitional_applies·not_yet·absent) · `citable_text` (keep-and-mark).
- `apply_amendment` interval-split + idempotent + same-date fold · `repeal` · `materialize` **gate** (approved OR auto-safe≥θ; repeals/replaces/amends KHÔNG auto) · `resolve_conflict` (hiệu-lực-gate → lex superior → lex posterior → abstain) · `correct_valid_from` (R5 tx-time) · `multihop` (CTE bounded-hop, cycle-guard).
- Bất biến **no-overlap do DB** (`uv_no_overlap` GiST EXCLUDE) — không phải app gác.

**W1 — Data pipeline (text thô → W2) — XONG 4 slice.**
- `parse_structure` (Chương/Mục/Điều/Khoản/Điểm → cây eId ổn định) · `extract_metadata` (số VB/loại/cơ quan/ngày ký/hiệu lực; doc_type suy từ hậu tố) · `extract_effective_overrides` (phased-commencement cấp Điều/Khoản) · `extract_relations` (cue-phrase → amends/replaces/repeals/cites/guides).
- `ingest_document` toàn trình (không cần tham số tay) · `load_relations_to_w2` → `norm_relation` **needs_review** → nối materialize gate (khép vòng data→W2).

**W3 — Retrieval + Grounding + Orchestration — XONG khung đầy đủ (lõi tất định + port cắm-được).**
- Lõi tất định (chạy KHÔNG cần model): `build_chunks` giữ-span zero-drift (span_text neo ≠ embed_text có header, M1) · `retrieve` keep-and-MARK effect_status@as_of (trả version-tại-ngày) · gates `gate1`/`gate2` (H3)/`gate3b` exactness · `ground` **R1 sufficiency floor**.
- **Port cắm-được + stub chạy ngay** (`w3/ports.py`): `LLMGateway`·`NLIVerifier`·`Embedder`·`Reranker`. `BaseLLMGateway` (guard tenant · wrap_untrusted X1 · cache content-hash theo tenant · audit · nhãn AI) + `EchoLLMGateway` (stub) + **`ClaudeLLMGateway`** (THẬT: Opus 5.5 + structured outputs; thiếu credential → `NotConfigured`). Stub: `HashEmbedder`/`NoopReranker`/`HoldNLI`.
- **Orchestrator** `answer_question`: vòng `retrieve→generate→verify→sufficiency→abstain/answer` + caveat **R3** (pending repeal/replace/amend) + confidence (F10 placeholder) + effect_status@as_of.
- **Eval harness** (`eval_harness.py`): `GoldCase`+`run_eval`+`EvalReport` 3-chiều + abstention 4-cell + Brier + `char_pr`. Gold set cắm vào là chạy.
- **Data-plane adapter** (`w1/source.py`): `DocumentSource` Protocol + `ingest_source` batch (lỗi 1 VB không chặn mẻ). Đội data cắm API thật = implement `fetch()`.

**⚡ CẮM LÀ CHẠY (khung xong, chỉ chờ input ngoài — KHÔNG phải viết lại kiến trúc):**
- **API key** → `ClaudeLLMGateway` call thật (đã có structured-output contract + abstain).
- **bge-m3 + BM25 + rerank** → implement `Embedder`/`Reranker` port, hybrid blend vào `retrieve`.
- **NLI model** → implement `NLIVerifier` (gate3 promote/hold — đã nối vào `ground`/orchestrator).
- **20–50 `meta.json` + VB thật** → `JsonlFileSource`/`DocumentSource.fetch`, chốt W1 mapping.
- **Gold set effectivity/omission/conflict** → `GoldCase` vào `run_eval`, bật CI gate.
- **primary-text** → điền số `authority_rank` 2025 trong `legal_rule_base` (gỡ provisional).

**W4 — Reasoning engine (Auditor hard-gate + orchestrator một-lượt) — XONG moat + engine.**
- `auditor.audit`: cổng TIỀN-output 3 tầng — (1) trích dẫn có thật · (3) ngày hiệu lực (cắm `repo.citable_text`; TRANSITIONAL giữ+đánh dấu, H3 version-match; rớt → KHÔNG tốn lời gọi) · (2) **element-wise** (áp dụng ⇔ MỌI yếu tố thoả, không holistic) · `prune_unsupported`. `ElementJudge` port + stub. `audit_trail` giữ mọi điều + lý do loại.
- `ReasoningEngine.analyze` (mode='single'): per-party `Researcher`(uỷ W3 `retrieve`)→`Auditor`→`Adjudicator`. Hợp đồng thu hẹp (verified ⊆ candidate), verified-set rỗng → **abstain insufficient_basis** (H1), cổng hậu-draft = W3 `ground`. Interface `Adjudication` cho W5/W6.

**W5 — Backend serving (slice-1: lõi bảo mật tất định) — XONG moat vận hành.**
- `TenantContext` (ép tenant_id, RBAC `require_role`) · `EgressPolicy` (C1: phân loại provenance fail-closed; **R2: dữ liệu khách local-down → DENY/HITL, KHÔNG failover Claude**) · `AuditLog` write-ahead (C5, append-only, ghi route/residency không nội dung) · `LegalService` bọc `ReasoningEngine` (bất biến: không request thiếu tenant_id · mọi response có nhãn AI + trace_id · dữ liệu khách không ra Claude).

**CHƯA CÓ KHUNG (net-new, cần build khi tới phase):** OCR (Vintern, ML) · L-MARS 6-lớp + Faith-Search · conflict DETECTION (FR-41, model+gold) · W4 Reasoner đa vai LangGraph (Phase 4) · W5 infra-lift (FastAPI/Celery/RLS `FORCE ROW LEVEL SECURITY`/KMS envelope — cắm trên `LegalService`) · W6 platform/JurisdictionPack/workflow UI.

---

## Phase 0 — Nền dữ liệu hiệu lực (moat lõi, làm TRƯỚC mọi thứ)

**Vì sao trước:** không có tầng này thì mọi tính năng phía trên chỉ là LLM rà hợp đồng chung chung — đúng cái thị trường đã có và đang bị chê.

**Việc chính:**
- Dựng schema canonical (mục 3 kiến trúc) + kho bitemporal (XTDB/Postgres).
- Pipeline nạp bước [1]–[6]: OCR → cấu trúc hoá → trích metadata → **trích quan hệ sửa đổi/bãi bỏ** → **versioning/tái dựng điều tại ngày T**.
- Nạp **lát luật lõi FDI**: đầu tư, lao động, thuế (Luật + Nghị định + **Thông tư** trung ương trước; địa phương sau).
- Neo trích dẫn tới điều–khoản–điểm.

**REUSE:** Akoma Ntoso, ELI, LegalRuleML, FRBR/LRMoo, XTDB (MPL-2.0).
**BUILD:** bước [5][6] — bộ trích quan hệ quy phạm + tái dựng bitemporal (không ai giải).

**GATE ra (đo được):**
- Cho một điều luật bất kỳ trong lát lõi + một ngày T → trả về **đúng văn bản tại T** (đã áp dụng/loại các sửa đổi–bãi bỏ) với độ chính xác ≥ ngưỡng đặt ra trên tập vàng.
- 100% đơn vị có `ngày hiệu lực` + liên kết NormRelation kiểm được.

---

## Phase 1 — MVP: Contract Review + grounding (brief bước 3–5)

**Mục tiêu:** sản phẩm bán được đầu tiên — rà hợp đồng ra "việc đã xong" có trích dẫn.

**Việc chính:**
- Tầng 2: RAG cấp điều–khoản, hiệu lực-aware, hybrid + Citation Verifier (3 cổng).
- **Contract Review** (HĐLĐ + hợp đồng FDI) → rủi ro + **điều khoản bỏ sót** + checklist tuân thủ.
- Omission detection: `RequiredClauseRule` gắn-thời-điểm trên taxonomy CUAD (41 loại), kiến trúc retrieval-rồi-review.
- **Assistant** có trích dẫn (một ngôn ngữ trước).
- **Benchmark harness 3 chiều** + seed test set ≥50 case có đáp án chuẩn: *đúng điều–khoản / đúng hiệu lực / bắt bỏ sót* — so với 1 baseline LLM, in bảng điểm.

**REUSE:** CUAD/ContractNLI/MAUD (CC BY 4.0), LegalBench-RAG (MIT), bge-m3, PAKTON (Apache-2.0); fork **Claude for Legal** cho khung playbook/checklist.
**BUILD:** omission gắn-thời-điểm; Citation Verifier cổng (3) khớp-nguyên-văn.

**GATE ra:** TraLuat **thắng baseline LLM có ý nghĩa** trên cả 3 chiều, đặc biệt *đúng hiệu lực* và *bắt bỏ sót* (nơi baseline yếu nhất). Đây là bằng chứng moat.

---

## Phase 2 — Song ngữ + Trust hardening (brief bước 6)

**Mục tiêu:** đủ tin cậy & tuân thủ để phục vụ khách FDI thật.

**Việc chính:**
- **Term base VN-EN** + căn chỉnh khái niệm (full/partial/non-equivalent); song ngữ ngang hàng cho Review + Assistant + Draft.
- Trust tier: confidence/abstention, audit trail đầy đủ, HITL queue, tenant isolation.
- Tuân thủ: hosting trong VN/khu vực + zero-retention (NĐ 356/2025), gắn nhãn AI (Luật 71/2025), xác định nghĩa vụ theo vai (Luật AI 134/2025).

**REUSE:** MTet law-subset + Official Gazette EN (quyền rõ ràng) làm hạt giống term base — **không scrape aggregator**.
**BUILD:** term base khái niệm + kiểm nhất quán hai bản (bản VN controlling).

**GATE ra:** output song ngữ ngang hàng, mọi câu giữ **hợp đồng đầu ra** (mục 9 kiến trúc); audit trail reproducible; vượt rà soát tuân thủ nội bộ.

---

## Phase 3 — Judgment & Precedent engine (năng lực khác biệt nhất)

**Mục tiêu:** đưa bản án vào → *đáng ra xử thế nào · đúng/sai · căn cứ điều luật · neo án lệ*. Gần như first-of-its-kind, không ai (kể cả global) đang bán.

**Việc chính:**
- Nạp **án lệ** (KB nhỏ ~82–90, tuyển chọn, có cấu trúc → *curated-KB + matching*, không cần retrieval quy mô lớn) + **bản án** (theo thỏa thuận TANDTC).
- **Liên kết bản án ↔ điều luật ↔ án lệ** (đồ thị); trích dẫn định dạng VN (tự xây, eyecite không dùng được).
- **Effective-dating kép**: án lệ tự hủy khi điều luật nền đổi (Điều 9(1) NQ 04/2019) → nối thẳng Phase 0.
- Judgment Analysis dùng doctrinal hook **"áp dụng-hoặc-giải-thích"**; schema nhãn **ALQAC 2026**.

**BUILD:** gần như toàn bộ (đất trống). **REUSE (ý tưởng):** AALawyer, CBR HYPO/CATO/Horty cho tầng giải thích.

**GATE ra:** trên tập bản án có đối chiếu chuyên gia, engine chỉ ra đúng căn cứ điều luật + án lệ áp dụng, và phát hiện điểm vênh "có án lệ mà không áp dụng/không giải thích" với độ chính xác đạt ngưỡng. **Luôn ở chế độ second-opinion, HITL.**

---

## Phase 4 — Reasoner đa vai ("tòa án trong máy")

**Mục tiêu:** Luật sư ⇄ Kiểm sát ⇄ Thẩm phán ⇄ Bộ ngành tranh biện; kết luận là thứ sống sót qua tranh biện.

**Việc chính:**
- Hiện thực lại pattern Researcher→Auditor→Adjudicator (từ LegalGraphRAG, viết sạch).
- **Auditor hard-gate** kiểm trích dẫn + thẩm quyền + ngày hiệu lực trước mọi phát ngôn.
- Cặp đầu tiên: **Luật sư ⇄ Kiểm sát** (tấn công–phòng thủ, giá trị thấy ngay) → thêm Thẩm phán/Bộ ngành làm tầng kiểm định.

**GATE ra:** trên tập case, output đa vai **tốt hơn đo được** so với một-lượt (bắt thêm rủi ro/bỏ sót), và không tăng tỉ lệ trích dẫn sai (nhờ Auditor). Cảnh báo học thuật: tránh "over-deliberation drift" và shortcut-learning.

---

## Phase 5 — Diện rộng + Portability ("nuốt trọn thị trường")

**Mục tiêu:** phủ hết tính năng thị trường + chứng minh portable.

**Việc chính:**
- Mở rộng workflow: due diligence, legal research, litigation analysis, Compliance Diff xuyên biên giới.
- Nạp phần còn lại của taxonomy: VB địa phương đầy đủ, công văn, điều ước/FTA, dữ liệu tham chiếu.
- **Đóng gói `JurisdictionPack`** khai báo → nạp **nước thứ 2 (ASEAN)** làm phép thử portability: thêm nước = cấu hình, không viết lại lõi.

**GATE ra:** nước thứ 2 lên được bằng cấu hình (không sửa lõi engine) và đạt baseline chất lượng; Compliance Diff chạy giữa 2 jurisdiction.

---

## Phụ thuộc & rủi ro xuyên suốt

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Nguồn dữ liệu & quyền (congbobanan không có API/terms công khai) | Chặn Phase 0/3 | Theo đuổi **thỏa thuận chia sẻ dữ liệu chính thức** sớm; không scrape |
| OCR tiếng Việt trên PDF scan (nếu 4TB nhiều scan) | Chi phí/độ trễ Phase 0 | Audit tỉ lệ scan trước; chọn OCR mạnh tiếng Việt; HITL cho phần khó |
| License lẫn aggregator trong data thô | Mìn pháp lý thương mại | Truy xuất nguồn gốc; tách phần aggregator ra khỏi corpus thương mại |
| LJP shortcut-learning (đoán theo đặc trưng bề mặt) | Judgment Analysis mất tin cậy | Bắt buộc neo điều luật + án lệ thật; không train trên "cần phán quyết làm đầu vào" |
| Tuân thủ VN đổi liên tục | Kiến trúc lệch luật | Hiệu lực-aware áp cho *chính luật quản lý mình*; đối chiếu văn bản gốc |
| Định vị "nói bản án sai" | Rủi ro pháp lý/đạo đức | Second-opinion + HITL + nhãn AI; không bao giờ "xử thay" |

---

## Verify-first checklist (làm TRƯỚC khi code chạm dữ liệu thật)

- [ ] **Điều khoản sử dụng vbpl.vn / Công báo** (NĐ 52/2015) — xác nhận quyền ingest.
- [ ] **Thỏa thuận TANDTC** cho án lệ (anle.toaan.gov.vn) + bản án (congbobanan) — không có API công khai.
- [ ] **Số lượng án lệ hiện hành** — đọc trực tiếp anle.toaan.gov.vn (notes vênh 82 vs 90, chưa xác nhận tới 11/2026).
- [ ] **Văn bản gốc 3 luật/nghị định 2025–2026**: NĐ 356/2025, Luật AI 134/2025, Luật 71/2025 — đối chiếu nghĩa vụ cấp điều.
- [ ] **License base-checkpoint** (Qwen trong ViLegalLM) nếu dùng model VN có sẵn.
- [ ] **Truy xuất nguồn gốc 4TB** — tách phần nào từ aggregator (nếu có).
- [ ] **★ Thang bậc `authority_rank`** — pull official Điều 4 bản **64/2025 + 87/2025** + toàn văn **Đ.55** (`legal-rule-base.md §6`).
- [ ] **License model local** — bge-m3/AITeamVN (Apache/MIT ✅), Qwen2.5 (Apache per-checkpoint), Vintern (MIT) — verify per card; **CMC/jina-v3/voyage = loại** (NC/API).
- [ ] **Model stack chốt theo benchmark** (VLegal-Bench + gold set), KHÔNG theo tên — `stack-db-and-models.md §5` (orchestration 3 tầng).

---

## Tóm tắt một dòng

**Dựng móng hiệu lực (Phase 0) → chứng minh moat bằng benchmark (Phase 1) → đủ chuẩn khách FDI (Phase 2) → mở năng lực không ai có: thẩm định bản án (Phase 3) → tòa án trong máy (Phase 4) → nuốt diện rộng + nước thứ 2 (Phase 5).** Mỗi bước là cửa có số, không phải lời hứa.
