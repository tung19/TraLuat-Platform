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
> **Đối chiếu sau audit 2026-11-10:** xem [bản sửa và bằng chứng kiểm thử](audit-fixes-2026-11-10.md). `DONE` dưới đây chỉ xác nhận phạm vi core ghi trong hàng; không phải chứng nhận production hay tính đúng của dữ liệu pháp lý. Test xanh không thay thế acceptance trên dữ liệu được chuyên gia duyệt.
> Nhóm: **MOAT** (huỷ diệt) · **PARITY** (ngang thị trường) · **BACKLOG** (nhóm 2, sau lõi) · **CONSTRAINT** (ràng buộc cứng, không phải tính năng nhưng cấm bỏ).

---

## A. MOAT — tính năng huỷ diệt (không được thiếu bất kỳ cái nào ở v1 lõi, trừ nơi ghi BACKLOG)

| ID | Tính năng | Spec sở hữu | Nhóm | Trạng thái | Cổng / ghi chú |
|---|---|---|:--:|:--:|---|
| **FR-01** | **Văn bản tại ngày T** (bitemporal, dựng lại luật tại thời điểm) | W2 §3 + W1 Stage 6 | MOAT | ✅ **DONE** | Đã sửa lịch sử transaction-time, subtree repeal đa ngữ và replay theo unit/lang; test PostgreSQL. Dữ liệu cũ hỏng cần đối soát riêng. |
| **FR-02** | **Omission** — điều bắt buộc còn THIẾU vs luật@T | W6 §1.1 (ReviewService 2-pass) | MOAT | 🟡 **WIP** | WIP: hiện là keyword/playbook; chưa kiểm nghĩa phủ định hoặc omission theo luật@T. |
| **FR-03** | **Judgment Analysis** — bản án đúng chưa + điều luật + án lệ | W6 §1.4 + W2 §5.2 | MOAT | 🟡 **WIP** | WIP: audit metadata bền vững; binding precedent lọc ngày. Chưa xác minh đầy đủ căn cứ do người dùng đưa vào. |
| **FR-04** | **Song ngữ VN–EN + neo trích dẫn** tới điều–khoản + ngày hiệu lực | W1 Stage 7 + W3 | MOAT | 🟡 **WIP** | BGE EN→VI đã test offline; API/UI trả nguyên văn nguồn và ngày. Dịch pháp lý HITL chưa; ZH vẫn DEFER. |
| **FR-05** | **Citation Verifier** 3 cổng (exists/in-force/supports) + 6 lớp + **abstain** | W3 §2 | MOAT | 🟡 **WIP** | Local JSON claim/quote và NLI thật đã nối runtime; đầu cuối với Qwen đã test trên fixture. Chưa đủ 6 lớp/gold pháp lý. |
| **FR-06** | **Đa-vai suy luận** (bounded, như cơ chế verify — không role-play) | W4 + W7 §2 | MOAT | 🟡 **WIP** | WIP: checkpoint gắn facts/as_of/lang/checklist/judge/policy + nội dung KB; chưa nghiệm thu suy luận bằng gold thật. |
| **FR-07** | **LAW-TRUE** — mù địa vị bị cáo; thiên vị tách `integrity_note` | W4 | MOAT | ✅ **DONE** | `w4` LAW-TRUE + integrity_note. |
| **FR-08** | **ComplianceAdvisory** — hoạt động DN → vi phạm? + cách tránh + trích dẫn | W7 §1 | MOAT/BACKLOG | 🟡 **WIP** | Đã truyền indexed retrieval/local gateway/NLI và xử lý lỗi model; chưa nghiệm thu tư vấn bằng corpus/gold thật. |
| **FR-09** | **ComplianceDiff khi luật đổi** + **alert-trigger** (VB/dự thảo mới → tự rà lại hợp đồng khách) | W6 §1.5 + change-watch trigger | MOAT | 🟡 **WIP** | WIP: subscription commit và RLS đã test; alert hook có sẵn nhưng chưa nối toàn bộ fan-out/review tự động ở runtime. |
| **FR-41** | **Cross-document conflict & consistency check** (Luật nói A, Thông tư nói B → theo thứ bậc cái nào thắng; phát hiện vượt-uỷ-quyền) | W2 §4 `resolve_conflict` + `legal-rule-base` + W6 service | MOAT | 🟡 **WIP** | WIP: còn provisional rank, chưa version theo as_of; không coi conflict output là kết luận pháp lý đã nghiệm thu. |

