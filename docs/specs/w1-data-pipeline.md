# W1 — Data pipeline (L1 Acquisition + L2 Ingestion) — Đặc tả triển khai

> Module brief chi tiết cho member nhận mảng **W1 / L1–L2**. Biến `meta.json` + PDF (mỗi điều luật / bộ ngành) → schema canonical (`document / unit / unit_version / norm_relation`), kèm trích quan hệ sửa đổi/bãi bỏ để feed W2.
> Nguồn pattern (đã đọc code, xác nhận bằng path+dòng): **Bluebell** (cấu trúc hoá + eId ổn định), **eyecite** (pipeline trích dẫn 4 giai đoạn + tách data↔engine), **cobalt** (FRBR URI). Đọc kèm `docs/implementation-architecture.md §W1`, `docs/specs/w2-knowledge-graph.md §7` (hợp đồng W1→W2), `research_notes/Repo deep read/{eyecite,indigo}.md`.
> Nguyên tắc vàng: W1 **không** phát minh chân lý — W1 chuẩn hoá nguồn thành record idempotent, có provenance, có version schema, để W2 là nguồn-sự-thật bitemporal. Mọi stage phát JSON, chạy lại được, không phá offset gốc.

---

## 0. Module này giao ra cái gì (deliverables)

1. **Pipeline 8 stage** điều phối bằng **Temporal** (mỗi stage một activity idempotent, có provenance + hash), chạy được trên dữ liệu mẫu trước khi có 4TB.
2. **Bộ record canonical** nạp cho W2: `document`, `unit[]`, `unit_version[]` (bản gốc), `norm_relation[]` (quan hệ sửa đổi/bãi bỏ/dẫn chiếu trích từ văn bản) — đúng schema W2 §2.
3. **`vn-legal-db`** — package dữ liệu trích dẫn tiếng Việt (loại VB, cơ quan/ký hiệu, biến regex), **tách rời** engine `traluat-cite` (dựng theo mô hình data↔engine của eyecite).
4. **`traluat-cite`** — engine trích dẫn 4 giai đoạn `clean → find → resolve → annotate` + pass trích quan hệ sửa đổi/bãi bỏ, giữ offset gốc bằng cơ chế kiểu `SpanUpdater`.
5. **Báo cáo đo tỉ lệ scan (OCR ratio)** của corpus + ngưỡng định tuyến OCR.
6. **"meta.json intake contract"** — danh sách field W1 cần từ `meta.json` (placeholder, chốt ở tuần 1).

**Nguyên tắc:** nếu `meta.json` đã có cấp Điều/Khoản → **map thẳng**, không parse lại; Bluebell chỉ dùng cho (a) PDF/text chưa cấu trúc, hoặc (b) kiểm tra chéo cây đơn vị. eId sinh ra là **khoá ổn định** để amendment trỏ vào — không trỏ id tự tăng.

> 🔴 **Audit fixes Critical ĐÃ ÁP** (chi tiết `docs/specs/spec-audit-fixes.md` W1; dấu ★ dưới): **(C1)** quan hệ trích ra mặc định `needs_review` — W2 **chỉ materialize khi `approved`**; **(C2)** `confidence` phải có công thức định nghĩa, **không bịa** (eyecite không có model confidence); **(C3)** **cổng ẩn danh bản án ở Stage 1** (NQ 03/2017). "W1 không phát minh chân lý" được *ép bằng cổng*, không chỉ là khẩu hiệu.

---

## 1. Hệ định danh & eId — chốt trước khi code

Trùng hệ URN của W2 (`docs/specs/w2-knowledge-graph.md §1`):
```
Work:     trl:<jur>/<doc_type>/<doc_number_slug>
Unit:     <work>/<unit_path>              vd .../dieu-3/khoan-2/diem-a
Version:  <unit>@<YYYY-MM-DD>/<lang>
```
- **FRBR URI** (canonical ID): port `refs/cobalt/cobalt/uri.py::FrbrUri.parse` (regex `FRBR_URI_RE`, `uri.py:3-20`; pure Python, không Django). Vietnam mapping vd: `/akn/vn/act/luat/2015/91/vie@2021-01-01/!main~dieu_1`.
- **eId ổn định** (kiểu Bluebell) = cột `unit.eid` unique. Định dạng `{parent}__{alias(loại)}_{clean_num}`, vd `nd99__dieu_3__khoan_2`. Xem §3 về cơ chế sinh.

---

## 2. meta.json intake contract (PLACEHOLDER — chốt tuần 1)

