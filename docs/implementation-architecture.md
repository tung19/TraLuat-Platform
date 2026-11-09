# TraLuat — Kiến trúc triển khai (build spec cho đội)

> Mục tiêu: để mỗi member nhận **một mảng** và code tiếp được ngay, dựa trên pattern đã bóc từ repo tham khảo trong `refs/`.
> Đây là bản tổng hợp của: `architecture.md` (tổng quan), `technical-design.md` (Data/AI/Layer/Feature), `layered-architecture.md` (15 layer), `repo-deep-read.md` (bóc code + steal-list), `roadmap.md` (phase).
> Nguyên tắc vàng xuyên suốt (đã xác nhận bằng cách đọc code): **mọi repo tham khảo đều mạnh ở phần cơ học và đều TRỐNG đúng một chỗ — hiệu lực-thời-gian. Đó là moat ta tự xây, cắm vào mọi mảng.**

---

## 0. Bản đồ mảng & phụ thuộc (ai code gì, theo thứ tự nào)

| # | Mảng (owner) | Layer | Phụ thuộc | Repo tham khảo chính |
|---|---|---|---|---|
| **W1** | **Data pipeline** | L1–L2 | — | Bluebell (parse/eId), eyecite (trích dẫn) |
| **W2** | **Đồ thị tri thức (Knowledge Graph)** ★ | L3–L4 | W1 | Indigo (bitemporal/FRBR), LeSICiN (hetero graph), LegalGraphRAG (4-layer KG) |
| **W3** | **AI/ML (retrieval + grounding)** | L5–L7 | W2 | PAKTON (retriever/gateway), L-MARS (verifier), legalbenchrag (eval) |
| **W4** | **Reasoning engine** | L8 | W3 | LegalGraphRAG (Auditor), PAKTON (orchestration) |
| **W5** | **Backend / Engineering** | P1–P4, L7, L11 | song song | PAKTON (backend skeleton) |
| **W6** | **Knowledge Platform & Ops** | L9, L12–L14 | W3,W5 | Claude for Legal (workflow), legalbenchrag (eval gate) |

**Thứ tự khởi công:** W5 (skeleton) + W1 (data) + W2 (KG) **song song trước** → W3 → W4 → W6.
**Bất biến toàn hệ:** (1) mọi đơn vị có `valid_from/valid_to` + `tx_from/tx_to`; (2) mọi output đi qua verify 3 cổng hoặc abstain; (3) dữ liệu khách cô lập theo tenant; (4) mọi output có trích dẫn + ngày + confidence + nhãn AI + HITL.

---

## W1 — DATA PIPELINE (L1 Acquisition + L2 Ingestion)

**Scope:** biến `meta.json` + PDF (mỗi điều luật / bộ ngành) → schema canonical, kèm trích quan hệ sửa đổi/bãi bỏ.

**Đầu vào thực tế (cần member xác nhận):** dữ liệu đã có **`meta.json` + PDF theo từng điều luật** → *tin tốt*: phần lớn gánh nặng **cấu trúc hoá đã xong ở nguồn**; pipeline chủ yếu là **map meta.json → schema** + OCR phần PDF scan + trích quan hệ. → **Việc đầu tiên của W1: dán schema `meta.json` thật để chốt mapping.**

**Pipeline (8 stage, điều phối bằng Temporal — xem `technical-design.md §A.6`):**
1. Ingest & dedup (hash, provenance) · 2. OCR/parse PDF (đo tỉ lệ scan trước!) · 3. Cấu trúc hoá (nếu meta.json đã có cấp điều/khoản thì chỉ chuẩn hoá) · 4. Trích metadata (số hiệu, ngày ban hành, **ngày hiệu lực**, cơ quan) · **5. Trích quan hệ sửa đổi/bãi bỏ ★** · **6. Versioning bitemporal ★** · 7. Căn chỉnh song ngữ · 8. Indexing.