---

## B. PARITY — nền để vào cuộc (cấm thiếu)

| ID | Tính năng | Spec sở hữu | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-10** | Hybrid retrieval (BM25+bge-m3+RRF+rerank) + lọc hiệu lực + tenant | W3 §1 | 🟡 **WIP** | Runtime đã nối FTS + BGE + RRF, identity model và canonical freshness gate. FTS chưa phải BM25; cross-encoder chưa cấu hình. |
| **FR-11** | Hỏi–đáp pháp lý grounded | W6 §1.3 (AssistantService) | 🟡 **WIP** | API → index → Qwen local → NLI → nguồn đã test đầu cuối với dữ liệu giả. Chưa có corpus/gold pháp lý để nghiệm thu. |
| **FR-12** | Phân rã cấu trúc Điều/Khoản/Điểm + eId | W1 Stage 3 | ✅ **DONE** | Core DONE: Mục định danh theo Chương; giữ continuation của Điểm; test parser adversarial. |
| **FR-13** | Đồ thị tri thức (dẫn chiếu/hướng dẫn/thứ bậc) | W2 §5.1 | 🟡 **WIP** | WIP: PostgreSQL traversal chỉ dùng cạnh approved và giới hạn hop; Neo4j live chưa kiểm trong đợt sửa. |
| **FR-14** | Tóm tắt VB / vụ việc | W4 / W6 | 🟡 **WIP** | Đã nối indexed retrieval/local gateway/NLI và nguồn UI; thiếu acceptance độ bao phủ tóm tắt. |
| **FR-15** | Soạn hợp đồng song ngữ | W6 §1.2 (DraftService) | 🟡 **WIP** | Pipeline draft có adapter local/index/NLI; hợp đồng song ngữ và chất lượng draft chưa nghiệm thu. |
| **FR-34** | **Soạn ĐƠN TỪ pháp lý theo mẫu** (khởi kiện/khiếu nại/tố giác…) — học từ kho mẫu (RAG, không fine-tune) | W6 §1.2b (PetitionDraftService) + DTP (L10) + TES (W3) | 🟡 **WIP** | WIP: template công phải reviewed + provenance + kiểm PII trước embedding; cần corpus mẫu được duyệt và serving thật. |
| **FR-16** | Rà soát hợp đồng | W6 §1.1 (ReviewService) | 🟡 **WIP** | WIP: dùng chung ReviewService với FR-02, chưa đủ semantic/as-of omission. |
| **FR-17** | Multi-tenant (RLS, cô lập) | W5 §2 | ✅ **DONE** | Core DONE: danh tính DB, role non-owner, kiểm cả membership đặc quyền; test provider thật hai tenant. Cần provision khi triển khai. |
| **FR-18** | Giao diện song ngữ | W6 §3 (L12) | ✅ **DONE** | `?lang=en` dịch nhãn UI (index + /tools) + toggle VI/EN. |

---

## C. DATA / PIPELINE (W1–W2 — cấm thiếu, nền của mọi thứ)

