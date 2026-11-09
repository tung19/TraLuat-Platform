# TraLuat — Mô hình Data & Metadata (phục vụ retrieval · reasoning · inference · eval/training)

> Audit: kiến trúc định nghĩa **loại data gì, metadata gì** để nuôi 4 chức năng AI; **repo định nghĩa field gì** (file+line); **ta bổ sung gì**.
> Nguồn: `research_notes/Repo deep read/metadata_retrieval_eval.md` + `metadata_reasoning.md` (đã verify). Đọc kèm `specs/w2-knowledge-graph.md`, `specs/w3-ai-retrieval-grounding.md`.

---

## 1. LOẠI DATA (data types)
| Data | Mô tả | Nguồn |
|---|---|---|
| VBQPPL | Luật/NĐ/TT + điều/khoản/điểm | raw data (được phép) |
| Án lệ | tình huống + giải pháp + điều diễn giải | raw data |
| Bản án | tình tiết + phán quyết + viện dẫn | raw data (đủ, đã ẩn danh) |
| Hợp đồng khách | tài liệu tenant (upload) | khách (cô lập) |
| Concept/Term | khái niệm ↔ thuật ngữ vi/en | tự dựng (moat #3) |
| Gold/Label set | nhãn để train/eval trọng số | HITL flywheel |

---

## 2. LOẠI METADATA — phân theo mục đích, so với repo

### 2.1 Định danh & cấu trúc (identity/structure)
- **TraLuat:** `frbr_uri`, `eid` ổn định, `unit_type`, `ordinal`, `path`, `struct_header`.
- **Repo:** Indigo giàu nhất (`frbr_uri`, doctype/subtype, number/date — `works.py:503-517`); Bluebell eId; eyecite `groups{volume,reporter,page,section,title}`; PAKTON chỉ `{in_document_index, parent_index, document_id}` (`structuralParser.py:326`).

### 2.2 Hiệu lực-thời-gian (temporal/effectivity) ★ moat
- **TraLuat:** `valid_from/valid_to` + **`tx_from/tx_to` (bitemporal 2 trục)** + `norm_relation.effective_date`.
- **Repo:** **CHỈ Indigo có hiệu lực thật** (`commenced`, `repealed_by/date/verb` ×8 verbs, `expression_date` — `works.py:528-538`, `documents.py:373`) nhưng **1 trục (valid-time)**. L-MARS có *phán đoán* `temporally_invalid` nhưng **không lưu ngày**. LegalGraphRAG single-snapshot (hard-delete điều ≤101). → **ta lấy template Indigo + thêm trục transaction-time.**

### 2.3 Thẩm quyền & jurisdiction
- **TraLuat:** `jurisdiction`, `authority.rank_level` (lex superior), `doc_type`, `lang`.
- **Repo:** chỉ Indigo (country/locality/doctype/subtype/language ISO-639-2); eyecite chỉ `court`; LegalGraphRAG hard-code PRC; L-MARS bias .gov US. → **không repo nào có jurisdiction truy vấn được per-record** (trừ Indigo).

### 2.4 Điều kiện áp dụng (applicability) — cho reasoning
- **Repo:** LegalGraphRAG `judge_dep` = **list phẳng vị ngữ NL "是否…"**, re-parse bằng `eval()` (mong manh!) + `related_laws[{id,text}]` (`rule_graph.py:9-37`, `judge_law.py:4-33`). 4 facet ontology (defendant/acts/property/intent).
- **TraLuat (NÂNG CẤP):** `applicability_condition[]` **có cấu trúc** `{element_id, text, source_unit_eid, temporal_window}` thay vì phẳng — để `verify_article` element-wise *auditable + versionable*, không `eval()`.

### 2.5 Trạng thái xác minh (verification-state) — cho grounding
- **Repo (L-MARS, mạnh nhất — @dataclass):** `ClaimRecord{claim, cited_url, cited_snippet, support_level, failure_type, severity, confidence[0,1], explanation}`; **enum 6** support_level, **enum 7** failure_type (gồm `temporally_invalid`), **enum 3** severity (`verify_agent.py:89-118`).
- **TraLuat (ADOPT nguyên):** dùng y các enum này, **nhưng `temporally_invalid` được backed bằng NGÀY THẬT** (tra `in_force`), không chỉ phán đoán. "nguồn trích" = `unit_eid + version` thay URL.

### 2.6 Finding/output — cho workflow
- **Repo (claude-for-legal):** finding block `Section / Playbook-says / Contract-says(verbatim) / Gap(enum 5) / Legal-risk(🔴🟠🟡🟢) + Business-friction (dual-axis) / Why / Redline / Fallback` (`vendor-agreement-review/SKILL.md:117-136`). Cell trích xuất `{value, state(enum 4), quote, location}` + nghĩa vụ verbatim (`ma-diligence-columns.md`).
- **TraLuat (ADOPT + thay ruột):** dùng schema finding + cell này, **"Playbook-says" nối `required_clause_rule@T`** (không tĩnh), mỗi finding kèm trích dẫn + ngày hiệu lực.

### 2.7 Tenant & governance
- **Repo:** **KHÔNG repo nào** có `tenant_id` (claude-for-legal chỉ folder `matters/<slug>/`). → net-new.
- **TraLuat:** `tenant_id` mọi object khách; `review_status`, `confidence`, `created_by`, `provenance`, nhãn AI.

### 2.8 Eval/training (đánh giá trọng số)
- **Repo:** legalbenchrag `Snippet{file_path, span}` + `tags=[corpus]` (`benchmark_types.py:24-60`); LeSICiN instance `{id, text[], labels[Section ids]}` multi-hot + **pos_weight** (TWS/VWS) + `thetas/lambdas/pthresh` (`helper.py:67-73`, `model.py:5-16`); CUAD 41-cat span / ContractNLI 17-hyp+NOTMENTIONED+evidence / MAUD 92 MCQ.
- **TraLuat (FORMALIZE):** entity `dataset_version` + `label` + `gold_span`; **tags đa chiều** = `{correct-article, correct-effectivity, catch-omission}` (mở rộng tag corpus của legalbenchrag thành 3 trục benchmark); pos_weight kiểu LeSICiN cho linking.

---

## 3. Bảng: CHỨC NĂNG AI → metadata tiêu thụ

| Chức năng | Metadata cần | Ta có? |
|---|---|---|
| **Retrieval** | embedding · struct_header · span · lang · **valid_from/to** · jurisdiction · authority.rank · **tenant** | ✅ (temporal+tenant là net-new) |
| **Reasoning** | norm_relation(type, effective_date) · authority.rank · **applicability_condition typed** · precedent(situation/solution/annulled) · judgment(facts/cited/outcome) | ✅ (applicability_condition = NÂNG CẤP so judge_dep) |
| **Inference/nội suy** | concept/term + equivalence_type · structural features (attr/align/struct) · multi-hop graph | 🟡 (cần định nghĩa structural features rõ) |
| **Eval/training (trọng số)** | gold_span · labels · **3-axis tags** · pos_weight · dataset_version · review_status/confidence | 🟡 (cần FORMALIZE dataset_version+label+gold) |

---

## 4. BỐN GAP repo để trống → TraLuat lấp (xác nhận file+line)
1. **Không hiệu lực/version attr** trên node/edge/rule (trừ Indigo 1-trục) → ta: bitemporal + norm_relation.effective_date.
2. **Không tenant_id** trên bất kỳ object nào → ta: tenant mọi nơi.
3. **Không jurisdiction truy vấn được** per-record (hard-code/bias) → ta: jurisdiction + authority.rank.
4. **applicability untyped** (judge_dep phẳng + `eval()`) → ta: `applicability_condition` có cấu trúc.

---

## 5. BỔ SUNG CỤ THỂ vào schema (ngoài w2 spec)
```
-- 2.4 điều kiện áp dụng có cấu trúc (nâng cấp judge_dep)
applicability_condition(id, unit_id FK, element_id, text,
   source_unit_eid, temporal_window daterange, review_status)

-- 2.5 trạng thái xác minh (adopt L-MARS, backed bằng ngày thật)
verification_record(id, answer_id, claim, cited_unit_eid, cited_version,
   support_level ENUM6, failure_type ENUM7, severity ENUM3,
   confidence FLOAT, explanation, as_of DATE)

-- 2.6 finding (adopt claude-for-legal, nối required_clause_rule@T)
finding(id, review_id, section, playbook_rule_id FK, contract_quote,
   gap ENUM5, legal_risk ENUM4, business_friction ENUM4,
   why, proposed_redline, fallback, citation_unit_eid, as_of)

-- 2.8 eval/training có version (flywheel L14)
dataset_version(id, name, created_at, note)
label(id, dataset_version_id FK, kind, subject_ref, value, labeler, confidence)
gold_span(id, query, file_path, span_start, span_end, tags[])  -- tags: 3-axis
```

**Enum chốt (adopt từ repo):**
- `support_level` = supported | partially_supported | unsupported | citation_unreachable | no_citation | verifier_error (L-MARS).
- `failure_type` = none | partially_relevant | unsupported | fabricated_source | **temporally_invalid** | no_citation | verifier_error (L-MARS; `temporally_invalid` nối `in_force`).
- `gap` = Missing term | Weaker than standard | Weaker than fallback | Non-standard structure | Unacceptable (claude-for-legal).
- `cell.state` = answered | not_present | unclear | needs_review (claude-for-legal).

> **Một dòng:** repo cho ta *hình dạng metadata* tốt (Indigo hiệu lực, L-MARS verify-enum, claude-for-legal finding, LeSICiN label+pos_weight) — TraLuat **ráp lại + thêm 3 trục không ai có (temporal 2-trục · tenant · jurisdiction-per-record) + nâng applicability từ phẳng/`eval()` thành typed.**
