# TraLuat — Định vị cạnh tranh (Nov 2026)

> Chụp nhanh thị trường legal-AI VN + verdict moat nào còn trống. Đọc kèm `docs/scope-and-priorities.md`.
> ⚠️ Nguồn: web research 2 nhánh (Lawgical + landscape). Số benchmark/usage của đối thủ phần lớn **tự báo** — không dùng làm căn cứ cứng.

---

## 1. Bản đồ đối thủ × năng lực

Năng lực: **#1** văn-bản-tại-ngày-T (bitemporal) · **#2** omission (điều bắt buộc còn thiếu) · **#3** judgment analysis (bản án → đúng chưa + án lệ) · **#4** diff+alert · **#5** dự thảo.

| Đối thủ | #1 | #2 | #3 | #4 | #5 | Là gì |
|---|:--:|:--:|:--:|:--:|:--:|---|
| **Lawgical** (trên Claude) | ❌ | ❌ | ❌ | nạp/ngày | ❌ | MCP connector tra cứu, indie (Vương Minh Nguyễn), © 2026 |
| **LuatVietnam + AI Luật** | ❌ | ~* | ~tra cứu | ✅ **dẫn đầu** | ~ | tra cứu + Q&A; "AI rà soát" = mâu thuẫn doc-vs-doc |
| **ThuVienPhapLuat** | ❌ | ❌ | ❌ | newsletter | ✅ | kho ~437k VB + 200k bản án; cờ hiệu lực + lược đồ |
| **phapluat.gov.vn** (Bộ TP) | ❌ | ❌ | ❌ | ~ | ✅ | cổng chính thống, có dự thảo; chạy AI của LuatVietnam |
| **⚠️ CMC C-OpenAI** (CLEX) | ~ | ~bench | ✅bench* | ❌ | ❌ | model + benchmark, **state-backed** (pilot Bộ KH&CN) |
| **Trợ lý ảo Toà án** (Viettel) | ❌ | ❌ | ~truy hồi | ❌ | ❌ | nội bộ toà, chỉ gợi bản án/án lệ tương tự |

\* chỉ là benchmark/model hoặc doc-vs-doc — **chưa phải sản phẩm** đúng nghĩa.

---

## 2. Verdict — 3 mũi moat còn trống không?

| Moat | Trạng thái | Ghi chú |
|---|---|---|
| **#1 văn bản tại ngày T** | 🟢 **trống hẳn** | không ai dựng lại điều luật tại ngày quá khứ bất kỳ; tất cả chỉ *latest + văn bản hợp nhất + cờ hiệu lực*. **Trống nhất + thủ được nhất.** |
| **#2 omission** | 🟡 **gần như trống** | chỉ có LuatVietnam "AI rà soát" (doc-vs-doc) + benchmark CMC; chưa ai làm "điều bắt buộc còn thiếu". |
| **#3 judgment analysis** | 🟡 **trống ở dạng sản phẩm** | toà có trợ lý nội bộ (truy hồi); CMC có "court-decision prediction" ở benchmark. Chưa ai *ship* tool audit bản án theo án lệ. **CMC dễ chạm tới nhất.** |

---

## 3. Đọc chiến lược

1. **Đe doạ thật = CMC, không phải Lawgical.** CMC state-backed, đang xây về #2/#3. Nhưng **không đụng #1**, mạnh model / **yếu kỷ luật dữ liệu bitemporal**, và vẫn là model+pilot chứ chưa là sản phẩm.
2. **#4/#5 = table-stakes** incumbent đã nắm (LuatVietnam dẫn đầu alert; TVPL/cổng có dự thảo). **Đừng đua bề rộng.**
3. **Lawgical = tầng tra cứu**, không phải engine. Điểm mạnh cần ≥: trích Điều–Khoản, nạp mới hằng ngày, cờ hiệu lực, **phân phối MCP/connector + free tier**.

## 4. Hệ quả → đã chốt vào scope

- **Xây-trước (kỹ thuật):** #1 bitemporal (W2). **Beachhead (bán):** FDI compliance/contract trên #1. *(hai trục khác nhau — xem scope §NHÓM 1)*
- **Alerting KHÔNG là trụ riêng** → *trigger* cho `ComplianceDiffService` (W6 §1.5) + omission (W6 §1.1): VB/dự thảo mới → tự rà lại hợp đồng khách → "điều này giờ thiếu/sai".
- **Phân phối:** MCP/free tier **chỉ cho luật công khai** (demo/lead-gen); lõi hợp đồng/bản án B2B + residency VN (connector ra API ngoài = vi phạm egress).
- **Đua CMC bằng:** #1 + kỷ luật dữ liệu + bản án/án lệ dạng sản phẩm — **không** đua benchmark, **không** đua tốc độ nhà nước.

