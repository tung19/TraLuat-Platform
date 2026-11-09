# TraLuat — Handoff: Data cleaning phải xuất gì cho W1

> Cho **đội làm sạch dữ liệu**. Đây là *hợp đồng output*: clean xong phải ra đúng các trường dưới để W1 nạp thẳng, **không phải làm lại**. Mỗi văn bản = 1 `meta.json` + (các) file text/PDF.
> Chuẩn chi tiết: `docs/specs/meta-json-assumed-schema.md`. Vì sao quan trọng: `docs/specs/w1-data-pipeline.md`.

---

## 0. Việc #1 ngay bây giờ
**Xuất 20–50 bản `meta.json` MẪU rồi gửi lại** → chốt mapping W1 trên dữ liệu thật. Đừng clean hết rồi mới đưa.
- **★ Mẫu PHẢI gồm ca KHÓ (không chỉ ca sạch dễ):** 1 văn bản **PDF scan xấu**, 1 **văn bản hợp nhất**, 1 bản **có văn bản sửa đổi nó**, 1 văn bản **hiệu lực theo từng phần** (các Điều khác ngày), 1 **án lệ**, 1 **bản án**. *Mẫu toàn ca dễ thì validate vô nghĩa.*

> 🔴 **Audit đã sửa 6 chỗ (đọc kỹ):** **(A)** hiệu lực có thể theo TỪNG ĐIỀU — không ép một ngày cấp văn bản (§1b); **(B)** `date_effective` phải kèm **câu nguồn + vị trí** (đội clean không phải luật sư); **(C)** mẫu gồm ca khó (trên); **(D)** ẩn danh theo **nguồn** + W1 có backstop, không bắt đội clean tự phán (§4); **(E)** quan hệ sửa đổi lấy ngày từ **văn bản sửa đổi** (§3); **(F)** thêm `jurisdiction`, chuẩn hoá **NFC**, phân biệt *hiệu lực vs áp dụng*, `scope`.

> ✅ **TỰ KIỂM (bắt buộc trước khi gửi):** mỗi `meta.json` phải PASS schema máy-đọc — `schemas/meta.schema.json`:
> ```
> python scripts/validate_meta.py <thư_mục_hoặc_file>.json
> ```
> Mẫu PASS tham chiếu: `sample_data/nd-99-2020.json`. File fail sẽ in rõ trường sai. W1 dùng *chính* schema này để gác lúc nạp.

---

## 1. Trường BẮT BUỘC cho mỗi văn bản (VBQPPL)
| Trường | Vì sao cần | Bắt buộc | Nếu nguồn thiếu |
|---|---|---|---|
| `doc_number` (vd `99/2020/NĐ-CP`) | định danh | ✅ | ghi `null`, W1 trích |
| `doc_type` (luat/nghi_dinh/thong_tu/quyet_dinh/nghi_quyet/cong_van/an_le/ban_an) | thứ bậc + routing | ✅ | — |
| `title_vi` | hiển thị/định danh | ✅ | — |
| `issuing_authority` | thẩm quyền (giải xung đột) | ✅ | ghi `null` |
| `date_issued` | mốc | ✅ | — |
| **`date_effective` + `date_effective_source`** | **moat #1 — thiếu là hỏng cả hệ** | ✅✅ | `needs_review`; **LƯU câu nguồn+vị trí** (§1b), KHÔNG đoán |
| `date_applicable` (ngày áp dụng, nếu khác hiệu lực) | hiệu lực ≠ áp dụng | ⬜ | — |
| `jurisdiction` (mặc định `VN`) · `scope` (quoc_gia/tinh) | portable + giải xung đột | ⬜ | mặc định VN / quoc_gia |
| `date_expired` / `status` | còn/hết hiệu lực | ⬜ | suy từ quan hệ |
| `source_uri` + `source_hash` | truy nguồn, chống trùng | ✅ | W1 tự tính hash nếu thiếu |
| `language` | song ngữ | ✅ | mặc định `vi` |