> 📌 **Luồng intake thứ 2 (FR-34 — đơn mẫu):** ngoài VBQPPL/bản án qua `meta.json`, có **kho template đơn từ** (khởi kiện/khiếu nại/tố giác) do **data-eng** đổ vào **lakehouse** (curated + ẩn danh). Luồng này **KHÔNG đi qua `meta.json`/stage 1–8** — nó đi đường riêng: lakehouse → **trigger (CDC/scheduled)** → `adapters/lakehouse_template.py` → **TemplateExemplarStore** (xem `integration-adapters §8b`, dùng ở W6 §1.2b). W1 chỉ cần biết để không trộn 2 luồng; không materialize template trong W1.

> **Schema `meta.json` thật CHƯA có.** Đây là hợp đồng W1 *cần* từ meta.json; member dán schema thật rồi map 1-1 vào cột canonical. Field nào thiếu ở nguồn → W1 tự trích (stage 2/4/5); field nào có sẵn → bỏ qua stage tương ứng.

**W1 cần đọc được từ mỗi bản ghi `meta.json` (mức văn bản):**

| Field cần | Map vào | Bắt buộc | Nếu thiếu → W1 trích ở |
|---|---|---|---|
| số hiệu văn bản (vd `91/2015/QH13`) | `document.doc_number` | ✅ | stage 4 (regex ký hiệu) |
| loại văn bản (Luật/Nghị định/Thông tư…) | `document.doc_type` | ✅ | stage 4 |
| cơ quan ban hành | `document.authority_id` (qua registry) | ✅ | stage 4 (ký hiệu suffix) |
| tiêu đề | `document.title_vi` | ✅ | — |
| ngày ban hành | `document.date_issued` | ✅ | stage 4 |
| **ngày hiệu lực** | `document.date_effective` | ✅ (moat) | stage 4 (câu "có hiệu lực từ…") |
| ngày hết hiệu lực / bị bãi bỏ | `document.date_expired` | ⬜ | stage 5 (quan hệ repeals) |
| trạng thái (còn/hết hiệu lực) | `document.status` | ⬜ | suy từ stage 5 |
| đường dẫn file PDF (list) | provenance stage 1 | ✅ | — |
| nguồn (URL vbpl.vn / cơ quan) | `document.source_uri` | ⬜ | — |
| **cây cấu trúc Điều/Khoản/Điểm** (nếu có) | `unit[]` thẳng | ⬜ | stage 3 (Bluebell parse) |
| text từng Điều/Khoản (nếu có) | `unit_version.text` | ⬜ | stage 2 (OCR/parse PDF) |
| văn bản liên quan (sửa đổi/thay thế/hướng dẫn gì) | `norm_relation[]` gợi ý | ⬜ | stage 5 (trích từ nội dung) |
| bản hợp nhất? ngôn ngữ? | `unit_version.lang`, cờ consolidation | ⬜ | — |

**Hai nhánh xử lý theo độ giàu của meta.json:**
- **Nhánh A — meta.json GIÀU cấu trúc** (có cây Điều/Khoản + text): bỏ stage 2–3, chỉ chuẩn hoá + sinh eId + stage 4–8. *Tin tốt: phần lớn gánh nặng cấu trúc hoá đã xong ở nguồn.*
- **Nhánh B — meta.json NGHÈO** (chỉ metadata + PDF): chạy đủ 8 stage, Bluebell gánh cấu trúc hoá.

→ **Việc #1 của W1:** dán schema thật vào bảng trên, đánh dấu Nhánh A/B theo từng bộ ngành (có thể lẫn lộn giữa các nguồn).

---

## 3. Pipeline 8 stage (điều phối Temporal) — tech cụ thể + data contract

Mỗi stage = 1 Temporal activity: **idempotent** (key = `source_hash`), **có provenance** (`stage`, `schema_version`, `tool_version`, `ts`), phát JSON có `schema_version`. Retry an toàn; không stage nào mutate in-place record của stage trước.

### Stage 1 — Ingest & dedup
- **Input:** thư mục `meta.json` + PDF theo điều luật/bộ ngành.
- **Tech:** đọc meta.json; `blake3`/`sha256` nội dung từng file → `source_hash`; dedup theo hash; ghi `provenance(source_uri, ministry, ingest_ts, hash)`.
- **Output contract:**
```json
{"schema_version":"w1.ingest.v1","doc_key":"<hash>","meta":{...raw meta.json...},
 "pdf_paths":["..."],"provenance":{"ministry":"...","ingest_ts":"...","source_hash":"..."}}
```
- Idempotent: cùng `source_hash` → skip. Giữ raw meta.json nguyên văn (không mất field để truy nguyên).
- **★ Cổng ẩn danh (Critical C3 — NQ 03/2017):** nếu doc là **bản án**, kiểm trạng thái ẩn danh = meta flag **+ backstop dò PII** (tên người, địa chỉ, CMND/CCCD, số điện thoại, biển số). Chưa ẩn danh / không có bằng chứng ẩn danh → **`quarantine`, KHÔNG vào pipeline**, đẩy HITL. Mặc định *chặn*, không nạp. (Bản án không ẩn danh chạm SoR = rủi ro pháp lý.)

