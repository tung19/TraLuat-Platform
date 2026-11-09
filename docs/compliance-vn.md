# TraLuat — Ràng buộc pháp lý VN (verify-first)

> Kết quả kiểm chứng từ nguồn gốc/uy tín (2026-11-05). Đọc kèm `implementation-architecture.md`.
> ⚠️ Mọi mục dưới đây đủ tốt để **thiết kế**, nhưng phần đánh dấu **[cần primary-text]** phải đối chiếu Công báo/văn bản gốc **trước khi tư vấn cho khách hoặc chốt pháp lý**.

---

## 1. Bảo vệ dữ liệu cá nhân (ảnh hưởng W5 Backend, W6 Platform)

**Khung mới (ĐÃ xác minh):** không còn là "NĐ 13/2023" như brief gốc. Giờ là:
- **Luật số 91/2025/QH15 về Bảo vệ dữ liệu cá nhân** — thông qua 26/6/2025, **hiệu lực 1/1/2026** (Điều 38(1)).
- Nghị định hướng dẫn **356/2025/NĐ-CP** (31/12/2025, hiệu lực 1/1/2026), **thay thế NĐ 13/2023**.

**Ràng buộc kiến trúc then chốt:**
| Điều | Nội dung | Tác động TraLuat |
|---|---|---|
| **NĐ 356 Điều 21–22** ⚠️ | **Bên cung cấp dịch vụ xử lý dữ liệu phải là PHÁP NHÂN VIỆT NAM + có chứng nhận dịch vụ xử lý dữ liệu của Bộ Công an** | **Ràng buộc cấu trúc lớn nhất** — ảnh hưởng pháp nhân vận hành, không chỉ kỹ thuật. [cần primary-text] |
| Luật Điều 20 | Chuyển dữ liệu xuyên biên giới gồm **xử lý/lưu trên cloud nước ngoài** | → hosting trong VN + zero-retention |
| Luật Điều 20(2) | **Hồ sơ TIA** nộp Bộ Công an trong **60 ngày** kể từ lần chuyển đầu | quy trình tuân thủ W6 |
| Luật Điều 20(6) | Miễn TIA cho **dữ liệu nhân viên** trên cloud — **KHÔNG** gồm dữ liệu khách hàng | → dữ liệu khách của SaaS *không* được miễn |
| NĐ 356 Điều 29 | Báo vi phạm Bộ Công an + chủ thể trong **72h** (sự cố vị trí/sinh trắc); lưu hồ sơ ≥5 năm | logging/audit W5 |
| Chế tài | tới **3 tỷ đồng** / **5% doanh thu** (vi phạm xuyên biên giới) / hình sự | — |

*(NĐ chế tài ấn định mức phạt cụ thể vẫn đang dự thảo, chưa xác nhận.)*

---

## 2. Trí tuệ nhân tạo (ảnh hưởng W6 Platform, định vị sản phẩm)

- **Luật AI số 134/2025/QH15** — thông qua 10/12/2025, **hiệu lực 1/3/2026**. Điều chỉnh theo **vai** (developer/provider/deployer/user) **VÀ theo tầng rủi ro** (cao/trung/thấp).
- **Luật Công nghiệp CNS 71/2025/QH15** — hiệu lực 1/1/2026; **Điều 44** gắn nhãn AI (thông báo đang tương tác với AI + sản phẩm trong Danh mục của Bộ KH&CN phải có dấu nhận diện máy/người đọc được).

**🔴 Phát hiện quan trọng nhất cho định vị sản phẩm:**
> **AI hỗ trợ tố tụng (litigation) được liệt kê rõ là HỆ THỐNG RỦI RO CAO** trong **Quyết định 33/2026/QĐ-TTg** (hiệu lực 15/8/2026). → **Judgment Analysis** ("bản án vào → đúng/sai") của TraLuat nhiều khả năng rơi vào **tầng rủi ro cao**: phải đánh giá hợp chuẩn, lập hồ sơ, **logging**, **giám sát của con người**, **đăng ký trên cổng**, và nhà cung cấp nước ngoài cần **đầu mối liên hệ tại VN**. [cần primary-text]

- **Nhãn AI**: provider phải công bố tương tác AI + gắn thẻ nội dung sinh (định dạng máy-đọc theo **NĐ 142/2026/NĐ-CP**, hiệu lực 1/5/2026). → thiết kế nhãn ở LLM Gateway/API (W3/W5).
- **Grace period**: 18 tháng (tài chính/y tế/giáo dục), 12 tháng (ngành khác).
- ⚠️ **Chưa giải quyết [cần primary-text]:** Luật AI 134 có **bãi bỏ** phần AI của Luật 71/2025 hay *song song*? Nguồn mâu thuẫn — phải đọc điều khoản chuyển tiếp/bãi bỏ của Luật 134.

