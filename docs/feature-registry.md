# TraLuat — Sổ cái tính năng (Feature Registry) — CHỐNG BỎ SÓT

> **Nguồn chân lý DUY NHẤT về "platform có những tính năng gì".** Mọi tính năng rải trong W1–W7 được gom về đây, mỗi cái 1 **ID (FR-xx)** + spec sở hữu + trạng thái + cổng.
>
> 🔒 **LUẬT CHỐNG BỎ SÓT (bắt buộc khi implement):**
> 1. Mỗi `FR-xx` phải map tới ít nhất 1 **build task** trong spec sở hữu.
> 2. Khi đóng một module, mỗi FR của nó phải ở trạng thái **Done** (qua acceptance test của spec) **hoặc** **Deferred** (ghi rõ lý do + ngày xem lại). **KHÔNG được để trống / biến mất.**
> 3. PR không được merge nếu đụng một FR mà không cập nhật cột *Trạng thái* ở đây.
> 4. Review hằng tuần: quét cả bảng, không FR nào "rơi" khỏi radar.
>
> Trạng thái: `SPEC` = đã đặc tả, chưa code · `WIP` · `DONE` (qua acceptance) · `DEFER` (hoãn, có lý do).
> Nhóm: **MOAT** (huỷ diệt) · **PARITY** (ngang thị trường) · **BACKLOG** (nhóm 2, sau lõi) · **CONSTRAINT** (ràng buộc cứng, không phải tính năng nhưng cấm bỏ).

---

## A. MOAT — tính năng huỷ diệt (không được thiếu bất kỳ cái nào ở v1 lõi, trừ nơi ghi BACKLOG)