| ID | Tính năng | Spec | Trạng thái |
|---|---|---|:--:|
| **FR-19** | Ingest + dedup | W1 Stage 1 | ✅ **DONE** — Core DONE: FRBR giữ hậu tố cơ quan, source hash mismatch yêu cầu duyệt, savepoint từng tài liệu. |
| **FR-20** | OCR / parse PDF (+ đo tỉ lệ scan) | W1 Stage 2 + §4 | 🟡 **WIP** — OCR dòng (VietOCR) + full-page port có; **đo tỉ lệ scan** chưa |
| **FR-21** | Trích metadata (số hiệu, ngày ban hành, **ngày hiệu lực**, cơ quan) | W1 Stage 4 | ✅ **DONE** — Core DONE: tách mệnh đề hiệu lực toàn văn bản khỏi ngoại lệ từng unit; cần kiểm corpus thật. |
| **FR-22** | Trích quan hệ sửa đổi/bãi bỏ | W1 Stage 5 | ✅ **DONE** — Core DONE: đích Điều chưa resolve giữ unresolved; không được biến thành quan hệ toàn văn bản; NULL-safe dedup. |
| **FR-23** | Engine trích dẫn/sửa đổi VN (`vn-legal-db`, pattern eyecite) | W1 §5 | 🟡 **WIP** — WIP: review/materialization tách biệt; amends thiếu payload không báo thành công và vẫn ở hàng đợi. |
| **FR-24** | Giải xung đột quy phạm (deterministic) | W2 §4 | 🟡 **WIP** — WIP: posterior yêu cầu cùng cơ quan/ngày ban hành; rank mặc định vẫn provisional và chưa version theo as_of. |
| **FR-25** | Chunking/indexing handoff | W1 Stage 8 + W3 chunking | ✅ **DONE** — Core: CLI reindex, kiểm vector/identity; duyệt repeal/replaces qua runtime cập nhật index cùng transaction. Import trực tiếp phải gọi reindex. |

---

## D. PLATFORM / GOVERNANCE (cấm thiếu)

| ID | Tính năng | Spec | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-26** | JurisdictionPack (portability, VN-first) | W6 §2 (L10) | ✅ **DONE** | `w6/jurisdiction` rank/vai theo vùng. |
| **FR-27** | Eval harness + eval-gate 3 chiều (L13) | W3 §4 + W6 §4 | 🟡 **WIP** | WIP: gate dùng omission_recall thật, tập rỗng fail; chưa có gold đủ để nghiệm thu. |
| **FR-28** | Observability (L11) | W5 §4 | ✅ **DONE** | `/metrics` Prometheus + OTel tracing (`w5/tracing`). |
| **FR-29** | Human Knowledge-Ops flywheel (L14) | W6 §5 | 🟡 **WIP** | Quyền platform/audit/connector riêng; repeal/replaces đã nối reindex. Amends thiếu payload vẫn ở queue; workflow nhập text sửa chưa có. |
| **FR-30** | LLM Gateway phân tầng (RULE→ML-local→LLM) + egress guard | W3 §3 + W5 §2.5/§3.1b | 🟡 **WIP** | Ollama thật đã nối; lỗi/JSON sai abstain, không fallback cloud. Mặc định disabled, demo tường minh. Residency và routing chất lượng chưa nghiệm thu. |

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
| **FR-35** | **Legal utilities toolbox** — **14 mục, bảng chi tiết FR-35.x bên dưới** (35.13 là ⚡moat-item) | tiện ích TVPL | parity trên W2/W3 (+ 35.13 moat) | 🟡 **WIP** | WIP: contract/range/source gate và publication version bất biến đã test; thiếu dữ liệu thật và contract cho một số dataset. |
| **FR-36** | **Document compare (as-of)** — so 2 phiên bản / **2 ngày BẤT KỲ** của cùng VB, redline cấp điều–khoản | "so sánh văn bản" | **powered by FR-01** | ✅ **DONE** | Core DONE: document_as_of giữ lịch sử và tiêu đề đúng thời điểm; test subtree repeal + compare. |
| **FR-37** | **Effectivity-aware relationship graph** — viz "gia phả" VB có **trục thời gian** (query in-force@T) | "lược đồ" | **powered by FR-13** | 🟡 **WIP** | WIP: lọc cạnh approved và bound-hop; chưa kiểm Neo4j/GDS live trong đợt sửa. |
| **FR-38** | **Forms / biểu mẫu library** — kho mẫu tải được | "biểu mẫu" | nối FR-34 | 🟡 **WIP** | WIP: validate finite-number, mẫu công qua review/PII; thư viện mẫu thật chưa được nghiệm thu. |
| **FR-39** | **Directory VPLS + bản đồ "gần bạn"** | DanLuat (không geo) | **PostGIS** + reference-data-plane | 🟡 **WIP** | WIP: PostGIS test đạt, kiểm tọa độ/radius/kind và PII; dữ liệu/freshness cần duyệt. |
| **FR-40** | **Danh bạ liên hệ công khai** (cán bộ khu vực…) | — | Postgres + reference-data-plane | 🟡 **WIP** | WIP: cùng directory store có validation; danh bạ thật cần nguồn và freshness. |

