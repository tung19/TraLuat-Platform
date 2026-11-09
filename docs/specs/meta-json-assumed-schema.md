# TraLuat — Schema `meta.json` GIẢ ĐỊNH (chờ meta thật)

> ⚠️ **GIẢ ĐỊNH** — tổng hợp từ metadata các repo đã audit (Indigo FRBR `works.py:503-538` · eyecite citation groups · canonical w2). **Thay bằng meta thật khi có.** Mục đích: W1 code được ngay, không chờ.
> Khớp: `specs/w1-data-pipeline.md` (điền vào "meta.json intake contract placeholder"), `specs/w2-knowledge-graph.md`, `specs/data-and-metadata-model.md`.

---

## 1. Giả định cấu trúc raw data
Theo mô tả: *"meta.json + PDF cho mỗi điều luật / bộ ban ngành"*. Giả định một **document = 1 văn bản** có `meta.json` mô tả + (các) PDF; nếu tách tới cấp điều thì có mảng `units`.

```
raw/
  <co_quan>/<doc_number>/
    meta.json
    full.pdf            (hoặc)
    dieu-1.pdf dieu-2.pdf ...
```

## 2. `meta.json` — văn bản QPPL (giả định)
```json
{
  "doc_number": "99/2020/NĐ-CP",
  "doc_type": "nghi_dinh",                 // luat|bo_luat|nghi_dinh|thong_tu|quyet_dinh|nghi_quyet|cong_van...
  "title_vi": "Nghị định ... ",
  "title_en": null,
  "issuing_authority": "Chính phủ",         // → authority (cần map rank_level)
  "authority_rank": 80,                      // giả định; nếu meta thiếu → tra bảng thẩm quyền
  "jurisdiction": "VN",
  "field": ["dau_tu"],                       // lĩnh vực: dau_tu|lao_dong|thue|...
  "date_issued": "2020-08-20",
  "date_effective": "2021-01-01",            // ★ NGÀY HIỆU LỰC (bắt buộc cho moat #1)
  "date_expired": null,
  "gazette_ref": "Công báo số ...",
  "status": "con_hieu_luc",                  // con_hieu_luc|het_hieu_luc|het_mot_phan
  "relations": [                             // ★ quan hệ sửa đổi/bãi bỏ (nếu meta có sẵn → đỡ phải trích)
    {"type": "amends",  "target_doc": "80/2015/NĐ-CP", "target_unit": "dieu-5", "effective_date": "2021-01-01"},
    {"type": "repealed_by", "source_doc": "80/2025/NĐ-CP", "effective_date": "2025-10-01"}
  ],
  "language": "vi",
  "source_uri": "vbpl.vn/...",
  "source_hash": "sha256:...",               // nếu thiếu → W1 tự tính
  "units": [                                 // (tuỳ chọn) nếu đã tách cấp điều
    {"eid": "nd99__dieu_3", "unit_type": "dieu", "ordinal": 3, "label": "Điều 3",
     "pdf": "dieu-3.pdf", "children": [
       {"eid": "nd99__dieu_3__khoan_1", "unit_type": "khoan", "ordinal": 1, "label": "1"},
       {"eid": "nd99__dieu_3__khoan_2", "unit_type": "khoan", "ordinal": 2, "label": "2"}
     ]}
  ]
}
```

## 3. Biến thể — án lệ (giả định)
```json
{
  "doc_type": "an_le",
  "number": "90/2026/AL",
  "name": "Án lệ số 90/2026/AL về ...",
  "source_judgment": "Bản án số .../...",
  "situation": "Tình huống án lệ: ...",       // → precedent.situation
  "solution": "Giải pháp pháp lý: ...",        // → precedent.solution
  "interpreted_units": ["blds-2015__dieu_468"],// điều luật diễn giải
  "date_adopted": "2026-05-29",
  "date_effective": "2026-07-01",
  "date_annulled": null
}
```

## 4. Biến thể — bản án (giả định)
```json
{
  "doc_type": "ban_an",
  "case_no": ".../2024/...",
  "court": "TAND ...",
  "date": "2024-03-15",
  "matter_type": "dan_su",
  "anonymization_status": "anonymized",        // ★ NQ 03/2017 — kiểm trước khi nạp
  "facts": "...",
  "holdings": "...",
  "cited_units": ["blds-2015__dieu_468"],       // viện dẫn điều luật
  "cited_precedents": ["08/2016/AL"],           // viện dẫn án lệ
  "outcome_label": "A_WIN"                       // schema ALQAC (A_WIN|PARTIAL_A|PARTIAL_B|B_WIN)
}
```

## 5. Mapping meta.json → schema canonical
| meta.json | → canonical (w2) |
|---|---|
| doc_number, doc_type, title_*, dates, gazette, status | `document` |
| issuing_authority, authority_rank | `authority` (+ rank_level) |
| units[].{eid, unit_type, ordinal, label, children} | `unit` (cây) |
| (text PDF sau OCR) + date_effective | `unit_version` (valid_from=date_effective) |
| relations[] | `norm_relation` (type, effective_date) → W2 materialize version |
| án lệ {situation, solution, interpreted_units, date_annulled} | `precedent` |
| bản án {case_no, facts, cited_units, outcome_label} | `judgment` |
| language | `unit_version.lang` / `concept/term` |

## 6. Hai nhánh xử lý (theo độ giàu của meta thật)
- **Nhánh A — meta GIÀU** (có `date_effective`, `relations`, `units` cấp điều): W1 **map thẳng**, bỏ qua phần trích cấu trúc/quan hệ → nhanh, chắc.
- **Nhánh B — meta NGHÈO** (chỉ số hiệu + tiêu đề + PDF): W1 chạy đủ pipeline — OCR → parse cấu trúc (Bluebell-style) → trích `date_effective` + `relations` (traluat-cite). Chậm hơn, cần HITL nhiều hơn.

## 7. Checklist khi meta THẬT về (validate giả định)
- [ ] Có `date_effective` cấp văn bản/điều không? (quyết định moat #1 chạy trực tiếp hay phải trích)
- [ ] Có `relations` (sửa đổi/bãi bỏ) sẵn không, hay phải trích từ text?
- [ ] Tách tới cấp điều/khoản chưa (có `units`)? PDF theo điều hay cả văn bản?
- [ ] Án lệ có giữ cấu trúc tình huống/giải pháp/điều diễn giải không?
- [ ] Bản án đã ẩn danh (NQ 03/2017) + có `cited_units/cited_precedents` không?
- [ ] Tỉ lệ PDF scan vs text?
→ Trả lời xong, tôi chốt W1 trúng và cập nhật doc này thành schema thật.
