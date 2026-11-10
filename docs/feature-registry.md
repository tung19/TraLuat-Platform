# TraLuat — Sổ cái tính năng (Feature Registry) — CHỐNG BỎ SÓT

> **Nguồn chân lý DUY NHẤT về "platform có những tính năng gì".** Mọi tính năng rải trong W1–W7 được gom về đây, mỗi cái 1 **ID (FR-xx)** + spec sở hữu + trạng thái + cổng.
>
> 🔒 **LUẬT CHỐNG BỎ SÓT (bắt buộc khi implement):**
> 1. Mỗi `FR-xx` phải map tới ít nhất 1 **build task** trong spec sở hữu.
> 2. Khi đóng một module, mỗi FR của nó phải ở trạng thái **Done** (qua acceptance test của spec) **hoặc** **Deferred** (ghi rõ lý do + ngày xem lại). **KHÔNG được để trống / biến mất.**
> 3. PR không được merge nếu đụng một FR mà không cập nhật cột *Trạng thái* ở đây.
> 4. Review hằng tuần: quét cả bảng, không FR nào "rơi" khỏi radar.
>
> Trạng thái: `SPEC` = đã đặc tả, chưa code · `WIP` = một phần/khung · `DONE` (qua acceptance test) · `DEFER` (hoãn, có lý do).
>
> **🔄 Đối chiếu code 2026-11-10 (cập nhật Nhóm-1: +FR-14, +35.2/35.6/35.9, +CN-05)** (230 test xanh): cột *Trạng thái* dưới đây đã rà theo codebase thật (không còn để trống "SPEC" mặc định). Nguồn chi tiết: `status-audit-current.md`.
> Nhóm: **MOAT** (huỷ diệt) · **PARITY** (ngang thị trường) · **BACKLOG** (nhóm 2, sau lõi) · **CONSTRAINT** (ràng buộc cứng, không phải tính năng nhưng cấm bỏ).

---

## A. MOAT — tính năng huỷ diệt (không được thiếu bất kỳ cái nào ở v1 lõi, trừ nơi ghi BACKLOG)

| ID | Tính năng | Spec sở hữu | Nhóm | Trạng thái | Cổng / ghi chú |
|---|---|---|:--:|:--:|---|
| **FR-01** | **Văn bản tại ngày T** (bitemporal, dựng lại luật tại thời điểm) | W2 §3 + W1 Stage 6 | MOAT | ✅ **DONE** | `w2/{bitemporal,repo}` reconstruct_as_of + effect_status + materialize-gate + GiST. |
| **FR-02** | **Omission** — điều bắt buộc còn THIẾU vs luật@T | W6 §1.1 (ReviewService 2-pass) | MOAT | ✅ **DONE** | `ReviewService` + RequiredClauseRule + `/review`. |
| **FR-03** | **Judgment Analysis** — bản án đúng chưa + điều luật + án lệ | W6 §1.4 + W2 §5.2 | MOAT | ✅ **DONE** | `JudgmentAnalysisService` + `/judgment` + audit CN-03. |
| **FR-04** | **Song ngữ VN–EN + neo trích dẫn** tới điều–khoản + ngày hiệu lực | W1 Stage 7 + W3 | MOAT | 🟡 **WIP** | **EN DONE** (retrieval cross-lingual bge-m3 + termbank VN-EN-ZH). 🔵 **ZH DEFER** (chưa có cầu/corpus). Dịch pháp lý HITL chưa. |
| **FR-05** | **Citation Verifier** 3 cổng (exists/in-force/supports) + 6 lớp + **abstain** | W3 §2 | MOAT | ✅ **DONE** | `w3/grounding` gate1/2/3b + NLI + R1 abstain. |
| **FR-06** | **Đa-vai suy luận** (bounded, như cơ chế verify — không role-play) | W4 + W7 §2 | MOAT | ✅ **DONE** | `w4/multi_role` + Auditor hard-gate. |
| **FR-07** | **LAW-TRUE** — mù địa vị bị cáo; thiên vị tách `integrity_note` | W4 | MOAT | ✅ **DONE** | `w4` LAW-TRUE + integrity_note. |
| **FR-08** | **ComplianceAdvisory** — hoạt động DN → vi phạm? + cách tránh + trích dẫn | W7 §1 | MOAT/BACKLOG | ❌ **SPEC** | nhóm-2, CHƯA code. |
| **FR-09** | **ComplianceDiff khi luật đổi** + **alert-trigger** (VB/dự thảo mới → tự rà lại hợp đồng khách) | W6 §1.5 + change-watch trigger | MOAT | ✅ **DONE** | `ComplianceDiffService` + `w5/alerts` (materialize→fan-out) + `/alerts`. |
| **FR-41** | **Cross-document conflict & consistency check** (Luật nói A, Thông tư nói B → theo thứ bậc cái nào thắng; phát hiện vượt-uỷ-quyền) | W2 §4 `resolve_conflict` + `legal-rule-base` + W6 service | MOAT | ✅ **DONE** | RESOLUTION (lex superior/posterior/abstain) + DETECTION số + **ngữ-nghĩa deontic** (`DeonticConflictDetector` cho-phép↔cấm, tất định). Mâu thuẫn tinh-vi hơn vẫn cắm NLI cùng port. |