### 1b. Ngày hiệu lực — các ca đặc biệt (★ sửa A/B)
- **Hiệu lực theo TỪNG PHẦN (phased commencement):** nếu các Điều hiệu lực khác ngày → ghi hiệu lực ở **cấp `unit`** (`unit.effective_date`), **KHÔNG** nhét một ngày cấp văn bản. Không rõ → `needs_review`.
- **Provenance (B):** luôn lưu `date_effective_source` = **câu nguồn + vị trí** đã lấy ngày (vd "Nghị định này có hiệu lực thi hành từ ngày…", thường ở Điều cuối) → W1/pháp chế verify. Đội clean không phải luật sư — chỉ *trích + chỉ chỗ*, không *phán*.
- **Hiệu lực vs áp dụng:** "có hiệu lực từ" (`date_effective`) ≠ "áp dụng cho/từ" (`date_applicable`) — đừng gộp.
- **Chuyển tiếp:** giữ **nguyên văn** điều khoản chuyển tiếp; KHÔNG xoá (W2 cần để dựng lại).

## 2. Cấu trúc & nội dung
- **Tốt nhất:** tách tới **Điều/Khoản/Điểm** (mảng `units[]` có `unit_type`, `ordinal`, `label`, `text`, cây cha-con). → W1 map thẳng (Nhánh A, nhanh+chắc).
- **Tối thiểu:** giữ **text sạch, đúng thứ tự, có đánh dấu tiêu đề Điều/Khoản** để W1 parse (Nhánh B).
- **PDF:** giữ bản gốc + ghi `is_scanned` + `ocr_conf` nếu đã OCR. **Giữ độ tin OCR**, đừng vứt.
- **★ (F) Chuẩn hoá Unicode NFC** cho mọi text tiếng Việt (dấu) — nhất quán để neo trích dẫn/khớp sau này; đừng trộn NFC/NFD.

## 3. Quan hệ sửa đổi/bãi bỏ (nếu nguồn có)
- Nếu văn bản/metadata nói "sửa đổi/bổ sung/bãi bỏ/thay thế/hướng dẫn văn bản X" → ghi vào `relations[]` (`type`, `target_doc`, `target_unit?`, `effective_date`).
- **★ (E) `relations.effective_date` lấy từ văn bản SỬA ĐỔI (văn bản hiện tại), KHÔNG phải văn bản bị sửa.** Ghi quan hệ từ phía văn bản *đang* sửa đổi/bãi bỏ cái khác (nó biết ngày hiệu lực của chính nó). Khi clean *văn bản bị sửa*, thường KHÔNG biết ngày này → **để trống, chỉ giữ câu gốc**, W1 nối sau.
- Không chắc → **giữ nguyên câu chữ gốc** trong text (W1 sẽ trích); **đừng xoá/viết lại** câu "được sửa đổi/bãi bỏ bởi…".

## 4. Theo loại — lưu ý riêng
- **Án lệ:** giữ cấu trúc **tình huống án lệ / giải pháp pháp lý / điều luật diễn giải** + số án lệ (`.../AL`) + ngày.
- **🔴 Bản án — ẩn danh (★ D, theo NGUỒN, không bắt đội clean tự phán):**
  - Ghi `anonymization_source`: nếu lấy từ **congbobanan.toaan.gov.vn** → toà đã ẩn danh ở nguồn → `source_anonymized` (tin).
  - Nguồn **khác / không rõ** → `anonymization_status = unverified` → **quarantine, KHÔNG nạp**, báo lại.
  - Đội clean **không cần tự quyết "đã ẩn danh đủ chưa"** (việc pháp lý nặng); chỉ ghi *nguồn* + *trạng thái*. **W1 có PII backstop** quét lần nữa (phòng thủ nhiều lớp).
- **Văn bản hợp nhất:** **ĐỪNG** trộn thành "bản gốc" — đánh dấu `is_consolidated: true` (nếu nhập nhầm, sẽ xoá mất lịch sử sửa đổi mà hệ cần dựng lại).

## 5. KHÔNG được làm (gây hỏng/rework)
- ❌ Bỏ/đoán bừa `date_effective`.
- ❌ Viết lại/tóm tắt nội dung điều luật (phải **nguyên văn**).
- ❌ Xoá câu "được sửa đổi/bãi bỏ bởi…".
- ❌ Đưa bản án **chưa ẩn danh**.
- ❌ Lấy dữ liệu từ **aggregator** (thuvienphapluat/luatvietnam/lawnet — vi phạm ToS); chỉ dùng **nguồn được phép** (vbpl.vn/Công báo/cổng TANDTC).
- ❌ Gộp văn bản hợp nhất thành bản gốc.