### Stage 2 — OCR/parse PDF (ĐO TỈ LỆ SCAN TRƯỚC — xem §4)
- **Tech:** phân loại mỗi PDF `text-native` vs `scan` bằng tỉ lệ ký tự trích được trên số trang (pdfplumber/pymupdf `get_text`); nếu scan → OCR (Tesseract `vie`, hoặc PaddleOCR/VietOCR cho chất lượng cao hơn tiếng Việt có dấu). Native → trích text trực tiếp.
- **Chỉ chạy khi:** Nhánh B, hoặc Nhánh A nhưng thiếu text ở `unit_version`.
- **Output contract:** `{"schema_version":"w1.ocr.v1","doc_key":"...","blocks":[{"page":1,"text":"...","bbox":[...],"ocr":true,"conf":0.97}],"ocr_ratio":0.0}`
- Giữ `bbox` + `conf` để truy nguyên và để stage 3 phục dựng thứ bậc.

### Stage 3 — Cấu trúc hoá (structure segmentation + eId) ★ Bluebell
- **Nhánh A:** chỉ **chuẩn hoá** cây có sẵn → map vào `unit`, sinh eId.
- **Nhánh B:** dựng **grammar kiểu Bluebell cho tiếng Việt** (xem §3.1) → text có thụt đầu dòng/keyword → cây đơn vị → eId.
- **eId:** port cơ chế `EidRewriter` của Bluebell (xem §3.2).
- **Output contract:**
```json
{"schema_version":"w1.struct.v1","doc_key":"...",
 "units":[{"eid":"dieu_3","unit_type":"dieu","ordinal":3,"label":"Điều 3","parent_eid":null},
          {"eid":"dieu_3__khoan_2","unit_type":"khoan","ordinal":2,"parent_eid":"dieu_3"}],
 "unit_text":[{"eid":"dieu_3__khoan_2","lang":"vi","text":"..."}]}
```
- Bất biến: `eid` unique trong văn bản; cây đệ quy khép kín (mọi `parent_eid` tồn tại).

#### 3.1 Grammar kiểu Bluebell cho VN (map keyword → AKN)
Bluebell dùng **thụt đầu dòng = thứ bậc** (preprocess sinh token INDENT/DEDENT) + keyword đầu dòng. Xây keyword VN map sang AKN element:

| Keyword VN | AKN (Bluebell) | unit_type | eId alias |
|---|---|---|---|
| PHẦN | `PART` | phan | part |
| CHƯƠNG | `CHAPTER` | chuong | chp |
| MỤC | `SECTION` | muc | sec |
| TIỂU MỤC | `SUBSECTION` | tieu_muc | subsec |
| ĐIỀU | `ARTICLE` | dieu | dieu* |
| KHOẢN | `PARAGRAPH` | khoan | khoan* |
| ĐIỂM | `POINT` | diem | diem* |

*(alias `dieu/khoan/diem` là alias riêng của TraLuat; Bluebell gốc dùng `art/para/point`.)*
- **VERIFIED:** `hier_element_name` của Bluebell liệt kê `ARTICLE | BOOK | CHAPTER | … | PART | PARAGRAPH | POINT | … | SECTION | SUBSECTION | …` (`refs/bluebell/crates/bluebell-core/src/grammar.pest:75-79`) + alias ngắn `ART | CHAP | PARA | SEC | SUBCHAP | SUBPARA | SUBSEC` (`grammar.pest:80`). → **CHAPTER/SECTION/ARTICLE map được sang Chương/Mục/Điều.**
- **VERIFIED:** thụt đầu dòng = thứ bậc — luật cú pháp `hier_element_block = { hier_element_name ~ block_attrs? ~ hier_element_heading? ~ eol ~ (indent ~ subheading? ~ hier_block_element* ~ dedent)? }` (`grammar.pest:64`); `indent`/`dedent` là token tổng hợp.
- **Thiết kế bền:** Bluebell bảo chứng *"luôn sinh AKN hợp lệ, không bao giờ từ chối input lỗi"* → copy tinh thần forgiving-parser (OCR tiếng Việt bẩn vẫn ra cây).

