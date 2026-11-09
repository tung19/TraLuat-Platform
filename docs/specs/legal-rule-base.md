# TraLuat — Legal Rule Base (tri thức pháp lý VN, cố định & versioned)

> **Nguồn chân lý DUY NHẤT về meta-rule của luật VN.** Tách cứng khỏi engine code: **engine code migrate/viết lại được; luật trong đây thì KHÔNG** — chỉ đổi khi LUẬT đổi, qua rà soát pháp chế.
> Engine (W2 §4 resolve_conflict, W3 retrieval, W6 services) chỉ **ĐỌC** rule base, không nhúng rule. Đây cũng là **seam portability** (đổi vùng tài phán = thay rule base, giữ engine). Khung khai báo nâng từ `JurisdictionPack` (W6 §2).

---

## 0. 5 tính chất bắt buộc
1. **Declarative + máy-đọc** (YAML/JSON/DSL) — không chôn trong hàm.
2. **Versioned + as_of** — *chính các rule này cũng đổi theo thời gian* → mỗi rule mang `valid_from/valid_to`.
3. **Neo primary-text** — mỗi rule có `source_eid` → chứng minh VÌ SAO (audit trail), không theo trí nhớ.
4. **Người-pháp-chế quản trị** — đổi rule qua rà soát + test + **rollback**, không phải dev PR.
5. **Single source + testable** — một chỗ; mỗi đổi có test-case.

## 0b. 6 nhóm rule trong rule base (gom bằng THAM CHIẾU, không di dời file)
| Nhóm | Sống ở | Vai trò |
|---|---|---|
| `authority_rank` (thang bậc) | §1 (đây) | lex superior |
| Quy tắc giải xung đột | §2 (đây) | superior/posterior/specialis/treaty |
| Quy tắc hiệu lực + hồi tố + chuyển tiếp | §3 (đây) | gate as_of |
| `resolve_as_of` policy | §4 (đây) | chọn mốc |
| `required_clause_rule` | W2/W6 §1.1 | omission (mandatory/default) |
| `DocumentTypePack` | W6 §1.2b | trường bắt buộc đơn từ |

---

## 1. `authority_rank` — thang bậc VBQPPL (versioned, as_of-aware)
> ★ Rank key theo **(cơ quan + loại VB)**, KHÔNG theo loại đơn thuần: Quyết định của Thủ tướng ≠ của UBND tỉnh ≠ của Chủ tịch UBND tỉnh.
> ⚠️ **Trạng thái: CHƯA CHỐT OFFICIAL** — wording khoản Điều 4 bản 2025 lấy từ structured DB (host MOJ sập lúc verify). **Phải pull official** (vbpl.vn / congbao.chinhphu.vn) trước khi load production. Nguồn đã xác minh verbatim: 80/2015 Đ.152/156/172, BLHS Đ.7, số hiệu+ngày của cả 4 luật.

**4 thời kỳ (valid_from):**
| # | valid_from → valid_to | Luật căn cứ |
|---|---|---|
| A1 | 2016-07-01 → 2020-12-31 | 80/2015/QH13 (gốc) |
| A2 | 2021-01-01 → 2025-03-31 | 80/2015 sửa bởi 63/2020/QH14 (minor: +Tổng KTNN vào thông tư liên tịch; thứ tự KHÔNG đổi) |
| B | 2025-04-01 → 2025-06-30 | 64/2025/QH15 (thay 80/2015; bỏ cấp xã; tách TT≠TTLT) |
| C | 2025-07-01 → (hiện hành) | 64/2025 sửa bởi 87/2025/QH15 (bỏ cấp huyện; khôi phục cấp xã; +QĐ Chủ tịch UBND tỉnh) |