**Reference (đọc file trong `refs/`):**
- **Bluebell** `grammar.pest`, `eid.rs`, `xml.rs` → sinh **eId ổn định** (`nd99__dieu_3__khoan_2`) cho amendment trỏ vào. Pattern cấu trúc hoá.
- **eyecite** `find.py`/`resolve.py`/`annotate.py` → pipeline trích dẫn `clean→find→resolve→annotate`; **tách data↔engine**: dựng package **`vn-legal-db`** (grammar VN: `Điều X Khoản Y của {Luật/NĐ/TT} số…/năm…`, `án lệ số…/AL`) + phát hiện **"được sửa đổi/bãi bỏ bởi"** → feed thẳng `norm_relation` (W2). Dùng `SpanUpdater` của eyecite để giữ offset gốc.

**Data contract ra:** mỗi stage phát JSON có version schema, idempotent, có provenance. Output cuối: records của `document / unit / unit_version / norm_relation` (xem W2).

**Acceptance:** nạp 1 nghị định + 1 văn bản sửa đổi nó → sinh đúng `norm_relation(amends, effective_date)` và đủ metadata ngày hiệu lực; tỉ lệ scan của corpus được đo và báo cáo.

---

## W2 — ĐỒ THỊ TRI THỨC / KNOWLEDGE GRAPH ★ (L3 + L4) — moat lõi

**Scope:** nguồn-sự-thật bitemporal + đồ thị tri thức pháp lý: quy phạm, quan hệ, án lệ, bản án, song ngữ — và neo "văn bản tại ngày T".

### W2.1 Mô hình dữ liệu (canonical, bitemporal)
Thực thể: `jurisdiction / authority(+rank_level) / document / unit(cây) / unit_version(valid_from,valid_to,tx_from,tx_to) / norm_relation / precedent / judgment / concept+term / clause_type / required_clause_rule`. (DDL phác thảo: `src/traluat/models.py` — *bản minh hoạ, không phải code sản phẩm*; chi tiết field: `technical-design.md §A.2`.)

**Reference — Indigo (đọc, remodel sang SQLAlchemy, KHÔNG chạy Django):**
- `indigo_api/models/works.py` (`Work`, `expressions`, `possible_expression_dates`, `create_expression_at`)
- `amendments.py` (`Amendment`, `AmendmentInstruction`, post_save → materialize expression mới)
- `documents.py` (`get_for_frbr_uri`: `expression_date__lte=T` → **as-of-T**; `valid_until`)
- `refs/cobalt` `uri.py` (`FrbrUri.parse`) → canonical ID.
**Indigo THIẾU (W2 tự thêm):** (a) norm-graph tổng quát có kiểu; (b) giải xung đột (lex superior/posterior/specialis qua `authority.rank_level`); (c) **transaction-time** (Indigo chỉ valid-time); (d) hợp nhất tự động.

### W2.2 Ba đồ thị con (đây là "đồ thị tri thức")
1. **Đồ thị quy phạm (norm graph):** node = `unit`; cạnh `norm_relation` (cites/amends/repeals/replaces/guides/conflicts/hierarchy). Dùng cho multi-hop (dẫn chiếu, văn bản hướng dẫn) + giải xung đột.
2. **Đồ thị liên kết bản án↔điều luật↔án lệ:** từ **LeSICiN** (`refs/LeSICiN/model/helper.py::generate_graph`) — đồ thị dị cấu (Bộ luật→Chương→Mục→Điều ⟂ Bản án→Điều). **Inductive stance**: bản án mới chỉ mã hoá text rồi *match* vào node điều luật, không dựng lại graph. Hiện đại hoá: bge-m3 thay Sent2Vec; retrieval (bi-encoder+rerank) thay BCE-toàn-label.
3. **KG suy luận 4 tầng (tùy chọn, cho W4):** từ **LegalGraphRAG** (`refs/LegalGraphRAG/core/graph_construct/`) — fact/feature/ontology/rule; charge-anchored retrieval (đoán vấn đề pháp lý → đi tới điều liên quan).

**Graph store:** khởi đầu **Apache AGE (openCypher trên Postgres)** để một hệ; tách **Neo4j** nếu multi-hop nặng. Đồ thị là **phái sinh** của `unit`/`norm_relation` (rebuild được), không phải nguồn-sự-thật thứ hai.