#### 3.2 Sinh eId ổn định (port `EidRewriter`)
- **VERIFIED:** sau khi parse, `rewrite_all_eids` (`refs/bluebell/crates/bluebell-core/src/xml.rs:1995`) duyệt cây bằng `EidRewriter` (`xml.rs:2213-2274`):
  - eId mỗi phần tử = `format!("{}__{}", child_prefix, …)` rồi `eid.push_str(alias(name)); … format!("{eid}_{clean_num}")` → **`{parent}__{alias}_{clean_num}`** (`xml.rs:2246,2261-2274`); `__` nối cấp, `_` nối alias với số.
  - `clean_num` (`refs/bluebell/crates/bluebell-core/src/eid.rs:5-35`): strip ký tự biên, gộp dấu câu nội bộ thành một `-`, giữ chữ/số unicode (vd `(123.4-5)`→`123-4-5`, `(2bis)`→`2bis`).
  - Numberless-but-expected → `nn`; còn lại → counter tăng dần theo (prefix, name) (`xml.rs:2267-2273`); `ensure_unique` chống trùng (`xml.rs:2274`).
  - Test khẳng định: `<section eId="chp_1__sec_1">`, `<p eId="chp_1__sec_1__p_1">`, `<item eId="list_1__item_a">` (`xml.rs:2447-2448,2531`).
- **TraLuat:** đây đúng là stage "cấu trúc hoá + ID đơn vị ổn định". eId là khoá mà `norm_relation`/commencement trỏ vào. **Khuyến nghị port bản Python reference (`bluebell/parser.py`) cho dễ nhúng** (Rust core embeddable nhưng nặng công cụ hoá); giữ đúng công thức eId để tương thích chéo.

