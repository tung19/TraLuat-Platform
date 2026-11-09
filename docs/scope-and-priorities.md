# TraLuat — Phạm vi & Ưu tiên (kim chỉ nam)

> Một trang chống lan man. Mọi ý tưởng tính năng đi qua **1 bộ lọc** + rơi vào **1 trong 3 nhóm**. Đọc kèm `README.md`, `docs/engineering-principles.md`.

---

## Bộ lọc DUY NHẤT cho mọi ý tưởng mới
Hỏi 3 câu — **trượt bất kỳ câu nào ⇒ KHÔNG xây (hoặc backlog):**
1. **Có dùng MOAT không?** = hiệu lực-thời-gian (bitemporal) + grounding neo điều–khoản + song ngữ VN. *Không dùng moat → là sân đối thủ, bỏ.*
2. **Có giữ được hợp đồng đầu ra không?** = trích dẫn + ngày hiệu lực + confidence/abstain + nhãn AI + HITL.
3. **Có an toàn pháp lý/đạo đức không?** = law-true (mù địa vị), defensive (không evasion), không tư vấn trực tiếp cho công chúng, residency VN.

> Câu thần chú: **grounded · gated · versioned · fail-closed · human-escalated.** Không đạt → không build.

---

## NHÓM 1 — XÂY TRƯỚC (lõi: moat + bán được)
**W1–W6.** Đây là sản phẩm.