**Thang bậc Thời kỳ A (2016-07 → 2025-03), cao→thấp** — *Điều 4 Luật 80/2015 (+63/2020)*:
> ⚠️ Bảng dưới = **A2 (từ 2021-01-01)**. Bản **A1 (2016-07 → 2020-12)**: giống hệt nhưng **bỏ "Tổng KTNN" khỏi mục Thông tư liên tịch (8a)** (63/2020 mới thêm). Thứ tự rank không đổi.
1 Hiến pháp · 2 Bộ luật/Luật/Nghị quyết (Quốc hội) · 3 Pháp lệnh/Nghị quyết + NQ liên tịch (UBTVQH) · 4 Lệnh/Quyết định (Chủ tịch nước) · 5 Nghị định + NQ liên tịch (Chính phủ) · 6 Quyết định (Thủ tướng) · 7 Nghị quyết (HĐTP TANDTC) · 8 Thông tư/Quyết định (Chánh án TANDTC · Viện trưởng VKSNDTC · Bộ trưởng · Tổng KTNN) · 8a Thông tư liên tịch · 9 NQ HĐND tỉnh · 10 QĐ UBND tỉnh · 11 VBQPPL đơn vị HC-KT đặc biệt · 12 NQ HĐND huyện · 13 QĐ UBND huyện · 14 NQ HĐND xã · 15 QĐ UBND xã.

**Thang bậc Thời kỳ B (2025-04 → 2025-06)** — *Điều 4 Luật 64/2025, 14 loại, BỎ cấp xã*: như A nhưng (8) Thông tư và (9) **Thông tư liên tịch tách thành 2 rank riêng**, dừng ở cấp huyện (…NQ HĐND huyện, QĐ UBND huyện), **không có cấp xã**.

**Thang bậc Thời kỳ C (từ 2025-07, hiện hành)** — *Điều 4 Luật 64/2025 sửa bởi 87/2025, 15 loại, chính quyền 2 cấp*:
1 Hiến pháp · 2 Bộ luật/Luật/NQ (QH) · 3 Pháp lệnh/NQ + NQ liên tịch (UBTVQH) · 4 Lệnh/QĐ (Chủ tịch nước) · 5 Nghị định/NQ + NQ liên tịch (Chính phủ) · 6 QĐ (Thủ tướng) · 7 NQ (HĐTP TANDTC) · 8 Thông tư (Chánh án/Viện trưởng/Tổng KTNN/Bộ trưởng) · 9 Thông tư liên tịch · 10 NQ HĐND tỉnh · 11 QĐ UBND tỉnh · 12 **QĐ Chủ tịch UBND tỉnh ★mới** · 13 VBQPPL đơn vị HC-KT đặc biệt · 14 NQ HĐND xã/phường/đặc khu ★khôi phục · 15 QĐ UBND xã. **BỎ cấp huyện.**