---

## B. PARITY — nền để vào cuộc (cấm thiếu)

| ID | Tính năng | Spec sở hữu | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-10** | Hybrid retrieval (BM25+bge-m3+RRF+rerank) + lọc hiệu lực + tenant | W3 §1 | ✅ **DONE** | `w3/retrieval` hybrid + push-down SQL + multihop. |
| **FR-11** | Hỏi–đáp pháp lý grounded | W6 §1.3 (AssistantService) | ✅ **DONE** | `service.lookup` + `answer_question` + `/lookup`. |
| **FR-12** | Phân rã cấu trúc Điều/Khoản/Điểm + eId | W1 Stage 3 | ✅ **DONE** | `w1/structure` + eId. |
| **FR-13** | Đồ thị tri thức (dẫn chiếu/hướng dẫn/thứ bậc) | W2 §5.1 | ✅ **DONE** | `w2/repo` multihop CTE + Neo4j projection + GDS. |
| **FR-14** | Tóm tắt VB / vụ việc | W4 / W6 | ✅ **DONE** | `service.summarize` (node=summary) + `/summarize` grounded cite-or-abstain. |
| **FR-15** | Soạn hợp đồng song ngữ | W6 §1.2 (DraftService) | 🟡 **WIP** | Pipeline draft generic có (`/draft`), HĐ **song ngữ** riêng chưa. |
| **FR-34** | **Soạn ĐƠN TỪ pháp lý theo mẫu** (khởi kiện/khiếu nại/tố giác…) — học từ kho mẫu (RAG, không fine-tune) | W6 §1.2b (PetitionDraftService) + DTP (L10) + TES (W3) | ✅ **DONE** | `PetitionDraftService` grounded + `/draft` (client→local) + template store. |
| **FR-16** | Rà soát hợp đồng | W6 §1.1 (ReviewService) | ✅ **DONE** | `ReviewService` (chung FR-02). |
| **FR-17** | Multi-tenant (RLS, cô lập) | W5 §2 | ✅ **DONE** | FORCE RLS + role non-owner + chống IDOR. |
| **FR-18** | Giao diện song ngữ | W6 §3 (L12) | 🟡 **WIP** | UI hiện VI-only; EN chưa. |

---

## C. DATA / PIPELINE (W1–W2 — cấm thiếu, nền của mọi thứ)

| ID | Tính năng | Spec | Trạng thái |
|---|---|---|:--:|
| **FR-19** | Ingest + dedup | W1 Stage 1 | ✅ **DONE** |
| **FR-20** | OCR / parse PDF (+ đo tỉ lệ scan) | W1 Stage 2 + §4 | 🟡 **WIP** — OCR dòng (VietOCR) + full-page port có; **đo tỉ lệ scan** chưa |
| **FR-21** | Trích metadata (số hiệu, ngày ban hành, **ngày hiệu lực**, cơ quan) | W1 Stage 4 | ✅ **DONE** |
| **FR-22** | Trích quan hệ sửa đổi/bãi bỏ | W1 Stage 5 | ✅ **DONE** |
| **FR-23** | Engine trích dẫn/sửa đổi VN (`vn-legal-db`, pattern eyecite) | W1 §5 | ✅ **DONE** |
| **FR-24** | Giải xung đột quy phạm (deterministic) | W2 §4 | ✅ **DONE** |
| **FR-25** | Chunking/indexing handoff | W1 Stage 8 + W3 chunking | ✅ **DONE** |