| ID | Tính năng | Spec sở hữu | Nhóm | Trạng thái | Cổng / ghi chú |
|---|---|---|:--:|:--:|---|
| **FR-01** | **Văn bản tại ngày T** (bitemporal, dựng lại luật tại thời điểm) | W2 §3 + W1 Stage 6 | MOAT | SPEC | **rễ cái** — #02/#03/#05 phụ thuộc. Gate L13 "đúng hiệu lực". |
| **FR-02** | **Omission** — điều bắt buộc còn THIẾU vs luật@T | W6 §1.1 (ReviewService 2-pass) | MOAT | SPEC | cần coverage-floor chống false-clear |
| **FR-03** | **Judgment Analysis** — bản án đúng chưa + điều luật + án lệ | W6 §1.4 + W2 §5.2 | MOAT | SPEC | ⚠️ rủi-ro-cao: HITL+logging; abstain chiều tuỳ nghi |
| **FR-04** | **Song ngữ VN–EN + neo trích dẫn** tới điều–khoản + ngày hiệu lực | W1 Stage 7 + W3 | MOAT | SPEC | EN = v1 (moat). 🔴 **ZH = DEFER (backlog, KHÔNG v1)** — không có parallel corpus VN-ZH, cross-border chủ yếu làm EN, cầu chưa chứng minh; bật khi có cầu thật. Dịch pháp lý cần **HITL + `equivalence_type`** (civil↔common law). Greenfield; reuse Akoma/ELI + VLQA (license chưa chắc). |
| **FR-05** | **Citation Verifier** 3 cổng (exists/in-force/supports) + 6 lớp + **abstain** | W3 §2 | MOAT | SPEC | bất biến mọi câu trả lời |
| **FR-06** | **Đa-vai suy luận** (bounded, như cơ chế verify — không role-play) | W4 + W7 §2 | MOAT | SPEC | có Auditor hard-gate |
| **FR-07** | **LAW-TRUE** — mù địa vị bị cáo; thiên vị tách `integrity_note` | W4 | MOAT | SPEC | không bao giờ đổi kết luận pháp lý |
| **FR-08** | **ComplianceAdvisory** — hoạt động DN → vi phạm? + cách tránh + trích dẫn | W7 §1 | MOAT/BACKLOG | SPEC | nhóm-2 (sau lõi) |
| **FR-09** | **ComplianceDiff khi luật đổi** + **alert-trigger** (VB/dự thảo mới → tự rà lại hợp đồng khách) | W6 §1.5 + change-watch trigger | MOAT | SPEC | ⚡ cái incumbent KHÔNG làm được. Alert = *trigger*, không phải trụ riêng. 🔴 **Dự thảo = kênh "dự báo", KHÔNG phải finding tuân thủ** (chưa in-force → đụng moat #1). Có ngưỡng chống alert-fatigue. |
| **FR-41** | **Cross-document conflict & consistency check** (Luật nói A, Thông tư nói B → theo thứ bậc cái nào thắng; phát hiện vượt-uỷ-quyền) | W2 §4 `resolve_conflict` + `legal-rule-base` + W6 service | MOAT | SPEC | ⚡ LuatVietnam "AI rà soát" chỉ doc-vs-doc nông; mình = thứ-bậc + hiệu-lực@T + cấp-yếu-tố. ⚠️ **F5-fix: `resolve_conflict` = RESOLUTION (giải tập đã-flag); DETECTION = IOU greenfield/HARD cần deliverable RIÊNG (input→model→output).** Tới khi có detection: **scope v1 = "giải xung đột do human/retrieval flag", KHÔNG "tự tìm".** High-stakes → HITL + "có dấu hiệu". Sequence SAU #1+graph. Loại finding THỨ BA (≠ omission ≠ ComplianceDiff). |

---

## B. PARITY — nền để vào cuộc (cấm thiếu)

| ID | Tính năng | Spec sở hữu | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-10** | Hybrid retrieval (BM25+bge-m3+RRF+rerank) + lọc hiệu lực + tenant | W3 §1 | SPEC | — |
| **FR-11** | Hỏi–đáp pháp lý grounded | W6 §1.3 (AssistantService) | SPEC | — |
| **FR-12** | Phân rã cấu trúc Điều/Khoản/Điểm + eId | W1 Stage 3 | SPEC | Bluebell pattern |
| **FR-13** | Đồ thị tri thức (dẫn chiếu/hướng dẫn/thứ bậc) | W2 §5.1 | SPEC | — |
| **FR-14** | Tóm tắt VB / vụ việc | W4 / W6 | SPEC | — |
| **FR-15** | Soạn hợp đồng song ngữ | W6 §1.2 (DraftService) | SPEC | — |
| **FR-34** | **Soạn ĐƠN TỪ pháp lý theo mẫu** (khởi kiện/khiếu nại/tố giác…) — học từ kho mẫu (RAG, không fine-tune) | W6 §1.2b (PetitionDraftService) + DTP (L10) + TES (W3) | **BACKLOG** (nhóm-2) | 🟠 **mở rộng thương mại, KHÔNG phải mũi moat lõi** (moat chỉ ~20% giá trị đơn). **3 câu phải chốt trước khi code** (mẫu trống/đã-điền · audience luật-sư/dân · số loại đơn) + **risk-posture HITL cứng** (nộp ra toà). Xem W6 §1.2b banner audit. |
| **FR-16** | Rà soát hợp đồng | W6 §1.1 (ReviewService) | SPEC | chung với FR-02 |
| **FR-17** | Multi-tenant (RLS, cô lập) | W5 §2 | SPEC | — |
| **FR-18** | Giao diện song ngữ | W6 §3 (L12) | SPEC | — |

---

## C. DATA / PIPELINE (W1–W2 — cấm thiếu, nền của mọi thứ)

| ID | Tính năng | Spec | Trạng thái |
|---|---|---|:--:|
| **FR-19** | Ingest + dedup | W1 Stage 1 | SPEC |
| **FR-20** | OCR / parse PDF (+ đo tỉ lệ scan) | W1 Stage 2 + §4 | SPEC |
| **FR-21** | Trích metadata (số hiệu, ngày ban hành, **ngày hiệu lực**, cơ quan) | W1 Stage 4 | SPEC |
| **FR-22** | Trích quan hệ sửa đổi/bãi bỏ | W1 Stage 5 | SPEC |
| **FR-23** | Engine trích dẫn/sửa đổi VN (`vn-legal-db`, pattern eyecite) | W1 §5 | SPEC |
| **FR-24** | Giải xung đột quy phạm (deterministic) | W2 §4 | SPEC |
| **FR-25** | Chunking/indexing handoff | W1 Stage 8 + W3 chunking | SPEC |

---

## D. PLATFORM / GOVERNANCE (cấm thiếu)

| ID | Tính năng | Spec | Trạng thái | Ghi chú |
|---|---|---|:--:|---|
| **FR-26** | JurisdictionPack (portability, VN-first) | W6 §2 (L10) | SPEC | — |
| **FR-27** | Eval harness + eval-gate 3 chiều (L13) | W3 §4 + W6 §4 | SPEC | 🚧 **CỔNG mở nhóm-2** |
| **FR-28** | Observability (L11) | W5 §4 | SPEC | — |
| **FR-29** | Human Knowledge-Ops flywheel (L14) | W6 §5 | SPEC | không rò rỉ text hợp đồng tenant |
| **FR-30** | LLM Gateway phân tầng (RULE→ML-local→LLM) + egress guard | W3 §3 + W5 §2.5/§3.1b | SPEC | — |

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
| **FR-35** | **Legal utilities toolbox** — **14 mục, bảng chi tiết FR-35.x bên dưới** (35.13 là ⚡moat-item) | tiện ích TVPL | parity trên W2/W3 (+ 35.13 moat) | SPEC | mỗi kết quả **neo điều–khoản + ngày hiệu lực** (calculator *có-nguồn-luật*, as_of-aware) — TVPL không làm |
| **FR-36** | **Document compare (as-of)** — so 2 phiên bản / **2 ngày BẤT KỲ** của cùng VB, redline cấp điều–khoản | "so sánh văn bản" | **powered by FR-01** | SPEC | TVPL so bản-bị-thay vs bản-thay; mình so **ngày T1 vs T2 bất kỳ** (point-in-time thật) |
| **FR-37** | **Effectivity-aware relationship graph** — viz "gia phả" VB có **trục thời gian** (query in-force@T) | "lược đồ" | **powered by FR-13** | SPEC | TVPL sơ đồ tĩnh; mình graph **time-travel** |
| **FR-38** | **Forms / biểu mẫu library** — kho mẫu tải được | "biểu mẫu" | nối FR-34 | SPEC | nối đơn-từ FR-34 |
| **FR-39** | **Directory VPLS + bản đồ "gần bạn"** | DanLuat (không geo) | **PostGIS** + reference-data-plane | SPEC | 🟠 **ưu tiên THẤP, land-grab** (0 moat, copy được). **Trọng tâm = DATA-FRESHNESS** (thu thập + giữ tươi địa chỉ/phone), map chỉ 10%. VN chưa ai làm. |
| **FR-40** | **Danh bạ liên hệ công khai** (cán bộ khu vực…) | — | Postgres + reference-data-plane | SPEC | 🟠 ưu tiên thấp. Blueprint **My-Reps (MIT)**: geocode→đa-giác→bảng. **Rủi ro freshness** (My-Reps chết khi API tắt) → cơ chế cập nhật là chính. |

### FR-35.x — chi tiết 14 tiện ích (chống sót từng cái)
> ✅ = TVPL confirmed có · ⚠️ = cần verify / đối thủ có. Mỗi mục đóng xong phải tick `DONE`/`DEFER`.
> 🔴 **Audit (đọc trước):** **chỉ ⚡35.13 là MOAT** (as-of thật sự giá trị). **35.1–35.12 = parity** — neo-luật chỉ là *nhãn provenance*, không phải khác biệt (user chỉ cần "hiện tại"). **Làm 3–4 cái dùng nhiều trước** (35.1 PIT, 35.6 gross-net, 35.7 lương vùng), KHÔNG bung 14. **Dated-logic (công thức đổi theo ngày) = tự BUILD** — OpenFisca chỉ date-hoá *tham số*, không date-hoá *công thức*. **Abstain khi luật mơ hồ** (calc sai hại hơn hardcode thật thà).

| ID | Tiện ích | TVPL | Trạng thái | Mình hơn (neo moat) |
|---|---|:--:|:--:|---|
| **35.1** | Tính thuế TNCN (auto BHXH 8%/BHYT 1.5%) | ✅ | SPEC | neo từng bậc thuế về điều + ngày hiệu lực |
| **35.2** | Tính thuế GTGT | ⚠️ | SPEC | neo thuế suất về NĐ/TT@T |
| **35.3** | Tra cứu mã số thuế + tình trạng hoạt động | ✅ | SPEC | — |
| **35.4** | Biểu thuế XNK (WTO/ASEAN) + tra mã HS | ✅ | SPEC | neo biểu thuế theo hiệp định/ngày |
| **35.5** | Lịch nộp thuế/báo cáo | ⚠️ | SPEC | sinh từ luật@T |
| **35.6** | Gross ↔ Net lương | ✅ | SPEC | neo tỷ lệ trích về luật@T |
| **35.7** | Lương tối thiểu vùng (tỉnh/huyện) | ✅ | SPEC | tự đổi khi NĐ lương mới in-force |
| **35.8** | BHXH một lần / trợ cấp thất nghiệp | ⚠️ | SPEC | neo công thức về luật BHXH@T |
| **35.9** | Lương làm thêm giờ / ngày lễ | ⚠️ | SPEC | neo BLLĐ@T |
| **35.10** | Tra cứu mã ngành nghề KD | ✅ | SPEC | neo về QĐ ngành nghề |
| **35.11** | Tra cứu xử phạt giao thông | ✅ | SPEC | neo mức phạt về NĐ@T + điều |
| **35.12** | Từ điển pháp lý / thuật ngữ | ⚠️ | SPEC | định nghĩa neo về văn bản gốc |
| **⚡35.13** | **Tính thời hiệu / thời hạn tố tụng** (khởi kiện, kháng cáo, khiếu nại…) | ⚠️ (TVPL chỉ đếm ngày thô) | SPEC | **MOAT-ITEM** — tính theo luật tố tụng@T, không phải calculator thường; gắn FR-34 + FR-02. TVPL/incumbent KHÔNG làm được. |
| **35.14** | Đếm ngày / lịch âm-dương | ⚠️ | SPEC | nền cho 35.13 |

---

## F. CONSTRAINT — ràng buộc cứng (không phải tính năng, nhưng BỎ = vi phạm pháp lý)

| ID | Ràng buộc | Spec | Trạng thái |
|---|---|---|:--:|
| **CN-01** | Data residency VN + egress fail-closed (NĐ 356/2025) | W5 §3.1 / §3.1b | SPEC |
| **CN-02** | Nhãn AI (Luật 71/2025, NĐ 142/2026) | W5 §3.4 | SPEC |
| **CN-03** | Judgment/điều-tra/kiểm-sát = rủi-ro-cao: HITL + logging (QĐ 33/2026) | compliance-vn | SPEC |
| **CN-04** | Án lệ **ràng buộc** (NQ 04/2019) | W2 §5.2 | SPEC |
| **CN-05** | Nguồn được phép + bản án ẩn danh (NQ 03/2017) | W1 + data-handoff | SPEC |
| **CN-06** | Mã hoá key-per-tenant + zero-retention (tuỳ tenant) | W5 §2.4 / §3.2 | SPEC |

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

> Một câu: **không FR nào được rơi.** Đóng module → mọi FR của nó `DONE` hoặc `DEFER` (có lý do). Đây là checklist bàn giao, không phải tài liệu đọc-rồi-quên.