### FR-35.x — chi tiết 14 tiện ích (chống sót từng cái)
> ✅ = TVPL confirmed có · ⚠️ = cần verify / đối thủ có. Mỗi mục đóng xong phải tick `DONE`/`DEFER`.
> 🔴 **Audit (đọc trước):** **chỉ ⚡35.13 là MOAT** (as-of thật sự giá trị). **35.1–35.12 = parity** — neo-luật chỉ là *nhãn provenance*, không phải khác biệt (user chỉ cần "hiện tại"). **Làm 3–4 cái dùng nhiều trước** (35.1 PIT, 35.6 gross-net, 35.7 lương vùng), KHÔNG bung 14. **Dated-logic (công thức đổi theo ngày) = tự BUILD** — OpenFisca chỉ date-hoá *tham số*, không date-hoá *công thức*. **Abstain khi luật mơ hồ** (calc sai hại hơn hardcode thật thà).

| ID | Tiện ích | TVPL | Trạng thái | Mình hơn (neo moat) |
|---|---|:--:|:--:|---|
| **35.1** | Tính thuế TNCN (auto BHXH 8%/BHYT 1.5%) | ✅ | 🟡 **WIP** | `calculator("thue_tncn")` neo bậc thuế + as_of |
| **35.2** | Tính thuế GTGT | ⚠️ | 🟡 **WIP** | `calculator("thue_gtgt")` neo thuế-suất@T |
| **35.3** | Tra cứu mã số thuế + tình trạng hoạt động | ✅ | 🟡 **WIP** | `calculator("tra_mst")` reference |
| **35.4** | Biểu thuế XNK (WTO/ASEAN) + tra mã HS | ✅ | 🟡 **WIP** | `calculator("bieu_thue_xnk")` HS+hiệp định@T |
| **35.5** | Lịch nộp thuế/báo cáo | ⚠️ | 🟡 **WIP** | `calculator("lich_nop_thue")` reference@T |
| **35.6** | Gross ↔ Net lương | ✅ | 🟡 **WIP** | `calculator("gross_net")` TNCN luỹ tiến + BH + giảm-trừ, hiệu-lực@T |
| **35.7** | Lương tối thiểu vùng (tỉnh/huyện) | ✅ | 🟡 **WIP** | `calculator("luong_toi_thieu")` |
| **35.8** | BHXH một lần / trợ cấp thất nghiệp | ⚠️ | 🟡 **WIP** | `calculator("bhxh_mot_lan")` công thức hệ-số trước/sau 2014@T |
| **35.9** | Lương làm thêm giờ / ngày lễ | ⚠️ | 🟡 **WIP** | `calculator("lam_them_gio")` hệ-số theo loại-ngày@T (neo BLLĐ) |
| **35.10** | Tra cứu mã ngành nghề KD | ✅ | 🟡 **WIP** | `calculator("tra_nganh")` VSIC reference |
| **35.11** | Tra cứu xử phạt giao thông | ✅ | 🟡 **WIP** | `calculator("muc_phat")` neo NĐ@T |
| **35.12** | Từ điển pháp lý / thuật ngữ | ⚠️ | 🟡 **WIP** | `tools/termbank` VN-EN-ZH neo điều |
| **⚡35.13** | **Tính thời hiệu / thời hạn tố tụng** (khởi kiện, kháng cáo, khiếu nại…) | ⚠️ (TVPL chỉ đếm ngày thô) | 🟡 **WIP** | `tools/deadlines` hiệu-lực-aware + neo điều + lùi ngày nghỉ + `/deadline`. **MOAT-ITEM.** |
| **35.14** | Đếm ngày / lịch âm-dương | ⚠️ | ✅ **DONE** | `tools/calendar_vn` + `tools/lunar` (thuật toán Hồ Ngọc Đức) → Tết/Giỗ Tổ TÍNH tự động, deadline tự lùi. |