---

## 5. Prior-art FR-34 (soạn đơn từ theo mẫu) — search riêng

| Mảnh | Ngoài kia | Hành động |
|---|---|---|
| Template + required-field assembly | ✅ giải xong OSS — **docassemble, Suffolk Assembly Line, A2J** (MIT) | tái dùng tầng field/validation/PDF |
| Exemplar-RAG drafting ("soạn như mẫu") | ✅ chuẩn **thương mại** — Spellbook/Henchman/Harvey (proprietary, common-law/hợp đồng); **0 repo OSS** | tự xây |
| DocumentTypePack (type→trường bắt buộc theo luật) | ❌ không off-the-shelf; mảnh rời: SALI (taxonomy), OASIS ECF (chỉ metadata, loại trừ nội dung), LegalRuleML | tự xây, học docassemble |
| Omission check | ARCCS (classifier); **InsufficiencyBench ICML 2026** (model yếu F2≈0.46) | tái dùng pattern + đo bằng bench |
| Trigger lakehouse→index | ✅ thiết kế mình **đúng chuẩn** (Delta CDF + scheduled sync + idempotent upsert) | scheduled sync đủ |

**Verdict:** từng nửa không mới, **tổ hợp (DTP neo-luật + exemplar-RAG + hiệu lực@T + civil-law VN + song ngữ) = greenfield**. Prior-art VN mỏng (chỉ `VietnamLegalAdvisor`, là skill không RAG). Steal-list chi tiết: W6 §1.2b.

---

## 6. TVPL feature map đầy đủ + ADOPT-LIST
> ⚠️ Site chặn fetch → số liệu TVPL tự công bố, chưa audit. Recon từ snippet + bên thứ ba.

**TVPL có gì:**
- **Nội dung:** VBQPPL ~430k (tổng ~585k) · Công văn ~137k · Bản án ~200k+ · Án lệ ~90 · VB hợp nhất · Dự thảo (chỉ *surface*) · English ~17.5k (~4%, paid, qua lawnet.vn) · TCVN (full-text paywall) · Biểu mẫu.
- **So sánh & quan hệ:** So sánh văn bản (redline **quan hệ sửa đổi**, không point-in-time) · Lược đồ "gia phả" (**tĩnh**) · cờ hiệu lực (paywall).
- **Tiện ích:** thuế TNCN · Gross↔Net · lương tối thiểu vùng · mã số thuế/ngành/HS · xử phạt giao thông · biểu thuế WTO/ASEAN.
- **Alert:** email tuần (free) · **bản tin field-targeted email+SMS** (paid) · theo dõi văn bản.
- **Cộng đồng/TM:** DanLuat (107k member, danh bạ LS) · Công việc pháp lý · seat-license concurrent-login (B2B, Basic 5 ~386k → Pro X ~124k/ng/th) · **không API công khai** · app iOS (TVPL/LawNet/iThong).
- **AI:** ❌ **CHƯA CÓ** (chỉ đang tuyển "TVPL Legal AI/AI Workspace", chưa ship). LuatVietnam "AI Luật" mới dẫn.
- **Mạng lưới (LawSoft JSC):** thuvienphapluat.vn + lawnet.vn (EN) + danluat + thuviennhadat.vn.

**ADOPT-LIST (bê về → map FR):**
| TVPL | Verdict | → FR |
|---|---|---|
| So sánh văn bản | bê + siêu-nạp (2 ngày bất kỳ) | **FR-36** / FR-01 |
| Lược đồ | bê + siêu-nạp (trục thời gian) | **FR-37** / FR-13 |
| Alert + dự thảo | bê + làm thật (diff giải thích, đa kênh) | **FR-09** |
| Tiện ích/calculator | bê parity + neo-nguồn-luật | **FR-35** |
| Biểu mẫu | bê parity | **FR-38** |
| Cờ hiệu lực / English | đã có, hơn | FR-01/13 · FR-04 |
| DanLuat / kho / content 20 năm | **BỎ / không đua** | — |

**Verdict:** moat lõi (#1 point-in-time · #2 omission · #3 judgment · AI) **TVPL đều KHÔNG có**. TVPL mạnh ở *kho + diff-quan-hệ + tiện ích + alert đa kênh*. → **không đua kho/cộng đồng; match alert; bê tiện ích + siêu-nạp moat.** Khung 2-lớp: `scope-and-priorities`.