---

## D. PLATFORM / GOVERNANCE (cấm thiếu)

| ID | Tính năng | Spec | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-26** | JurisdictionPack (portability, VN-first) | W6 §2 (L10) | ✅ **DONE** | `w6/jurisdiction` rank/vai theo vùng. |
| **FR-27** | Eval harness + eval-gate 3 chiều (L13) | W3 §4 + W6 §4 | ✅ **DONE** (khung) | loader + `EvalReport.gate` + smoke; 🔵 gold data thật cần chuyên gia. |
| **FR-28** | Observability (L11) | W5 §4 | ✅ **DONE** | `/metrics` Prometheus + OTel tracing (`w5/tracing`). |
| **FR-29** | Human Knowledge-Ops flywheel (L14) | W6 §5 | ✅ **DONE** | `knowledge_ops` queue→approve→materialize + gold export. |
| **FR-30** | LLM Gateway phân tầng (RULE→ML-local→LLM) + egress guard | W3 §3 + W5 §2.5/§3.1b | ✅ **DONE** | `w3/gateway` router + `EgressPolicy` residency. |

---

## E. BACKLOG (nhóm 2 — làm SAU lõi, theo thứ tự; vẫn phải qua bộ lọc 3 câu)

| ID | Tính năng | Spec | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-31** | Vai mở rộng (điều tra/kiểm sát/kiểm toán) + **workbench theo vai** | W7 §2, §4 | DEFER | guardrail rủi-ro-cao mạnh hơn |
| **FR-32** | Loophole/Gap advisory (defensive) | W7 §3 | DEFER | **sau cùng** — dual-use, cần rà riêng |
| **FR-33** | Law-sim Change-Propagation (tác động khi luật đổi) | W7 §5b | DEFER | *chỉ cái này* trong "law simulation" đáng làm |

---

## G. LỚP GIỮ CHÂN / TIỆN ÍCH (bê tiện ích tốt nhất từ TVPL về + **siêu-nạp bằng moat**)
> Chiến lược: đây là **mồi + stickiness** (dùng hằng ngày), KHÔNG phải moat. Nhưng **mỗi cái đều nhúng moat** (neo điều–khoản + `as_of`) → khác hẳn bản TVPL. Xem khung 2-lớp ở `scope-and-priorities`.

| ID | Tính năng | Nguồn cảm hứng (TVPL) | Map | Trạng thái | Mình hơn ở |
|---|---|---|---|:--:|---|
| **FR-35** | **Legal utilities toolbox** — **14 mục, bảng chi tiết FR-35.x bên dưới** (35.13 là ⚡moat-item) | tiện ích TVPL | parity trên W2/W3 (+ 35.13 moat) | 🟡 **WIP** | registry `w1/calculators` chạy; **14/14 mục xong** (toàn bộ). |
| **FR-36** | **Document compare (as-of)** — so 2 phiên bản / **2 ngày BẤT KỲ** của cùng VB, redline cấp điều–khoản | "so sánh văn bản" | **powered by FR-01** | ✅ **DONE** | `ComplianceDiffService.diff` + `/compare` + form `/tools`. |
| **FR-37** | **Effectivity-aware relationship graph** — viz "gia phả" VB có **trục thời gian** (query in-force@T) | "lược đồ" | **powered by FR-13** | ✅ **DONE** | `/graph` Cytoscape time-travel + GDS overlay. |
| **FR-38** | **Forms / biểu mẫu library** — kho mẫu tải được | "biểu mẫu" | nối FR-34 | 🟡 **WIP** | template store có; form có cấu trúc + validation chưa. |
| **FR-39** | **Directory VPLS + bản đồ "gần bạn"** | DanLuat (không geo) | **PostGIS** + reference-data-plane | ✅ **DONE** | `w1/directory` PostGIS `nearby` + `/directory` Leaflet + seed 13 cơ quan. 🔵 data-freshness thật cần đội data. |
| **FR-40** | **Danh bạ liên hệ công khai** (cán bộ khu vực…) | — | Postgres + reference-data-plane | ✅ **DONE** | cùng bảng `directory` (kind co_quan/vien_ksnd/thi_hanh_an). |