> **FR-35:** 13 mục WIP cần dữ liệu/công thức được chuyên gia nghiệm thu; 35.14 có core lịch đã test. `lich_nop_thue` và `ma_nganh` chưa có contract riêng nên từ chối publication. Không coi fixture test là dữ liệu pháp lý được duyệt.

---

## F. CONSTRAINT — ràng buộc cứng (không phải tính năng, nhưng BỎ = vi phạm pháp lý)

| ID | Ràng buộc | Spec | Trạng thái |
|---|---|---|:--:|
| **CN-01** | Data residency VN + egress fail-closed (NĐ 356/2025) | W5 §3.1 / §3.1b | 🟡 **WIP** — egress code fail-closed đã test; residency vật lý chưa chứng minh |
| **CN-02** | Nhãn AI (Luật 71/2025, NĐ 142/2026) | W5 §3.4 | ✅ **DONE** |
| **CN-03** | Judgment/điều-tra/kiểm-sát = rủi-ro-cao: HITL + logging (QĐ 33/2026) | compliance-vn | 🟡 **WIP** — audit durable và HITL flag đã có; quy trình người ký chưa nghiệm thu |
| **CN-04** | Án lệ **ràng buộc** (NQ 04/2019) | W2 §5.2 | ✅ **DONE** — `binding_precedents` (effective@T) + judgment cờ án-lệ-ràng-buộc bỏ sót |
| **CN-05** | Nguồn được phép + bản án ẩn danh (NQ 03/2017) | W1 + data-handoff | ✅ **DONE** — license-gate + `w1/anonymize` áp khi ingest bản án |
| **CN-06** | Mã hoá key-per-tenant + zero-retention (tuỳ tenant) | W5 §2.4 / §3.2 | 🟡 **WIP** — SoftwareKMS chỉ là scaffold; chưa triển khai KMS và zero-retention thực tế |

---

## Tổng kết đếm (để đối chiếu nhanh — nếu con số lệch là có cái bị thêm/bớt ngoài quy trình)
- **MOAT:** 10 (FR-01…09 **+ FR-41** cross-doc conflict) — *FR-08 nhóm-2*
- **PARITY:** 9 (FR-10…18)
- **DATA/PIPELINE:** 7 (FR-19…25)
- **PLATFORM/GOV:** 5 (FR-26…30)
- **BACKLOG:** 4 (FR-31…33 **+ FR-34** đơn từ — nhóm-2, liệt kê ở bảng PARITY dưới FR-15 nhưng trạng thái WIP)
- **GIỮ CHÂN/TIỆN ÍCH:** 6 (FR-35…40 — bê từ TVPL + siêu-nạp moat; FR-39 map/geo, FR-40 danh bạ); **FR-35 nở ra 14 tiện ích con FR-35.1…35.14** (35.13 = moat-item)
- **CONSTRAINT:** 6 (CN-01…06)
- **Tổng FR = 41 (trong đó FR-35 = 14 mục con) · CN = 6. Data mọi tính năng theo `reference-data-plane.md`; meta-rule luật VN theo `legal-rule-base.md` (infra, không phải FR).**

## Trạng thái sau audit 2026-11-10

Giữ đủ 41 FR, 14 mục FR-35.x và 6 CN ở các bảng trên. Bỏ rollup cũ “29 DONE / 6 CN DONE” vì nó gộp core code, scaffolding và nghiệm thu production.

Ngày 11/11 đã nối FTS/BGE/RRF, local model và NLI vào runtime; xem [bằng chứng và cấu hình](local-ai-wiring-2026-11-11.md). Các phần còn cần code gồm semantic/as-of omission, versioned legal rule base, BM25/cross-encoder, payload sửa đổi đã duyệt và fan-out runtime. Các phần cần dữ liệu/hạ tầng gồm gold và nguồn luật được duyệt, identity issuer, KMS, residency, kiểm thử tải và Neo4j/GDS. Đây là backlog cụ thể, không phải tất cả đều bị chặn bởi yếu tố bên ngoài.

Chi tiết tình trạng A01–A30, migration, kiểm thử và giới hạn: [audit-fixes-2026-11-10.md](audit-fixes-2026-11-10.md).