### Stage 4 — Trích metadata (số hiệu, ngày ban hành, **ngày hiệu lực**, cơ quan)
- **Tech:** ưu tiên lấy từ meta.json; thiếu thì regex trên text (ký hiệu `…/QH..`, `…/NĐ-CP`, `…/TT-…`; "có hiệu lực (thi hành) từ ngày…", "ban hành ngày…"). Dùng `vn-legal-db` để map ký hiệu suffix → cơ quan (`authority`).
- **Output:** bổ sung các field mức `document` (§2). **Ngày hiệu lực là field moat** — nếu không có, đánh dấu `review_status=needs_review` thay vì đoán.
- **🌐 Tiền xử lý per-ngôn-ngữ (ng.tắc #14):** NER chạy trên **encoder VN (PhoBERT-family) → CẦN word-seg VnCoreNLP** trước. ⚠️ **chỉ áp cho encoder path** — bge-m3/LLM **không cần** word-seg. ZH segmenter = **defer cùng ZH**. NFC normalize mọi text (đã ở data-handoff).

### Stage 5 — Trích quan hệ sửa đổi/bãi bỏ ★ (feed `norm_relation` cho W2)
- **Tech:** chạy engine `traluat-cite` (§5) với pass phát hiện động từ quan hệ ("được sửa đổi, bổ sung bởi…", "được thay thế bởi…", "bãi bỏ…", "hướng dẫn…", "quy định chi tiết…") nối **hai trích dẫn văn bản** → cạnh có kiểu.
- **Output contract:**
```json
{"schema_version":"w1.relation.v1","relations":[
  {"relation_type":"amends","src_frbr":"trl:vn/tt/.../","dst_frbr":"trl:vn/nd/99/...",
   "src_unit_eid":"dieu_1","dst_unit_eid":"dieu_3__khoan_2",
   "effective_date":"2024-07-01","evidence_span":[1203,1271],
   "confidence":0.0,"confidence_basis":"<CÔNG THỨC phải định nghĩa>","review_status":"needs_review"}]}
```
- `relation_type ∈ {cites, amends, repeals, replaces, guides, conflicts, hierarchy}` (khớp W2 §2).
- **Quan trọng:** W1 chỉ *trích* quan hệ + `effective_date`; **W2 mới áp** qua R3/R4 để materialize version (W2 §3). W1 **không** tự dựng bitemporal.
- **★ Critical C1 — cổng materialize:** `review_status` mặc định **`needs_review`** (KHÔNG `auto`). **W2 R3/R4 chỉ áp relation khi `review_status='approved'`** (hoặc `confidence≥θ` cho tập loại *auto-safe* định nghĩa rõ, vd `cites`/`guides`; **không** auto cho `repeals`/`replaces`). Một `repeals` giả viết lại version mà cả hệ tin → **precision > recall: thà bỏ sót còn hơn sai.** Hàng chờ duyệt HITL = deliverable của W1.
- **★ Critical C2 — `confidence` KHÔNG được bịa:** traluat-cite/eyecite không có sẵn model confidence. `confidence` phải có **công thức định nghĩa + `confidence_basis`** (vd: pattern chặt/lỏng · giải được antecedent hay không · 1 vs nhiều ứng viên · meta.json xác nhận chéo). Chưa có công thức → luôn `needs_review`.
- `evidence_span` = offset trên **text gốc** (giữ qua SpanUpdater) → truy nguyên được.

### Stage 6 — Versioning bitemporal (bàn giao, KHÔNG materialize ở W1) ★
- W1 **không** sở hữu bitemporal. W1 phát `unit_version[]` **bản gốc** (`valid_from = date_effective`, `valid_to = NULL`, status) + `norm_relation[]`. W2 áp quan hệ (R3 `apply_amendment`, R4 `repeal`) để sinh version mới.
- **Lý do:** nguồn-sự-thật bitemporal là moat của W2 (W2 §3); W1 tách bạch để tránh hai nguồn ghi.
- **Output = hợp đồng W1→W2** (§6).

### Stage 7 — Căn chỉnh song ngữ (nếu có bản tiếng Anh/bản dịch)
- **Tech:** nếu nguồn có bản song ngữ → căn Điều↔Điều theo eId + thứ tự; không có → bỏ qua. Phát `unit_version` với `lang` tương ứng, cùng `unit_id`.
- **Output:** thêm dòng `unit_version(lang='en', …)` gắn cùng `unit`.

### Stage 8 — Indexing (bàn giao chunk cho W3/W4)
- **Tech:** chunk theo **đơn vị cấu trúc** (Điều/Khoản) chứ không theo ký tự thô; giữ `struct_header` (đường dẫn eId + label) để trích dẫn ngược. Embedding để W3 (bge-m3) — W1 có thể chỉ phát chunk, W3 nhúng.
- **Output contract:** `{"schema_version":"w1.chunk.v1","chunks":[{"unit_eid":"dieu_3__khoan_2","lang":"vi","text":"...","struct_header":"Điều 3 › Khoản 2"}]}`
- Khớp bảng `chunk` của W2 §2 (`unit_version_id FK, lang, text, struct_header`).

---

## 4. Đo tỉ lệ OCR (bắt buộc, làm SỚM)

Trước khi build nặng, **đo corpus** để biết gánh nặng OCR:
- **Định nghĩa:** `ocr_ratio = số_trang_scan / tổng_số_trang`. Một trang là "scan" nếu text-native trích được < `θ` ký tự/trang (mặc định `θ=50`, chốt bằng mẫu) — tức gần như không có text layer.
- **Cách đo:** stage 2 mở mỗi PDF bằng pymupdf, đếm ký tự `page.get_text()`; phân loại trang; cộng dồn theo văn bản và theo bộ ngành.
- **Báo cáo:** bảng `ministry × {native_pages, scan_pages, ocr_ratio, n_docs}` + histogram. Đây là **acceptance #4** và là đầu vào quyết định đầu tư engine OCR (Tesseract `vie` cơ bản vs VietOCR/PaddleOCR).
- **Định tuyến:** `ocr_ratio` mức văn bản ghi vào provenance; văn bản OCR nặng → `review_status` ưu tiên HITL ở stage 3–4.

---

## 5. Engine trích dẫn/sửa đổi tiếng Việt (`vn-legal-db` trên pattern eyecite)

eyecite = **pipeline regex-token điều khiển bằng dữ liệu**: engine (tokenize→find→resolve→annotate) ngôn-ngữ-độc-lập, dùng lại được; **cơ sở pattern (reporters-db/courts-db) 100% của Mỹ** → phải xây lại cho VN. Ta tách **`vn-legal-db` (data)** khỏi **`traluat-cite` (engine)** đúng mô hình đó.

### 5.1 Pipeline 4 giai đoạn (giữ nguyên shape của eyecite)
- **VERIFIED:** `refs/eyecite/eyecite/__init__.py` export **đúng 4 hàm** = 4 giai đoạn: `clean_text` (`clean.py:7`), `get_citations` (`find.py:40`), `resolve_citations` (`resolve.py`), `annotate_citations` (`annotate.py:129`). → mirror API 4 hàm.
```
text thô ──clean_text()──▶ plain_text   (VN: chuẩn hoá NFC, dọn artefact OCR, số/ký hiệu)
         ──get_citations()──▶ list[Citation]
         ──resolve_citations()──▶ dict[Resource → [citations]]
         ──annotate_citations()──▶ text có markup (offset gốc được giữ)
```

### 5.2 Tách data↔engine (lesson cốt lõi)
- **VERIFIED:** engine nạp pattern DB từ pip package ngoài: `from reporters_db import JOURNALS, LAWS, RAW_REGEX_VARIABLES, REPORTERS` (`refs/eyecite/eyecite/tokenizers.py:14`); `_populate_reporter_extractors()` biến data → `TokenExtractor` (`tokenizers.py:133-359`). Court names nạp ở **`helpers.py:8`** (`from courts_db import courts`) — xem Match check.
- **TraLuat `vn-legal-db`** (package data có version riêng) chứa:
  - Từ vựng loại VB + viết tắt: Luật, Bộ luật, Nghị định (NĐ-CP), Thông tư (TT), Thông tư liên tịch, Quyết định (QĐ), Nghị quyết (NQ), Pháp lệnh, Công văn, án lệ.
  - Cơ quan ban hành / ký hiệu suffix (-CP, -TTg, -BTC, -BCA, -NHNN, -TANDTC, -QH…) — analogue của courts-db.
  - Biến regex-template (analogue `RAW_REGEX_VARIABLES`): `$so`, `$nam`, `$dieu`, `$khoan`, `$diem`, `$loai_vb`, `$co_quan`.
- **`traluat-cite`** (engine) giữ nguyên shape eyecite: `TokenExtractor` + token có kiểu, dispatch theo kiểu token ở `find.py` (`_extract_full_citation` tại `find.py:224`), `Document` + danh sách token theo thứ tự vị trí. Khi pattern VN nhiều → thêm **prefilter Aho-Corasick** (trigger string "Điều", "Khoản", "Nghị định", "Thông tư", "án lệ số").

### 5.3 Ngữ pháp trích dẫn/sửa đổi VN (new `regexes.py`)
- **Neo thứ bậc:** `Điều X Khoản Y Điểm Z` (và đảo "điểm z khoản y Điều x"), dải ("các Điều 1 đến 5", "Khoản 1 và 2"), "Chương/Mục/Phần".
- **Tham chiếu công cụ:** `của Luật/Bộ luật … số …/QH.., Nghị định số …/NĐ-CP, Thông tư số …/TT-…, ngày…/năm…`.
- **Tên luật không số:** "Bộ luật Dân sự 2015", "Luật Đất đai".
- **Án lệ:** `án lệ số …/AL` (vd `Án lệ số 05/2016/AL`).
- **Back-reference (analogue id./supra/short):** "điều này", "khoản trên", "nêu trên", "nói trên", "cùng điều", "văn bản này" → resolve về công cụ đầy đủ gần nhất (dùng lại logic `antecedent_guess` + `last_resolution` của `resolve.py` — các resolver là tham số inject được).
- **★ Động từ quan hệ (stage 5):** "được sửa đổi, bổ sung bởi…", "được thay thế bởi…", "bãi bỏ…", "hướng dẫn…", "quy định chi tiết…" → quan hệ có kiểu giữa hai trích dẫn công cụ → feed `norm_relation`.

### 5.4 Giữ offset gốc (anchoring cấp điều–khoản)
- **VERIFIED:** `annotate.py` giữ offset bằng `class SpanUpdater` (`annotate.py:20`) diff `text_before` vs `text_after` qua `fast_diff_match_patch.diff(...)` (`annotate.py:91`), precompute step-function, `update(offset, bisect)` remap O(log n) (`annotate.py:117`); `annotate_citations` remap mỗi span từ không-gian plain → source trước khi chèn (`annotate.py:129+`).
- **TraLuat:** đây đúng cơ chế để neo trích dẫn/`evidence_span` vào **ký tự trên văn bản gốc** sau khi clean/OCR-normalize. `evidence_span` của `norm_relation` (stage 5) và anchor chunk (stage 8) đều dùng lại `SpanUpdater` gần như nguyên văn.

### 5.5 Resolver về canonical ID (bàn giao L2→W2)
- Override `resolve_full_citation` → tra registry văn bản canonical của TraLuat (Luật/NĐ/TT → FRBR URI; án lệ → AL ID), fallback clustering `Resource` mỏng kiểu eyecite khi chưa biết.

---

## 6. Interface W1 xuất ra (hợp đồng W1 → W2)

Trùng `docs/specs/w2-knowledge-graph.md §7`. W1 phát **4 loại record JSON** (có `schema_version`, idempotent, provenance):

```python
class IngestOutput(Protocol):
    def documents() -> list[DocumentRecord]: ...        # mức văn bản: frbr_uri, doc_number, doc_type,
                                                         #   authority, date_issued, date_effective, status, source_hash
    def units() -> list[UnitRecord]: ...                 # cây: eid (unique), unit_type, ordinal, label, parent_eid
    def unit_versions() -> list[UnitVersionRecord]: ...  # BẢN GỐC: unit_eid, lang, text, status, valid_to=None
                                                         #   ★ G7-fix: valid_from = unit.effective_date NẾU CÓ (phased commencement),
                                                         #     fallback document.date_effective. KHÔNG ép document-level khi điều có ngày riêng.
    def norm_relations() -> list[NormRelationRecord]: ...# src/dst frbr+eid, relation_type, effective_date,
                                                         #   evidence_span, confidence, review_status
```
- **Ranh giới rõ:** W1 cung cấp **bản gốc + quan hệ**; W2 **materialize bitemporal** (R3/R4) và sở hữu transaction-time. W1 không ghi `tx_*`.
- **Nhánh A:** nếu meta.json đã có cấp Điều/Khoản → `units()` map thẳng, W2 chỉ dựng `unit_version` + áp quan hệ (đúng câu W2 §7).
- Chunk (stage 8) xuất riêng cho W3 theo bảng `chunk` của W2 §2.

---

## 7. Acceptance tests (phải xanh)

1. **amendment end-to-end:** nạp **1 Nghị định + 1 văn bản sửa đổi nó** → W1 sinh đúng `norm_relation(relation_type='amends', effective_date=…)` nối đúng `src_unit_eid`→`dst_unit_eid`, kèm `evidence_span` trỏ đúng câu "được sửa đổi… bởi…". (Áp quan hệ để reconstruct là việc của W2 test.)
2. **metadata hiệu lực:** mỗi `document` có đủ `doc_number, doc_type, authority, date_issued, date_effective`; thiếu `date_effective` → `review_status=needs_review` (không bịa ngày).
3. **eId ổn định:** parse lại cùng văn bản 2 lần → eId **y hệt**; eId unique trong văn bản; cây `parent_eid` khép kín; khớp công thức `{parent}__{alias}_{clean_num}`.
4. **đo scan:** chạy đo OCR trên corpus mẫu → in bảng `ministry × ocr_ratio` + tổng; phân loại trang native/scan tất định với cùng `θ`.
5. **giữ offset:** sau clean/OCR-normalize, `annotate` chèn marker mà mọi `evidence_span` vẫn trỏ đúng ký tự trên text gốc (assert round-trip span).
6. **idempotent:** chạy lại pipeline với cùng `source_hash` → không tạo record trùng; output byte-ổn định (trừ timestamp provenance).
7. **trích dẫn VN:** câu "Điều 3 Khoản 2 của Nghị định số 99/2015/NĐ-CP" → 1 citation đúng eId `dieu_3__khoan_2` + đúng FRBR công cụ; back-reference "khoản này" resolve về công cụ gần nhất.
8. **★ cổng materialize (C1):** quan hệ `review_status != 'approved'` → W2 **từ chối áp** (không materialize version). Chỉ relation approved mới đổi version. *(test chéo với W2.)*
9. **★ cổng ẩn danh (C3):** fixture bản án **chưa ẩn danh** (có PII) → bị `quarantine`, KHÔNG vào SoR; bản án đã ẩn danh → qua.
10. **★ precision quan hệ:** trên tập gán nhãn, đo precision/recall `traluat-cite`; **precision của `repeals/replaces` ≥ ngưỡng cao** (đặt mục tiêu) — adversarial fixtures (dẫn chiếu lồng, "điều này" mơ hồ, trích dẫn văn bản khác).

---

## 8. Build tasks (thứ tự cho member)

1. **Tuần 1:** dán schema `meta.json` thật → điền bảng §2, đánh dấu Nhánh A/B theo bộ ngành. Chạy **đo OCR ratio** (§4) → báo cáo. ← *chốt phạm vi thật.*
2. Stage 1 (ingest/dedup/provenance) + khung Temporal activity idempotent.
3. `vn-legal-db` (data) + `traluat-cite` (engine 4 giai đoạn) — port shape eyecite, grammar VN §5.3. Test 7.
4. Stage 3 cấu trúc hoá + eId (port `EidRewriter`, công thức §3.2). Test 3. (Nhánh A: chỉ map+eId.)
5. Stage 4 metadata + Stage 5 trích quan hệ (`norm_relation`) + `SpanUpdater`. Test 1, 2, 5.
6. Stage 2 OCR (Tesseract `vie` → nâng VietOCR nếu `ocr_ratio` cao). Test 4 hoàn chỉnh.
7. Stage 7 song ngữ + Stage 8 chunk/indexing. Hợp đồng ra W2/W3.
8. Hardening: idempotent + schema_version mọi stage. Test 6.

---

## 9. Steal-list (file trong `refs/` — đã VERIFY path+dòng)

| Cần | File (đã mở xác nhận) |
|---|---|
| eId ổn định `{parent}__{alias}_{clean_num}` | `bluebell/crates/bluebell-core/src/xml.rs:1995` (`rewrite_all_eids`), `:2213-2274` (`EidRewriter`), `:2388` (`alias`); `…/eid.rs:5-35` (`clean_num`); test `xml.rs:2447-2448,2531` |
| Grammar cấu trúc hoá (indent=thứ bậc, keyword) | `bluebell/crates/bluebell-core/src/grammar.pest:64` (`hier_element_block`), `:75-80` (keyword + alias); bản Python port: `bluebell/parser.py` |
| Pipeline trích dẫn 4 giai đoạn (API) | `eyecite/eyecite/__init__.py` (4 export); `clean.py:7`, `find.py:40` + `:224`, `resolve.py`, `annotate.py:129` |
| Tách data↔engine (xây `vn-legal-db`) | `eyecite/eyecite/tokenizers.py:14` (`import reporters_db`), `:133-359` (`_populate_reporter_extractors`); court ở `helpers.py:8` |
| Giữ offset khi annotate (anchor evidence_span) | `eyecite/eyecite/annotate.py:20` (`SpanUpdater`), `:91` (`fast_diff_match_patch.diff`), `:117` (`update`), `:129` (`annotate_citations`) |
| Resolver antecedent (back-reference VN) + inject | `eyecite/eyecite/resolve.py` (`resolve_citations`, resolver inject được) |
| FRBR URI parse (canonical ID) | `cobalt/cobalt/uri.py:3-20` (`FRBR_URI_RE`), `FrbrUri.parse` (pure Python) |

---

## 10. Match check (đối chiếu với research_notes — đã mở repo xác nhận)

Đã mở trực tiếp các file repo; đối chiếu với `research_notes/Repo deep read/{eyecite,indigo}.md`:

- ✅ **Bluebell — indent=thứ bậc:** KHỚP. `grammar.pest:64` dùng `(indent ~ … ~ dedent)`; token INDENT/DEDENT tổng hợp như note mô tả.
- ✅ **Bluebell — keyword CHAPTER/SECTION/ARTICLE map Chương/Mục/Điều:** KHỚP. `grammar.pest:75-79`.
- ✅ **Bluebell — short alias (`ART/CHAP/PARA/SEC/SUBSEC…`):** KHỚP. `indigo.md:301` nói có alias ngắn — xác nhận tại `grammar.pest:80` (ban đầu dễ bỏ sót vì ở dòng tiếp theo). *Không phải sai sót của note.*
- ✅ **Bluebell — eId ổn định phân cấp `{parent}__{alias}_{clean_num}`:** KHỚP chính xác. `xml.rs:2246,2261-2274`; `clean_num` `eid.rs:5-35`; test `xml.rs:2447-2448,2531` đúng như `indigo.md:305-319`.
- ✅ **eyecite — pipeline 4 giai đoạn (clean/find/resolve/annotate):** KHỚP. `__init__.py` export đúng 4 hàm như `eyecite.md:15`.
- ✅ **eyecite — `SpanUpdater` giữ offset qua `fast_diff_match_patch`:** KHỚP. `annotate.py:20,91,117` đúng như `eyecite.md:123-135`.
- ⚠️ **eyecite — data↔engine split: "reporters_db/courts_db imported in tokenizers.py":** **CHỈNH LẠI.** Chỉ **`reporters_db`** được import ở `tokenizers.py:14`. **`courts_db` được import ở `helpers.py:8`** (`from courts_db import courts`), KHÔNG ở `tokenizers.py`. → Research note `eyecite.md:82-90` đã ghi ĐÚNG (reporters_db@tokenizers.py:14-15, courts@helpers.py:8); chỉ cách diễn đạt gộp trong đề bài là chưa chính xác. Về bản chất (data tách khỏi engine) vẫn đúng tuyệt đối.

**Kết luận:** mọi claim nền tảng của hai research note đều xác nhận được trên code thật. Khác biệt duy nhất đáng ghi là vị trí import `courts_db` (helpers.py, không phải tokenizers.py) — đã phản ánh đúng trong §5.2 và steal-list.