### FR-35.x — chi tiết 14 tiện ích (chống sót từng cái)
> ✅ = TVPL confirmed có · ⚠️ = cần verify / đối thủ có. Mỗi mục đóng xong phải tick `DONE`/`DEFER`.
> 🔴 **Audit (đọc trước):** **chỉ ⚡35.13 là MOAT** (as-of thật sự giá trị). **35.1–35.12 = parity** — neo-luật chỉ là *nhãn provenance*, không phải khác biệt (user chỉ cần "hiện tại"). **Làm 3–4 cái dùng nhiều trước** (35.1 PIT, 35.6 gross-net, 35.7 lương vùng), KHÔNG bung 14. **Dated-logic (công thức đổi theo ngày) = tự BUILD** — OpenFisca chỉ date-hoá *tham số*, không date-hoá *công thức*. **Abstain khi luật mơ hồ** (calc sai hại hơn hardcode thật thà).

| ID | Tiện ích | TVPL | Trạng thái | Mình hơn (neo moat) |
|---|---|:--:|:--:|---|
| **35.1** | Tính thuế TNCN (auto BHXH 8%/BHYT 1.5%) | ✅ | ✅ **DONE** | `calculator("thue_tncn")` neo bậc thuế + as_of |
| **35.2** | Tính thuế GTGT | ⚠️ | ✅ **DONE** | `calculator("thue_gtgt")` neo thuế-suất@T |
| **35.3** | Tra cứu mã số thuế + tình trạng hoạt động | ✅ | ✅ **DONE** | `calculator("tra_mst")` reference |
| **35.4** | Biểu thuế XNK (WTO/ASEAN) + tra mã HS | ✅ | ✅ **DONE** | `calculator("bieu_thue_xnk")` HS+hiệp định@T |
| **35.5** | Lịch nộp thuế/báo cáo | ⚠️ | ✅ **DONE** | `calculator("lich_nop_thue")` reference@T |
| **35.6** | Gross ↔ Net lương | ✅ | ✅ **DONE** | `calculator("gross_net")` TNCN luỹ tiến + BH + giảm-trừ, hiệu-lực@T |
| **35.7** | Lương tối thiểu vùng (tỉnh/huyện) | ✅ | ✅ **DONE** | `calculator("luong_toi_thieu")` |
| **35.8** | BHXH một lần / trợ cấp thất nghiệp | ⚠️ | ✅ **DONE** | `calculator("bhxh_mot_lan")` công thức hệ-số trước/sau 2014@T |
| **35.9** | Lương làm thêm giờ / ngày lễ | ⚠️ | ✅ **DONE** | `calculator("lam_them_gio")` hệ-số theo loại-ngày@T (neo BLLĐ) |
| **35.10** | Tra cứu mã ngành nghề KD | ✅ | ✅ **DONE** | `calculator("tra_nganh")` VSIC reference |
| **35.11** | Tra cứu xử phạt giao thông | ✅ | ✅ **DONE** | `calculator("muc_phat")` neo NĐ@T |
| **35.12** | Từ điển pháp lý / thuật ngữ | ⚠️ | ✅ **DONE** | `w1/termbank` VN-EN-ZH neo điều |
| **⚡35.13** | **Tính thời hiệu / thời hạn tố tụng** (khởi kiện, kháng cáo, khiếu nại…) | ⚠️ (TVPL chỉ đếm ngày thô) | ✅ **DONE** | `w1/deadlines` hiệu-lực-aware + neo điều + lùi ngày nghỉ + `/deadline`. **MOAT-ITEM.** |
| **35.14** | Đếm ngày / lịch âm-dương | ⚠️ | ✅ **DONE** | `w1/calendar_vn` + `w1/lunar` (thuật toán Hồ Ngọc Đức) → Tết/Giỗ Tổ TÍNH tự động, deadline tự lùi. |