### W2.3 Ontology / lược đồ khái niệm
Chuẩn: Akoma Ntoso (cấu trúc) + LegalRuleML (quy phạm deontic) + ELI (ngày). Concept node + term (vi/en) + `equivalence_type` (full/partial/none) cho song ngữ (W liên quan AI).

**Acceptance (moat #1):** cho một điều có ≥1 sửa đổi + 1 bãi bỏ → `reconstruct_as_of(unit, T)` trả đúng văn bản tại mọi mốc T (trước/trong/sau sửa đổi, sau bãi bỏ=None); `document_as_of` ghép đúng; truy vấn `known_as_of` (transaction-time) trả đúng "trước đây hệ thống tin gì".

---

## W3 — AI/ML: RETRIEVAL + GROUNDING (L5–L7)

**Scope:** truy xuất cấp điều–khoản hiệu lực-aware + verify trích dẫn + hạ tầng mô hình.

### W3.1 Retrieval (L5)
- Hybrid **BM25 + dense (bge-m3, MIT)** → RRF → rerank; **tokenizer tiếng Việt** (BM25 `.split()` của PAKTON vô dụng cho VN).
- **effectivity filter**: mọi truy vấn mang `as_of_date`, chỉ giữ `unit_version` còn hiệu lực tại T (tra W2). ← *khác biệt cốt lõi, không repo nào có.*
- Multi-hop qua norm graph (W2).
**Reference:** PAKTON `retrievers/base.py` (interface cắm được) — **thêm** metadata filter (effectivity + tenant) mà PAKTON thiếu. Idiom "retrieve wide, rerank narrow" từ legalbenchrag.

### W3.2 Grounding & Verify (L6)
- **Citation Verifier 3 cổng:** (1) có thật (tra KB) · (2) còn hiệu lực tại `as_of_date` (bitemporal W2) · (3) hỗ trợ khẳng định (NLI).
- **Verifier cấp-khẳng-định 6 lớp** + **Faith-Search repair** + **abstain** + cross-provider.
**Reference:** **L-MARS** `lmars/verify_agent.py` (6 lớp) + `faith_search/{workflow,router,aggregator}.py`. "Nguồn trích" đổi URL→**id+phiên bản điều luật VN** (dễ hơn). Lớp `temporally_invalid` + repair theo ngày = **đúng trục hiệu lực**.

### W3.3 Model/Inference runtime (L7)
- **LLM Gateway tập trung** (PAKTON có mẫu per-node `models/llm.py` nhưng *lặp* — ta gom lại): swappable (Claude Opus/Sonnet; `endpoint_url`→vLLM/self-host cho tenant nhạy cảm), **prompt-cache, log I/O cho audit, nhãn AI, guard tenant**.
- Extractor fine-tune (metadata/relation/NLI): ViLegalBERT/Qwen + rule; **không train trên dữ liệu NC/aggregator**.

### W3.4 Eval harness (feed L13)
**Reference — legalbenchrag:** mô hình **span ký tự rời-nhau** + **P/R cấp ký tự** + **chunker giữ-span** (2 assert bảo toàn) + diskcache tất định. (Phác thảo: `src/traluat/eval_harness.py`.) **Thêm:** chunk theo đơn vị cấu trúc VN; eval **lọc-hiệu-lực**; **benchmark 3 chiều** (đúng điều–khoản / đúng hiệu lực / bắt bỏ sót) qua `tags`.

**Acceptance:** truy vấn với `as_of_date` chỉ trả điều còn hiệu lực; mọi câu trả lời kèm trích dẫn verify được hoặc abstain; harness in bảng P/R 3 chiều so với 1 baseline LLM.

---

## W4 — REASONING ENGINE (L8)

**Scope:** vòng lặp grounding + Auditor hard-gate + (sau) reasoner đa vai.

- **Vòng lặp grounding** (pseudocode: `technical-design.md §B.2`): parse(as_of_date) → retrieve → effectivity filter → generate (LLM chỉ dùng cands, trích dẫn inline) → verify 3 cổng → confidence/abstain.
- **Auditor HARD-GATE** — **Reference: LegalGraphRAG** `core/agents/auditor.py` (`audit`, `prune_unsupported_cases`) + `core/judge/judge_law.py::verify_article` (**kiểm từng yếu tố cấu thành**, không yes/no tổng thể). **Thêm cổng NGÀY HIỆU LỰC** (LegalGraphRAG thiếu). Loại án lệ không còn điểm tựa (`prune`).
- **Orchestration:** PAKTON `Interrogator/graph/builder.py` (loop) + sub-agent-as-tool. Siết stop-condition (PAKTON mong manh).
- **Reasoner đa vai (Phase 4):** Luật sư⇄Kiểm sát⇄Thẩm phán⇄Bộ ngành; Auditor chạy trên *mọi* phát ngôn trước output. Viết lại sạch từ pattern, không copy.

**Acceptance:** với một tình huống, Auditor loại đúng điều không áp dụng / đã hết hiệu lực trước khi Adjudicator phán; output đa vai tốt hơn một-lượt mà không tăng trích dẫn sai.

---

## W5 — BACKEND / ENGINEERING (P1–P4, L7 serving, L11)

**Scope:** xương sống chạy được + API + hạ tầng + multi-tenancy.

**Reference — PAKTON `PAKTON Framework/` (skeleton dùng ngay):** FastAPI (`API/api.py`, Celery-async + **SSE streaming từng step/tool**), Celery (`tasks.py`), SQLAlchemy + Alembic, Docker/compose/nginx. Ba kho tách: SQL(metadata)/Postgres-checkpointer(history)/vector(chunk).
**Phải tự thêm (PAKTON thiếu):**
- **Multi-tenancy xuyên suốt** (PAKTON một index chung): `tenant_id` mọi nơi, RLS/schema-per-tenant, mã hoá key-per-tenant. **KB luật chia sẻ read-only; dữ liệu khách cô lập cứng, không train.**
- **Data residency trong VN** + zero-retention tuỳ chọn (NĐ 356/2025).
- **Observability** (OTel + metrics + cost LLM) + **nhãn AI** ở API/gateway (Luật 71/2025).

**Acceptance:** upload tài liệu → task async → trả kết quả streaming; hai tenant không thấy dữ liệu nhau; mọi output có nhãn AI; trace đầy đủ.

---

## W6 — KNOWLEDGE PLATFORM & OPS (L9, L12–L14)

**Scope:** đóng gói tính năng + trải nghiệm + cổng chất lượng + vận hành tri thức.

- **L9 Workflow:** Review (+omission 2 lượt), Draft (song ngữ), Assistant, **Judgment Analysis** (bản án→đúng/sai+căn cứ+án lệ), Compliance Diff. (Chi tiết build: `technical-design.md §D`.) **Reference:** Claude for Legal (fork khung playbook/checklist markdown, thay ruột bằng grounding của ta).
- **L10 Jurisdiction Config:** `JurisdictionPack` khai báo (tháp thứ bậc, quy tắc thẩm quyền, ngữ pháp trích quan hệ, nguồn, term base) → portability. Thiết kế từ đầu để VN không bị hardcode.
- **L12 Experience:** UI rà soát (highlight rủi ro/bỏ sót theo màu), **đối chiếu song ngữ**, **điều hướng trích dẫn** (click điều → xem văn bản tại ngày T), màn hình HITL.
- **L13 Trust/eval-gate:** benchmark 3 chiều làm **cổng CI** (port từ W3.4) — repo legalbenchrag chỉ xuất CSV, ta nối threshold pass/fail.
- **L14 Human Knowledge-Ops:** công cụ gán gold set, **tuyển/cập nhật án lệ**, viết `required_clause_rule`/playbook, duyệt HITL → **flywheel: output duyệt → gold set → fine-tune**. (Ý "experience-memory" học từ AgentCourt.)

### W6.1 — Fork Claude for Legal (tầng workflow, chi tiết)
`refs/claude-for-legal` (Apache-2.0) = **marketplace plugin, 100% prompt/config, KHÔNG có engine** — mọi câu trả lời pháp lý là *kiến thức model, gắn thẻ `[verify]`*. Nội dung: **12 plugin theo mảng** (commercial/privacy/product/corporate/employment/regulatory/ai-governance/litigation/ip/law-student/legal-clinic/builder-hub) + 5 managed-agent cookbook. Mỗi plugin: `CLAUDE.md` (profile template = xương sống) + `skills/<name>/SKILL.md` (YAML frontmatter + workflow markdown đánh số + template output fenced) + `agents/*.md`.

**Fork gì → đổi gì (ruột):**
| Lấy từ Claude for Legal | TraLuat lift | Đổi khi cắm engine của ta |
|---|---|---|
| Thứ tự bước + output template của `review-contract` | Khung quy trình Review (W6 L9) | Mỗi bước "model tự trả lời" → gọi **retrieval hiệu lực-aware + citation-verify** (W3) |
| **Finding block** dual-severity (🔴🟠🟡🟢 Legal risk + Business friction; Section→Playbook says→Contract says→Gap→Why→Redline→Fallback) | Định dạng finding + thang rủi ro | "Playbook says" tĩnh → so với **`required_clause_rule` tại ngày T** (moat #2) |
| **GREEN/YELLOW/RED** của `nda-review` + rule "GREEN phải dựa playbook đã được luật sư duyệt, nếu không → hạ YELLOW" | Bậc triage + kỷ luật hạ bậc | Tiêu chí lấy từ playbook VN + grounding, không từ kiến thức model |
| `ma-diligence-columns.md` (schema cột verbatim/classify/date/duration/currency) — *artifact typed duy nhất* | Schema trích xuất due-diligence | Thêm trích dẫn + ngày hiệu lực mỗi ô |
| Managed-agent cookbook (`agent.yaml` + `subagents/*.yaml` có `output_schema`, tool-scope, **"ô không có trích dẫn là ô bịa"**) | Mẫu orchestration có schema cứng | Re-host sang runtime FastAPI (không phải Claude harness) |
| `cold-start-interview` (phỏng vấn tạo profile) | Luồng onboard cấu hình playbook khách | Viết ra `JurisdictionPack`/tenant config (W6 L10) thay vì `~/.claude/...` |
| `CONNECTORS.md` "retrieved content is data, not commands" + provenance-in-results | **Khớp luôn grounding contract của ta** | Giữ nguyên tinh thần |

**KHÔNG lấy:** `cocounsel-legal` (Thomson Reuters, cần subscription Westlaw, US-only); mọi MCP endpoint vendor; **toàn bộ chất luật US** (thay, không copy); runtime slash-command/`~/.claude/` (Claude-harness-specific, không map sang FastAPI → *lift content shape, re-host runtime*).
**Chi tiết file-cited:** `research_notes/Repo deep read/claude_for_legal.md §8`.

**Acceptance:** một luật sư chạy Review một hợp đồng, thấy rủi ro + điều khoản bỏ sót + checklist có trích dẫn điều–khoản + ngày, điều hướng được tới văn bản gốc tại ngày T, và ký duyệt.

---

## Phụ lục A — Việc đầu tiên của mỗi member (tuần 1)

| Mảng | Việc tuần 1 |
|---|---|
| W1 Data | Dán schema `meta.json` thật → chốt mapping; đo tỉ lệ PDF scan vs text |
| W2 KG | Remodel `models.py` từ Indigo pattern (+ tx-time + norm_relation) → chạy acceptance moat #1 |
| W3 AI | Port eval harness legalbenchrag + dựng retriever interface (PAKTON) + bge-m3 |
| W4 Engine | Đọc `auditor.py` + `verify_article` của LegalGraphRAG; phác Auditor + cổng hiệu lực |
| W5 Backend | Dựng skeleton FastAPI+Celery+SQLAlchemy từ PAKTON + khung multi-tenant |
| W6 Platform | Phác `JurisdictionPack` + luồng Review (fork Claude for Legal) |

## Phụ lục B — Steal-list (file cụ thể trong `refs/`)
Xem `docs/repo-deep-read.md §6` và `§10` — bảng trỏ thẳng file cho từng thứ cần dựng.

## Phụ lục C — Đang chờ (sẽ gộp vào khi xong)
- **Kiểm chứng pháp lý (đang chạy nền):** NĐ 356/2025, Luật AI 134/2025, Luật 71/2025, số lượng án lệ, terms vbpl.vn → cập nhật ràng buộc W5/W6.
- **Schema `meta.json` của 4TB** → chốt W1.