## 6. Mẫu `meta.json` (VBQPPL có sửa đổi)
```json
{
  "doc_number": "99/2020/NĐ-CP",
  "doc_type": "nghi_dinh",
  "title_vi": "Nghị định ...",
  "issuing_authority": "Chính phủ",
  "date_issued": "2020-08-20",
  "date_effective": "2021-01-01",
  "status": "con_hieu_luc",
  "language": "vi",
  "source_uri": "https://vbpl.vn/...",
  "source_hash": "sha256:...",
  "is_scanned": false,
  "relations": [
    {"type": "amends", "target_doc": "80/2015/NĐ-CP", "target_unit": "dieu-5", "effective_date": "2021-01-01"}
  ],
  "units": [
    {"unit_type": "dieu", "ordinal": 3, "label": "Điều 3", "children": [
      {"unit_type": "khoan", "ordinal": 2, "label": "2", "text": "Mức vốn pháp định tối thiểu là 20 tỷ đồng."}
    ]}
  ]
}
```

## 7. Checklist tự kiểm trước khi bàn giao mỗi batch
- [ ] Mọi văn bản có `date_effective` (hoặc `needs_review` nếu thật sự không có).
- [ ] Text nguyên văn, đúng thứ tự, không tóm tắt.
- [ ] Bản án: đã ẩn danh + `anonymization_status`.
- [ ] Không có nguồn aggregator; `source_uri` trỏ nguồn được phép.
- [ ] Giữ câu "sửa đổi/bãi bỏ bởi…"; `relations[]` điền nếu có.
- [ ] Văn bản hợp nhất đánh dấu `is_consolidated`.
- [ ] (OCR) giữ `is_scanned`/`ocr_conf`; tính `source_hash`.

## 8. Cách chạy validator + cách bàn giao

**Chạy validator (tự kiểm trước khi gửi):**
```
# cần Python 3.9+ ; cài 1 lần:
pip install -r requirements-data.txt      # chỉ gồm: jsonschema
# kiểm 1 file hoặc cả thư mục:
python scripts/validate_meta.py duong_dan/toi/meta_cua_ban/
```
Mọi file phải `✓ PASS` mới gửi. File fail in rõ trường sai.

**Quy ước bàn giao:**
- **Mã hoá:** UTF-8, **chuẩn hoá NFC** (dấu tiếng Việt nhất quán).
- **Đặt tên + layout:** mỗi văn bản một `meta.json` + (các) PDF cùng chỗ:
  `raw/<co_quan>/<doc_number>/meta.json` · `.../full.pdf` (hoặc `dieu-3.pdf`…).
- **Batch:** gửi theo lô (vd theo bộ ngành / theo đợt), kèm một `manifest.csv` (doc_number, doc_type, có date_effective?, is_scanned?) để tiện đối chiếu.
- **Kênh giao:** thống nhất với team kỹ thuật (git-LFS / Drive nội bộ / NAS). ⚠️ **Dữ liệu trong VN** — bản án/dữ liệu nhạy cảm không đẩy ra dịch vụ ngoài nước.
- **Nguồn:** chỉ **vbpl.vn / Công báo / cổng TANDTC** — không aggregator (đã nêu §5).

**Vòng lặp:** gửi **20–50 mẫu (gồm ca khó)** trước → team kỹ thuật đối chiếu + chốt schema (có thể bump version) → mới làm đại trà.

> 🔒 **Validator SIẾT thêm (bản vá chaos-validation):**
> - **Bản án:** `anonymization_status` **KHÔNG được null**; để INGEST phải là `source_anonymized` hoặc `verified` (+ `anonymization_source` có giá trị). `unverified` → **FAIL = quarantine, không nạp** (đúng chủ trương §4).
> - **Ngày:** phải là **ngày lịch THẬT** (không chỉ đúng hình dạng) + năm trong `[1945..nay+5]` → chặn OCR lật `2071-13-45`, `2021-99-99`.
> - **NFC:** mọi chuỗi phải chuẩn hoá **NFC** (dấu tiếng Việt) — validator báo nếu lẫn NFD.

---

> Một câu: **clean = chuẩn hoá về đúng các trường trên (nhất là `date_effective`, nguyên văn điều–khoản, quan hệ sửa đổi, ẩn danh bản án) — không diễn giải, không bỏ sót, không aggregator.** Gửi 20–50 mẫu trước để chốt.