> **FR-35 tổng: 14/14 DONE** (+ `le_phi` bonus). Mục lookup cần DATA thật từ đội data; công thức (TNCN/BHXH/làm-thêm) + lịch/âm-dương đã tính đúng.

---

## F. CONSTRAINT — ràng buộc cứng (không phải tính năng, nhưng BỎ = vi phạm pháp lý)

| ID | Ràng buộc | Spec | Trạng thái |
|---|---|---|:--:|
| **CN-01** | Data residency VN + egress fail-closed (NĐ 356/2025) | W5 §3.1 / §3.1b | ✅ **DONE** |
| **CN-02** | Nhãn AI (Luật 71/2025, NĐ 142/2026) | W5 §3.4 | ✅ **DONE** |
| **CN-03** | Judgment/điều-tra/kiểm-sát = rủi-ro-cao: HITL + logging (QĐ 33/2026) | compliance-vn | ✅ **DONE** (judgment/draft audit + hitl_required) |
| **CN-04** | Án lệ **ràng buộc** (NQ 04/2019) | W2 §5.2 | ✅ **DONE** — `binding_precedents` (effective@T) + judgment cờ án-lệ-ràng-buộc bỏ sót |
| **CN-05** | Nguồn được phép + bản án ẩn danh (NQ 03/2017) | W1 + data-handoff | ✅ **DONE** — license-gate + `w1/anonymize` áp khi ingest bản án |
| **CN-06** | Mã hoá key-per-tenant + zero-retention (tuỳ tenant) | W5 §2.4 / §3.2 | ✅ **DONE** |

---

## Tổng kết đếm (để đối chiếu nhanh — nếu con số lệch là có cái bị thêm/bớt ngoài quy trình)
- **MOAT:** 10 (FR-01…09 **+ FR-41** cross-doc conflict) — *FR-08 nhóm-2*
- **PARITY:** 9 (FR-10…18)
- **DATA/PIPELINE:** 7 (FR-19…25)
- **PLATFORM/GOV:** 5 (FR-26…30)
- **BACKLOG:** 4 (FR-31…33 **+ FR-34** đơn từ — nhóm-2, liệt kê ở bảng PARITY dưới FR-15 nhưng trạng thái BACKLOG)
- **GIỮ CHÂN/TIỆN ÍCH:** 6 (FR-35…40 — bê từ TVPL + siêu-nạp moat; FR-39 map/geo, FR-40 danh bạ); **FR-35 nở ra 14 tiện ích con FR-35.1…35.14** (35.13 = moat-item)
- **CONSTRAINT:** 6 (CN-01…06)
- **Tổng FR = 41 (trong đó FR-35 = 14 mục con) · CN = 6. Data mọi tính năng theo `reference-data-plane.md`; meta-rule luật VN theo `legal-rule-base.md` (infra, không phải FR).**

## 📊 Rollup trạng thái (đối chiếu code 2026-11-10)

**41 FR chính + 14 mục FR-35.x + 6 CN:**
- ✅ **DONE (26 FR)**: FR-01,02,03,05,06,07,09,10,11,12,13,16,17,19,21,22,23,24,25,26,27,28,29,30,34,36,37,39,40 *(≈29 incl. tiện ích)*
- 🟡 **WIP (4)**: FR-04 (EN xong/ZH defer) · FR-15 (draft generic) · FR-18 (UI VI-only) · FR-20 (thiếu đo scan)
- ❌ **SPEC chưa code (1)**: FR-08 ComplianceAdvisory
- 🔵 **DEFER theo spec (3+1)**: FR-31,32,33 + FR-04-ZH
- **FR-35.x**: **14/14 DONE** (công thức+lịch tính đúng; lookup cần data thật)
- **CN**: **6/6 DONE**

**Chặn bởi NGOÀI (không code thêm được)**: vLLM/GPU · API key Claude · data thật (thuế/lương/phạt/toạ độ/template/gold) · authority_rank 2025 · meta.json thật · Paddle/boto3/hvac.

> Một câu: **không FR nào được rơi.** Đóng module → mọi FR của nó `DONE` hoặc `DEFER` (có lý do). Đây là checklist bàn giao, không phải tài liệu đọc-rồi-quên.