> ⚠️ **Tách 2 trục (đừng gộp — lỗi hay gặp):**
> - **Xây-trước (kỹ thuật):** `#1 bitemporal "văn bản tại ngày T"` (W2) — nền của omission (#2) + judgment (#3). *Đây là moat trống nhất + thủ được nhất.* **Nó KHÔNG phải "beachhead"** — tự nó không bán được, chỉ là hạ tầng.
> - **Beachhead (bán):** **FDI compliance + contract review** chạy *trên* #1 — khách B2B trả tiền, trong VN. Đây mới là cửa vào thị trường, đúng north-star "bán việc đã xong".

- **W1** Data pipeline (nạp + trích quan hệ, có cổng chất lượng + ẩn danh).
- **W2** Đồ thị tri thức bitemporal (moat #1) — "văn bản tại ngày T".
- **W3** Retrieval hiệu lực-aware + grounding 3 cổng + eval harness.
- **W4** Auditor hard-gate + (bounded) đa-vai-như-cơ-chế-verify.
- **W5** Backend multi-tenant + residency + egress fail-closed.
- **W6** Review (+omission theo luật@T) · Draft song ngữ · Assistant · **Judgment Analysis (second-opinion)**.
- 🚧 **CỔNG:** không mở nhóm 2 cho tới khi **benchmark 3 chiều (L13) đạt** (đúng điều–khoản / đúng hiệu lực / bắt bỏ sót) + qua các **fix Critical** (`docs/specs/spec-audit-fixes.md`, w2 §11, w3 §8).

---

## NHÓM 2 — BACKLOG (extension: đáng làm, nhưng SAU, theo thứ tự)
Chỉ bắt đầu khi lõi vững. Mỗi cái vẫn phải qua bộ lọc 3 câu.
1. **ComplianceAdvisory** (W7 §1): use case doanh nghiệp → vi phạm? + cách tránh + trích điều luật. *(giá trị thương mại rõ, tái dùng pattern ARCCS/COLING; cần coverage-floor chống false-clear.)*
2. **Vai mở rộng + workbench theo vai** (W7 §2,§4): điều tra / kiểm sát-quyết-định / kiểm toán — *cần guardrail rủi-ro-cao mạnh hơn Judgment Analysis*.
3. **Loophole advisory** (W7 §3): **sau cùng** — nhạy cảm dual-use, cần control thật + rà đạo đức/pháp lý riêng.
4. **Law-simulation: Change-Propagation** (W7 §5b): mô phỏng *tác động khi luật đổi* neo văn bản versioned — *chỉ cái này* trong "law simulation" đáng làm (không ai làm + dùng moat).
5. **PetitionDraftService — soạn đơn từ** (FR-34, W6 §1.2b): khởi kiện/khiếu nại/tố giác theo mẫu. *Mở rộng thương mại, moat chỉ ~20% giá trị → nhóm-2.* **Chốt 3 câu trước khi code** (mẫu trống/đã-điền · audience luật-sư/dân · số loại đơn) + **HITL cứng** (nộp ra toà).

---

## NHÓM 3 — KHÔNG XÂY (đã cân nhắc & loại)
| Bỏ | Vì sao |
|---|---|
| **Mô phỏng toà role-play / diễn lại phiên xử** | đông, repo no-LICENSE, **không neo hiệu lực**, không dùng moat → sân đối thủ |
| **Win-probability / dự đoán kết quả vụ án** | chỉ là classification, **EU rủi-ro-cao**, VN đã có đối thủ (CMC/Viettel) |
| **Xã hội agent có chuẩn (generative-agent society)** | chuẩn trừu tượng, reward-hack — không phải luật thật |
| **Tư vấn "cách lách luật để né"** | evasion — vi phạm đạo đức/định vị; chỉ làm *defensive risk-awareness* |
| **Trang tra cứu luật thuần** | đã có đầy thị trường; ta bán "việc đã xong", không bán search box |
| **Alerting / theo dõi VB mới *như một trụ riêng*** | sân incumbent (LuatVietnam dẫn đầu: theo-dõi-điều-khoản + email). Đừng đua bề rộng. ⚠️ **Giữ, nhưng chỉ dạng *trigger*:** VB/dự thảo mới → **tự chạy lại omission/diff trên hợp đồng khách** → "điều này giờ thiếu/sai" (cái incumbent KHÔNG làm được, vì cần moat). Nhúng vào #2, không dựng độc lập. |
| **Fork cocounsel-legal / phụ thuộc Westlaw** | cần subscription TR, US-only |

---

## Định vị cạnh tranh (chốt sau audit, Nov 2026)
| Đối thủ | Là gì | Đe doạ | Khe hở của ta |
|---|---|---|---|
| **CMC C-OpenAI** (CLEX) | model + benchmark, **state-backed** (pilot Bộ KH&CN) | 🔴 **cao nhất** — đang xây về #2/#3 | **không đụng #1**; mạnh model, **yếu kỷ luật dữ liệu bitemporal** + chưa là sản phẩm. ⚠️ số benchmark là **tự báo**, không dùng làm căn cứ cứng. |
| **LuatVietnam** | tra cứu + AI Q&A + **alert dẫn đầu** | trung — sân #4/#5 | không có #1/#2/#3 dạng sản phẩm; "AI rà soát" chỉ *doc-vs-doc*, không phải "điều còn thiếu" |
| **ThuVienPhapLuat / phapluat.gov.vn** | kho + cờ hiệu lực + lược đồ + **dự thảo** | thấp | chỉ *latest + quan hệ*, không dựng-lại-tại-ngày-T |
| **Lawgical** (trên Claude) | **tầng tra cứu** (MCP connector), indie | thấp | không #1/#2/#3, không bản án/án lệ/dự thảo |

- **Đua bằng gì:** #1 + kỷ luật dữ liệu + **bản án/án lệ dạng sản phẩm**. **KHÔNG** đua benchmark, **KHÔNG** đua tốc độ với nhà nước (CMC) — thắng bằng *độ sâu + đúng*.
- **Phân phối (học Lawgical nhưng có ràng buộc):** MCP/connector + free tier **CHỈ cho luật công khai** (demo, lead-gen). Lõi hợp đồng/bản án vẫn **B2B + residency VN** — connector đẩy qua API ngoài VN = vi phạm egress, cấm với data khách.

---

## Khung 2 lớp — tiện ích (giữ chân) vs moat (trả tiền)
Bê tiện ích tốt nhất của TVPL về, nhưng **đặt đúng lớp** để không lẫn moat với mồi:
```
LỚP GIỮ CHÂN (parity · dùng hằng ngày · MỒI)   →  FR-35 toolbox · FR-36 compare · FR-37 graph · FR-38 forms · FR-09 alert
      ↑ kéo user vào mỗi ngày, giữ chân
LỚP TRẢ TIỀN (moat · lý do MUA)                →  #1 point-in-time · #2 omission · #3 judgment · AI
      ↑ cái TVPL/incumbent KHÔNG có
```
- **Quy tắc:** tiện ích KHÔNG phải moat — nhưng **mỗi tiện ích phải nhúng moat** (neo điều–khoản + `as_of`). Vd calculator thuế của mình **có-nguồn-luật** (neo điều + ngày hiệu lực), khác hẳn TVPL.
- **Không đua:** kho văn bản (mày đã có), cộng đồng DanLuat, 20 năm content của TVPL — sân của họ.
- **Phải match (khe hở cụ thể):** alert **đa kênh (email+SMS) field-targeted** + **dự thảo tracking thật** (TVPL chỉ "surface").
- ⏰ **Đồng hồ chạy:** TVPL + LuatVietnam đang xây AI → moat an toàn nhưng **có hạn thời gian**.

---

## Phân biệt cốt lõi (hay bị lẫn → gây lan man)
- **Đa vai để *cho ra câu trả lời đúng hơn* (W4, có Auditor) = GIỮ** · *diễn lại phiên toà* = BỎ.
- **Advisory *phòng thủ* (cảnh báo rủi ro/vùng mờ) = OK** · *hướng dẫn né luật* = CẤM.
- **Second-opinion có neo cho chuyên gia = OK** · *phán quyết tự động / "thẩm phán sai"* = CẤM (chỉ chỉ ra điểm vênh *ràng buộc được*; chiều tuỳ nghi thì abstain).
- **Claude for Legal = scaffold tầng workflow (tier-3), KHÔNG đóng moat** — fork khung, thay ruột bằng grounding.

---

## Nhắc nhanh về tuân thủ (ràng buộc cứng, không phải tính năng)
Residency VN + cô lập tenant + egress fail-closed (NĐ 356/2025) · nhãn AI (Luật 71/2025) · Judgment/điều-tra/kiểm-sát = rủi-ro-cao QĐ 33/2026 (HITL + logging + engineered, không "hô") · án lệ **ràng buộc** (NQ 04/2019) · nguồn dữ liệu được phép + bản án ẩn danh (NQ 03/2017). Chi tiết: `docs/compliance-vn.md`.

---

## Một dòng cho cả đội
> **Xây lõi hiệu lực-aware cho chắc và chứng minh bằng benchmark. Mọi thứ khác là extension — chỉ chạm khi nó *dùng moat*. Nghi ngờ thì hỏi: "cái này có cần biết luật đúng tại ngày T + neo trích dẫn không?" Không → bỏ.**