**Hệ quả định vị:** càng củng cố định vị **second-opinion, human-in-the-loop** (không "xử thay") — vừa đúng đạo đức, vừa giảm gánh tuân thủ tầng rủi ro cao.

---

## 3. Án lệ (ảnh hưởng W2 KG, Judgment Analysis)

- **Chuỗi văn bản (ĐÃ xác minh):** NQ **03/2015** (hiệu lực 16/12/2015) → NQ **04/2019/NQ-HĐTP** (hiệu lực 15/7/2019) → **sửa đổi** (không thay thế) bởi NQ **02/2025/NQ-HĐTP** (hiệu lực 1/7/2025). Hợp nhất: **VBHN 11/VBHN-TANDTC**.
- ✅ Xác nhận: **"NQ 04/2025" KHÔNG điều chỉnh án lệ** (đó là văn bản hình sự, không liên quan).
- **Nghĩa vụ "áp dụng-hoặc-giải-thích" = Điều 8 NQ 04/2019** (doctrinal hook cho "bản án đúng/sai"). [verbatim cần trích từ VBHN 11]
- **SỐ LƯỢNG ÁN LỆ = 90** (đọc *trực tiếp* từ anle.toaan.gov.vn — mới nhất **Án lệ 90/2026/AL**). Giải quyết mâu thuẫn "82 vs 90": 82 = cuối 2025; 90 = sau QĐ 162/QĐ-CA (29/5/2026, áp dụng 1/7/2026). → *KB án lệ nhỏ, tuyển chọn → đúng như thiết kế: curated-KB + matching.*
- 🔧 **Ghi chú kỹ thuật ingestion:** `anle.toaan.gov.vn` có **chuỗi chứng chỉ TLS không đầy đủ** → trình duyệt/WebFetch từ chối; phải xử lý ở tầng nạp (W1).
- ✅ **GỠ BLOCKER:** án lệ **VÀ toàn bộ bản án thường** đã nằm sẵn trong raw data được phép dùng → *không cần* thỏa thuận TANDTC riêng; nạp qua pipeline W1 như mọi văn bản. → **Judgment Analysis có kho bản án đầy đủ** để `LinkingService` học/match (inductive kiểu LeSICiN) + neo án lệ. Lưu ý: bản án phải tôn trọng **chế độ ẩn danh NQ 03/2017** (kiểm trạng thái ẩn danh ở W1 stage [1]).

---

## 4. Quyền dùng nguồn dữ liệu (ảnh hưởng W1 Data)

- **vbpl.vn** (CSDL quốc gia) — theo **NĐ 52/2015/NĐ-CP** (hiệu lực 20/7/2015), **Điều 12: khai thác miễn phí**. ⚠️ **[cần xác nhận]** có dự thảo NĐ *thay thế* NĐ 52 đang lấy ý kiến 2025 — kiểm bản kế nhiệm đã hiệu lực chưa.
- **congbobanan.toaan.gov.vn** — theo **NQ 03/2017/NQ-HĐTP** (hiệu lực 1/7/2017): đăng trong 30 ngày, có loại trừ (xử kín, người chưa thành niên, bí mật NN/nghề nghiệp), **bắt buộc ẩn danh**.
- **Cơ sở tái sử dụng = BẢN QUYỀN, không phải các NĐ trên:** theo Luật SHTT, **văn bản QPPL/hành chính + bản dịch chính thức KHÔNG thuộc bảo hộ quyền tác giả** → text luật/bản án tự do tái dùng. ⚠️ **[cần primary-text: Điều 15 Luật SHTT]** — đây là căn cứ *chịu lực*, phải xác minh. Tái dùng bản án phải tôn trọng chế độ ẩn danh của NQ 03/2017.
- Tuyệt đối không cào aggregator (thuvienphapluat/luatvietnam/lawnet — có ToS riêng).

---

## 5. Việc cần làm tiếp (primary-text, ưu tiên)
1. **NĐ 356 Điều 21–22** — yêu cầu pháp nhân VN + chứng nhận BCA (ảnh hưởng *cấu trúc công ty*).
2. **Điều khoản bãi bỏ của Luật AI 134** — quan hệ với Luật 71/2025.
3. **QĐ 33/2026** — xác nhận litigation AI = rủi ro cao + nghĩa vụ kèm theo.
4. **Điều 15 Luật SHTT** — căn cứ miễn bản quyền cho văn bản pháp luật.
5. **Tình trạng hiệu lực NĐ 52/2015** (có bản thay thế chưa).
6. **Điều 8 VBHN 11/VBHN-TANDTC** — verbatim nghĩa vụ áp-dụng-hoặc-giải-thích.