## 2. Quy tắc giải xung đột
Căn cứ codified: **Đ.156 Luật 80/2015** / **Đ.58 Luật 64/2025** (áp dụng VBQPPL).
1. ✅ **Lex superior (codified)** — `authority_rank` cao hơn thắng (Đ.156 K2 / Đ.58 K3).
2. ✅ **Lex posterior (codified)** — *cùng cơ quan ban hành*, chọi → ban hành **sau** thắng (Đ.156 K3 / Đ.58 K4).
3. ⚠️ **Lex specialis — NGUYÊN TẮC CHUNG (jurisprudence), CHƯA xác nhận codified trong Đ.156/Đ.58.** Dùng như *heuristic* (cùng rank, chuyên ngành thắng chung — scope metadata), **không trích như điều luật**. → VERIFY-OFFICIAL (§6).
   - 🔴 **posterior ⟂ specialis = ABSTAIN → human:** khi *luật-sau-tổng-quát* đụng *luật-trước-chuyên-biệt* ("lex posterior generalis non derogat priori speciali"), **KHÔNG auto "sau thắng"** → `unresolved → human` (nguyên tắc #6).
4. **★ Ưu tiên điều ước quốc tế** — Đ.58 K5 (từ 2025-04): nội địa không cản điều ước VN là thành viên; xung đột → điều ước thắng, **trừ Hiến pháp**. ⚠️ pre-2025 có thể đã áp qua **Luật Điều ước quốc tế** (không chỉ từ 2025) → VERIFY (§6).
> Lưu ý: clause **lex-mitior** (Đ.156 K4 2015 — *tổng quát cho mọi trách nhiệm pháp lý*, không chỉ hình sự) KHÔNG còn trong Đ.58 — chuyển về hồi tố (Đ.55). → versioned theo as_of (Đ.156 K4 cho vụ ≤2025-03; Đ.55/Đ.58 cho ≥2025-04). Xem §3–4.

## 3. Hiệu lực · hồi tố · chuyển tiếp
- **Áp dụng theo thời điểm** (Đ.156 K1 / Đ.58 K2): VB áp cho **hành vi/sự kiện xảy ra khi VB đang có hiệu lực**. → nền của `as_of`.
- **Hồi tố (Đ.152 2015 / Đ.55 2025):** chỉ khi thật cần + lợi ích chung + cấp trung ương; **CẤM** quy trách nhiệm pháp lý **mới** hoặc **nặng hơn** về trước; VB địa phương không hồi tố. *(Đ.55 toàn văn: VERIFY-OFFICIAL.)*
- **★ Lex mitior — KHÔNG chỉ hình sự:**
  - **Tổng quát (Đ.156 K4, 2015):** luật sau quy **trách nhiệm pháp lý nhẹ hơn / không trách nhiệm** cho hành vi trước → **áp luật sau** (cho *mọi loại* trách nhiệm, không riêng hình sự). *(pre-2025; Đ.58 bỏ, xem Đ.55)*
  - **Hình sự (BLHS Đ.7):** luật nhẹ hơn/bỏ tội/giảm hình phạt **áp NGƯỢC**; luật nặng hơn **không** hồi tố.
  - **Hành chính (Luật Xử lý VPHC):** áp dụng **quy định có lợi** cho đối tượng. *(VERIFY điều cụ thể)*
  → đây là **ngoại lệ bắt buộc của as_of** (xem §4), áp cho hình sự + hành chính + trách nhiệm pháp lý nói chung.
- **Chuyển tiếp:** điều khoản chuyển tiếp giữ quan hệ cũ theo luật cũ trừ khi luật mới quy định khác → **hết hiệu lực ≠ không áp dụng** (nối W3 fix, W2 §4).

## 4. `resolve_as_of` — chọn mốc (cross-cutting, mọi service GỌI, không tự chế)
```
resolve_as_of(input, question_type):
 ① TỰ TRÍCH mốc từ input (ngày ký HĐ / ngày vi phạm / ngày trong bản án…)
 ② Mốc phụ thuộc CÂU HỎI (không phải 1 mốc cứng):
     • hiệu lực HĐ → ngày ký · hậu quả vi phạm → ngày vi phạm
     • thủ tục (thời hiệu/thẩm quyền) → ngày khởi kiện/nộp
     • lex mitior (KHÔNG chỉ hình sự — §3): hình sự (BLHS Đ.7) · hành chính (Luật XLVPHC) ·
       trách nhiệm pháp lý tổng quát (Đ.156 K4, pre-2025) → nếu có luật sau NHẸ HƠN,
       đánh giá CẢ luật@ngày-sự-việc LẪN luật nhẹ hơn, chọn CÓ LỢI cho đối tượng
 ③ Suy ra được → TỰ trả lời + nêu giả định + CONFIRM ("hiểu sự việc xảy ra [X],
    trả lời theo luật tại đó + nêu hệ quả nếu mốc khác") — propose-then-confirm
 ④ Mơ hồ/nhiều mốc/không rõ → HỎI user trước
 ⑤ KHÔNG im lặng lấy "hôm nay"; "hôm nay" chỉ khi user xác nhận MỚI phát sinh
 ⑥ Luôn HIỂN THỊ as_of đã dùng; nhận cả khoảng ngày/không chắc
 ⑦ TRẢ VỀ: as_of_map = {sub_issue → anchor_date}  (★ A/F3-fix: KHÔNG 1 scalar — vd {hiệu-lực-HĐ: 2019, vi-phạm: 2022, thời-hiệu: 2024})
 ⑧ Mốc trích = ML/LLM → PHẢI GATE (confidence + abstain/HITL như citation); batch (API/ComplianceDiff) mơ hồ → FAIL→HITL, KHÔNG today
 ⑨ Lex-mitior: với mỗi anchor, fetch CẢ luật@anchor LẪN luật-sau-nhẹ-hơn → so favorability NGOÀI cổng in_force (dùng applies_from cho hồi tố)
```
`as_of` này chảy xuyên suốt: retrieval → `resolve_conflict` (cổng hiệu lực) → grounding — **cùng một as_of**.

## 5. Quản trị (governance)
- Đổi rule = **PR của pháp chế** (không phải dev): kèm `source_eid` + `valid_from/to` + test-case + **người duyệt** + **rollback**.
- **Trigger luật mới đụng rule:** khi VB mới amend/repeal một `source_eid` rule base đang dùng → auto-flag rule đó cho pháp chế (xem reference-data-plane auto-update). **Không auto-rewrite rule.**
- **Định kỳ human re-review** (vì luật net-new có thể đổi meta-rule mà không amend đúng source_eid — vd Luật Ban hành VBQPPL mới).

## 6. VERIFY-OFFICIAL (chốt trước khi load production)
> 🔴 **★ X4-fix (chaos — ENFORCED load-gate, không chỉ checklist):** mỗi rule mang **`verification_status ∈ {provisional, verified_official, heuristic}`** + `source_hash` của primary-text. **Loader TỪ CHỐI rule `provisional` ở production**; resolution phụ thuộc rule `heuristic` (vd lex_specialis) → **abstain→human**. Rule base chưa-chốt KHÔNG vào prod được bằng cơ chế, không bằng lời hứa. *(đồng bộ Data#12 Round-2.)*
- [ ] Wording khoản Điều 4 bản **64/2025** + **87/2025** (pull vbpl.vn / congbao.chinhphu.vn).
- [ ] Toàn văn **Đ.55 Luật 64/2025** (hồi tố).
- [ ] Thành phần "nghị quyết liên tịch UBTVQH–Chính phủ" từng thời kỳ.
- [ ] Số điều **điều khoản chuyển tiếp** từng luật.
- [ ] **Lex specialis** có codified trong Đ.156/Đ.58 không (hay chỉ nguyên tắc chung) — hiện dùng như heuristic.
- [ ] **Treaty priority pre-2025** nằm ở đâu (Luật Điều ước quốc tế?) — có áp trước Đ.58 không.
- [ ] Điều cụ thể **lex mitior hành chính** (Luật Xử lý VPHC) + toàn văn **Đ.55/Đ.58** để chốt lex-mitior post-2025.
- Nguồn official đã định vị: `vbpl.vn/FileData/.../VanBanGoc_80.2015.QH13.pdf`; congbao cho 63/2020, 64/2025, 87/2025.

---

## 7. Engine dùng rule base thế nào (single-source, call-don't-reimplement)
- `in_force(eid, as_of)` sống DUY NHẤT ở **W2 TemporalRepository**; §4 + W3 + W6 **gọi**, không tự implement.
- `resolve_conflict` (W2 §4) đọc `authority_rank(as_of)` + quy tắc §2 từ đây.
- Mọi service (W6) gọi `resolve_as_of` (§4) — không chôn default "hôm nay".
- Migrate code từ repo: **BÓC rule pháp lý hardcode của họ (US/EU) → ĐỌC từ rule base này.**
