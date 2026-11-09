# W2 — Đồ thị tri thức (Knowledge Graph) — Đặc tả triển khai

> Module brief chi tiết cho member nhận mảng **W2 / L3–L4** (moat lõi). Code được ngay từ dữ liệu mẫu, không chờ 4TB.
> Nguồn pattern: Indigo (bitemporal/FRBR), LeSICiN (hetero graph linking), LegalGraphRAG (KG 4 tầng). Đọc kèm `docs/implementation-architecture.md §W2`, `docs/repo-deep-read.md`.

---

## 0. Module này giao ra cái gì (deliverables)

1. **Nguồn-sự-thật bitemporal** (Postgres) + API truy vấn "văn bản tại ngày T".
2. **Đồ thị quan hệ quy phạm** (norm graph) + giải xung đột.
3. **Đồ thị liên kết bản án↔điều luật↔án lệ** (inductive matching).
4. Ba **interface** cho W3/W4 tiêu thụ: `TemporalRepository`, `GraphQuery`, `LinkingService`.

**Nguyên tắc:** Postgres là nguồn-sự-thật duy nhất. Graph (AGE) và vector (pgvector) là **chỉ mục phái sinh — rebuild được**, không phải nguồn thứ hai.

---

## 1. Hệ định danh (URN) — chuẩn hoá trước khi code

```
Work:     trl:<jur>/<doc_type>/<doc_number_slug>
Unit:     <work>/<unit_path>                         vd .../dieu-3/khoan-2/diem-a
Version:  <unit>@<YYYY-MM-DD>/<lang>                  vd ...@2024-07-01/vi
```
- `eId` ổn định (kiểu Bluebell) là cột unique trên `unit`: `nd99__dieu_3__khoan_2`. Amendment/commencement trỏ vào `eId`, **không** trỏ vào id tự tăng.
- Parse/serialize URN: port `refs/cobalt/.../uri.py::FrbrUri.parse` (pure Python).

---

## 2. Schema canonical (DDL-level)

**Nhóm văn bản/cấu trúc:**
```
jurisdiction(id, code UNIQUE, name, legal_family, config_ref)
authority(id, jurisdiction_id FK, name, type, rank_level INT, parent_id FK)   -- rank_level cho lex superior
document(id, frbr_uri UNIQUE, jurisdiction_id FK, doc_number, doc_type,
         authority_id FK, title_vi, title_en, date_issued, date_effective,
         date_expired, status, source_uri, source_hash, gazette_ref)
unit(id, document_id FK, parent_id FK, unit_type, ordinal INT, label,
     eid UNIQUE)                                     -- cây đệ quy; KHÔNG chứa text
```

**Nhóm bitemporal (trái tim):**
```
unit_version(id, unit_id FK, lang,
   valid_from DATE, valid_to DATE NULL,              -- valid-time (hiệu lực)
   applies_from DATE NULL,                           -- ★ A-fix: hồi tố — áp cho hành vi TỪ ngày này (có thể < valid_from); NULL = = valid_from
   tx_from TIMESTAMPTZ, tx_to TIMESTAMPTZ,           -- transaction-time (hệ thống tin)
   text TEXT NULL,                                   -- NULL = tombstone (bãi bỏ)
   status, source_relation_id FK NULL, review_status, created_by)
-- INDEX: (unit_id, lang, valid_from, valid_to), (unit_id, tx_to) partial WHERE tx_to='infinity'
-- ★ effect_status(eid, as_of) → {in_force|expired_citable|transitional_applies|not_yet} (KHÔNG chỉ bool in_force)
```

**Nhóm đồ thị/quan hệ:**
```
norm_relation(id, relation_type, effective_date DATE, evidence_span, confidence, review_status,
   src_doc_id FK, src_unit_id FK NULL,              -- ★ G3-fix: endpoint cấp DOCUMENT hoặc UNIT (unit NULL = quan hệ cả văn bản, vd "thay thế TOÀN BỘ NĐ X")
   dst_doc_id FK, dst_unit_id FK NULL,
   order_key INT)                                    -- ★ G4-fix: khóa thứ tự intra-date = (date_issued, gazette/doc_number) → fold các amendment CÙNG effective_date theo thứ tự
   -- relation_type ∈ {cites, amends, repeals, replaces, guides, conflicts, hierarchy}
   -- document-level repeal/replace: tombstone mọi unit_version mở của dst_doc tại effective_date (R3/R4 áp ở cấp doc)
   -- ★ C3-fix: UNIQUE dedupe (src_doc,src_unit,dst_doc,dst_unit,relation_type,effective_date) → replay/CDC không nhân đôi edge
```

**Nhóm án lệ/bản án:**
```
precedent(id, jurisdiction_id FK, number, name, source_judgment_id FK,
   situation, solution, interpreted_unit_eids[], date_adopted,
   date_effective, date_annulled DATE NULL, annul_cause)
judgment(id, jurisdiction_id FK, court_id, case_no, date, matter_type,
   facts, holdings, cited_unit_eids[], cited_precedent_ids[],
   outcome_label, anonymization_status, source_uri)
```

**Nhóm song ngữ / omission (dùng chung với W3/W6):**
```
concept(id, label)
term(id, concept_id FK, lang, text, authority_source)
concept_alignment(concept_id FK, equivalence_type)   -- full|partial|none
clause_type(id, name, cuad_mapping)
required_clause_rule(id, jurisdiction_id FK, contract_type, clause_type_id FK,
   valid_from DATE, valid_to DATE NULL, source_unit_eid, severity)
```

**Nhóm phái sinh (indexing, L4):**
```
chunk(id, unit_version_id FK, lang, text, embedding VECTOR(1024), struct_header,
   valid_from DATE, valid_to DATE NULL, tenant_id, jurisdiction, doc_type,   -- ★ G13-fix: DENORMALIZE từ unit_version/document → filter as_of+tenant NẰM TRÊN bảng có HNSW index (đẩy predicate vào ANN, không post-filter-join). Auto-consolidator giữ đồng bộ.
   embedding_model)                                  -- ★ E-fix: model đã embed (dual-index: bge-m3 cho cross-lingual + AITeamVN cho VN) → query match ĐÚNG không gian
-- INDEX: HNSW(embedding), B-tree(tenant_id, valid_from, valid_to, doc_type) để narrow trước/trong ANN (iterative_scan)
-- ★ C3-fix: UNIQUE(unit_version_id, lang, span, embedding_model) → rebuild = drop-then-insert, replay không nhân đôi chunk
```

> 🔴 **★ C5-fix (chaos — replication + read-skew):** commit amendment yêu cầu **synchronous replication** (`synchronous_commit=remote_apply`) → failover không mất amendment vừa commit. **Pin `law_version`/`rule_base_version` tại ĐẦU query** và luồn qua mọi stage (resolve_as_of→retrieve→resolve_conflict→grounding) → 1 câu trả lời không đọc 2 phiên bản rule khác nhau. (cache key đã có version §6.2 — live path cũng phải pin.)

---

## 3. Bitemporal — thuật toán (đặc tả hành vi)

**R1. reconstruct_as_of(unit, as_of, lang, known_as_of=now) → text|None**
```
SELECT text FROM unit_version
WHERE unit_id=:u AND lang=:L
  AND valid_from <= :as_of AND (valid_to IS NULL OR valid_to > :as_of)   -- valid-time
  AND tx_from <= :known AND tx_to > :known                              -- transaction-time
→ nếu 0 dòng hoặc status='repealed' hoặc text IS NULL ⇒ None  (vắng mặt đúng)
```
Bất biến: với một (unit, lang, known_as_of) và một as_of, truy vấn trả **đúng 1 dòng** (hoặc 0). Nếu >1 ⇒ dữ liệu hỏng (khoảng valid-time chồng nhau) → test phải bắt.

**R2. document_as_of(document, as_of, lang) → text** — duyệt `unit` theo `ordinal`, ghép `reconstruct_as_of`, bỏ unit trả None.

**R3. apply_amendment(target_unit, new_text, effective_date, source_note, src_unit=None)**
- Đóng version đang mở tại `effective_date`: `valid_to = effective_date`.
- Chèn version mới `valid_from=effective_date, valid_to=NULL, tx_from=now, tx_to='infinity'`.
- Nếu `src_unit`: thêm `norm_relation(src, target, 'amends', effective_date)`.
> 🔴 **★ Chaos-fix (atomicity + idempotency + concurrency) — BẮT BUỘC:**
> - **Atomic (C1):** đóng + chèn trong **MỘT transaction SERIALIZABLE**; crash giữa chừng = rollback (không để "đóng mà chưa chèn" → luật biến mất).
> - **Idempotent (C1):** apply theo `source_relation_id` — đã áp (có version mở `source_relation_id=R` @effective_date) thì **no-op**; hoặc giữ **applied-ledger** keyed by relation id. Chống replay (Temporal/CDC at-least-once) double-apply.
> - **Serialize per-unit (C2):** `SELECT … FOR UPDATE` trên unit (hoặc SERIALIZABLE + retry) — 2 amendment đồng-thời cùng unit không cùng đọc 1 open row. EXCLUDE constraint (§11) là *lưới an toàn*, KHÔNG phải cơ chế điều khiển đồng thời.
> - **tx-versioning, KHÔNG in-place UPDATE** valid_to (giữ transaction-time — R5 mới reconstruct được "điều hệ thống từng tin").
> - **Same-date fold:** gộp các relation cùng `effective_date` theo `order_key` (§2 G4) rồi áp tuần tự → 1 version kết quả (không tạo `[d,d)` zero-width).

**R4. repeal(...)** = apply_amendment với `new_text=None, status='repealed', relation_type='repeals'` (cùng ràng buộc atomic/idempotent/serialize R3). Document-level repeal: tombstone mọi unit_version mở của dst_doc @effective_date.

**R5. correct_amendment_date(version_id, correct_valid_from)** — transaction-time: `tx_to=now` cho bản ghi sai (giữ lại để audit), chèn bản ghi đúng `tx_from=now`. ⇒ `known_as_of` trong quá khứ vẫn trả "điều hệ thống từng tin".

*(Phác thảo tham chiếu: `src/traluat/temporal.py` — minh hoạ, member viết lại trong module thật.)*

---

## 4. Giải xung đột quy phạm (deterministic)

> Thang bậc + quy tắc đọc từ **`docs/specs/legal-rule-base.md`** (authority_rank versioned theo as_of + Đ.156/Đ.58). `in_force` dùng **TemporalRepository (single-source), KHÔNG tự implement lại**.

`resolve_conflict(candidate_units[], as_of) → (winner, losers[], explanation)`:

**① CỔNG HIỆU LỰC (chạy ĐẦU TIÊN, theo as_of — không phải "hôm nay"):**
- chia: **còn hiệu lực @as_of** (`in_force`=true) vs **hết hiệu lực @as_of**.
- hết hiệu lực → **KHÔNG tranh thắng**, NHƯNG **vẫn trả về để CITE** kèm status (hết hiệu lực từ…, thay bởi…).
- **★ chuyển tiếp (nối W3 fix, legal-rule-base §3):** nếu điều khoản chuyển tiếp giữ luật cũ áp cho quan hệ phát sinh trước → nó **re-enter** (áp dụng được), gắn cờ. **KHÔNG hard-drop.**

**② Trong nhóm còn hiệu lực, áp theo thứ tự:**
1. **lex superior** (codified Đ.156 K2/Đ.58 K3): `authority_rank(as_of)` cao hơn thắng.
2. **lex posterior** (codified Đ.156 K3/Đ.58 K4): *cùng cơ quan*, cùng rank → `valid_from` mới hơn thắng.
3. ⚠️ **lex specialis** (nguyên tắc chung, **chưa xác nhận codified** — heuristic): cùng rank → chuyên ngành (scope) thắng chung. **Khi posterior ⟂ specialis (luật-sau-tổng-quát vs luật-trước-chuyên-biệt) → ABSTAIN → human** (ng.tắc #6).
4. **ưu tiên điều ước quốc tế** (vụ ≥2025-04, Đ.58 K5; pre-2025 verify Luật Điều ước QT) — trừ Hiến pháp.

**③ Abstain** nếu: không có bên nào còn hiệu lực (và không chuyển tiếp) · as_of mơ hồ · confidence thấp → `needs_review`, không đoán.

Trả kèm `explanation` (vì sao chọn) + **losers kèm status** → audit trail. **Thuần logic, không LLM.**

> ⚠️ `resolve_conflict` chỉ GIẢI khi đã có `candidate_units[]`. **PHÁT HIỆN** 2 điều cùng-chủ-đề-chọi-nhau (+ phân biệt cụ-thể-hoá-hợp-lệ vs vượt-uỷ-quyền) = **FR-41** (feature riêng, detection greenfield/hard — xem registry).

---

## 5. Ba đồ thị con (L4)

### 5.1 Norm graph (quy phạm)
- Node = `unit`; edge = `norm_relation`. Projection sang **Apache AGE** (openCypher trên Postgres).
- Query mẫu (multi-hop dẫn chiếu/hướng dẫn, lọc hiệu lực tại T):
```cypher
MATCH (a:Unit {eid:$eid})-[r:guides|cites*1..3]->(b:Unit)
WHERE r.effective_date <= $as_of
RETURN b
```
- Rebuild từ `norm_relation` bất cứ lúc nào.

### 5.2 Đồ thị liên kết bản án↔điều luật↔án lệ (cho Judgment Analysis)
Từ **LeSICiN** (`refs/LeSICiN/model/helper.py::generate_graph`), hiện đại hoá:
- **Node**: Bộ luật→Chương→Mục→Điều (cây thứ bậc) + Bản án + Án lệ.
- **Inductive**: bản án MỚI không vào graph, không train lại — mã hoá text (**bge-m3**) rồi **match** vào node điều luật (bi-encoder + cross-encoder rerank thay BCE-toàn-label).
- **Ba tín hiệu match** (học từ LeSICiN): attr (text↔text), **align (text↔cấu trúc — trội)**, struct. → khớp cả nội dung lẫn thứ bậc.
- **THÊM (LeSICiN thiếu)**: lọc ứng viên theo **ngày bản án** (chỉ điều còn hiệu lực tại thời điểm vụ việc), cạnh sửa đổi/bãi bỏ.

### 5.3 KG suy luận 4 tầng (tùy chọn, Phase 3+, cho W4)
Từ **LegalGraphRAG** (`core/graph_construct/`): fact/feature/ontology/rule + charge-anchored retrieval. Chỉ dựng khi làm reasoner.

---

## 6. Interface cho W3/W4 (hợp đồng tích hợp)

```python
class TemporalRepository(Protocol):
    def reconstruct_as_of(unit_eid: str, as_of: date, lang="vi",
                          known_as_of: datetime|None=None) -> str|None: ...
    def document_as_of(frbr_uri: str, as_of: date, lang="vi") -> str: ...
    def effect_status(unit_eid: str, as_of: date) -> EffectStatus: ...   # ★ B3-fix: enum {in_force|expired_citable|transitional_applies|not_yet}, KHÔNG bool
    def in_force_detail(unit_eid: str, version_date: date, as_of: date) -> InForceDetail: ...  # {in_force, transitional, version_match} — W4 dùng
    def versions(unit_eid: str) -> list[UnitVersion]: ...

class GraphQuery(Protocol):
    def multihop(src_eid: str, rel_types: list[str], hops: int,
                 as_of: date) -> list[Unit]: ...
    # ★ A-fix: nhận TẬP anchor (đa-mốc/lex-mitior), KHÔNG scalar. Cổng hiệu lực lọc theo effect_status;
    #   lex-mitior/hồi tố so sánh favorability GIỮA các anchor — chạy NGOÀI cổng in_force (không drop luật nhẹ-hơn-sau).
    def resolve_conflict(unit_eids: list[str], anchors: list[date], question_type: str) -> ConflictResult: ...

class LinkingService(Protocol):
    def link_judgment(facts: str, as_of: date, top_k=20) -> list[UnitMatch]: ...  # điều luật áp dụng
    def match_precedents(situation: str, as_of: date) -> list[PrecedentMatch]: ...
```
`in_force()` là điểm nối quan trọng nhất: **Citation Verifier (W3 L6) gọi hàm này cho cổng "còn hiệu lực".**

---

## 7. Hợp đồng đầu vào (W1 → W2)
W1 nạp cho W2 các record JSON: `document`, `unit[]`, `unit_version[]` (bản gốc), và `norm_relation[]` (quan hệ sửa đổi/bãi bỏ trích từ văn bản). W2 áp `norm_relation` qua R3/R4 để materialize version. **Nếu meta.json đã có cấp điều/khoản → map thẳng vào `unit`; W2 chỉ cần dựng `unit_version` + áp quan hệ.**

---

## 8. Acceptance tests (phải xanh)
1. **as-of cơ bản:** 1 điều, 1 sửa đổi (eff T1), 1 bãi bỏ (eff T2) → `reconstruct_as_of` trả: bản gốc khi `t<T1`; bản mới khi `T1≤t<T2`; `None` khi `t≥T2`; `None` khi `t<date_effective`.
2. **document_as_of:** ghép đúng, bỏ điều đã bãi bỏ.
3. **transaction-time:** nhập sai ngày → `correct_amendment_date` → `known_as_of` quá khứ trả bản cũ, hiện tại trả bản đúng; bản ghi sai vẫn còn (audit).
4. **đúng-một-dòng:** không có (unit, lang, t) nào trả >1 version.
5. **conflict:** Nghị định vs Thông tư cùng điều chỉnh → chọn Nghị định (lex superior) kèm explanation.
6. **linking:** 1 bản án mẫu → `link_judgment` trả điều luật đúng, loại điều đã hết hiệu lực tại ngày bản án.

---

## 9. Build tasks (thứ tự cho member)
1. Schema + migration (Alembic) cho nhóm văn bản/cấu trúc/bitemporal.
2. `TemporalRepository` + R1–R5 + test acceptance 1–4. ← *chứng minh moat #1*.
3. `norm_relation` + AGE projection + `GraphQuery.multihop` + `resolve_conflict` + test 5.
4. `LinkingService` (bge-m3 + bi-encoder, inductive) + test 6.
5. `chunk` + embedding + hợp đồng cho W3.

## 10. Steal-list (file trong `refs/`)
| Cần | File |
|---|---|
| Work/Expression + as-of + amendment→version | `indigo/indigo_api/models/{works,amendments,documents}.py` |
| URN parse | `cobalt/.../uri.py` |
| eId ổn định | `bluebell/.../eid.rs`, `xml.rs` |
| Hetero graph + inductive match | `LeSICiN/model/{helper,submodules,model}.py` |
| KG 4 tầng (sau) | `LegalGraphRAG/core/graph_construct/` |

---

## 11. Audit phản biện — lỗi xác nhận & sửa (review độc lập)
> Nguồn: `research_notes/Spec audit/w2_review.md`. §3–§5 ở trên có lỗi correctness thật; dưới là bản sửa (ưu tiên áp dụng). Bản phác `src/traluat/temporal.py` dính C1/C2 — coi như *đã bị thay thế* bởi thiết kế sửa dưới.

**🔴 C1 — Bất biến "một dòng" KHÔNG có constraint → phải ép ở DB.** `apply_amendment` gãy khi: ingest lệch thứ tự/hồi tố giữa chừng (2 row mở → `.one_or_none()` ném `MultipleResultsFound`, không phải None), effective < valid_from (overlap), **2 sửa đổi cùng ngày** (rất phổ biến 1/1 → ghost zero-width + last-writer-wins). Sửa:
```sql
ALTER TABLE unit_version ADD CONSTRAINT uv_no_overlap
  EXCLUDE USING gist (unit_id WITH =, lang WITH =, daterange(valid_from,valid_to) WITH &&)
  WHERE (tx_to = 'infinity');
```
và **viết lại `apply_amendment` để SPLIT thật** (tạo đoạn đuôi khi effective rơi giữa interval) + **từ chối/‑xử-lý-tường-minh insert lệch thứ tự & hồi tố**.

**🔴 C2 — Đóng version bằng UPDATE in-place (`prev.valid_to=...`) phá tx-time** → sau sửa đổi không dựng lại được "điều hệ thống từng tin" (mâu thuẫn R5). **Mọi thay đổi một `unit_version` phải qua tx-versioning** (`tx_to=now` + chèn row mới), không UPDATE `valid_to` tại chỗ.

**🟠 H1** R5 chỉ sửa 1 row → hàng xóm đóng sai ngày → tái tạo overlap; hard-code `lang="vi"`. Sửa cả cặp qua tx-version; dùng `wrong.lang`.
**🟠 H2** Thiếu **un-apply/revival**; `norm_relation` không có tx/valid → quan hệ W1 trích sai không de-materialize được; chưa set `source_relation_id`. Thêm FSM apply/unapply kiểu Indigo `AmendmentInstruction`; định nghĩa chính sách revival khi "bãi bỏ văn-bản-bãi-bỏ".
**🟠 H3** **Commencement từng phần chưa mô hình hoá**; `valid_from` lẫn với `date_effective` cấp văn bản → **phá `in_force()`** (cổng W3). Thêm commencement cấp điều (kiểu Indigo `Commencement.provisions`).
**🟠 H4 — Giải xung đột nhiều lỗi:** (a) **Thông tư *hướng dẫn* bị coi là xung đột** (không tra cạnh `guides`); (b) **lex specialis bất khả thi — thiếu cột `scope`** dù §4 cần; (c) `rank_level` *cơ quan* không xếp được cùng-cơ-quan khác doc_type (Luật vs Nghị quyết/Pháp lệnh) — thứ bậc VN theo **doc_type** (Luật BH VBQPPL Đ.4); (d) cascade cứng âm thầm chọn **luật chung mới đè luật riêng cũ** (thường SAI) → **trả `unresolved → human`**. Sửa: thêm `scope`, thứ bậc theo doc_type, tra `guides`, escalate general-vs-special.
**🟠 H5 — Linking tự mâu thuẫn:** §5.2 nói align (text↔cấu trúc) trội *nhưng* thay bằng bi-encoder text-only → **không tạo được align** (align đến từ graph/metapath encoder). Sửa: giữ **light GNN cho tín hiệu cấu trúc** HOẶC bỏ tuyên bố "align trội"; thêm lại negative sampling + calibrate ngưỡng. *(Inductive cho bản án mới thì đúng.)*

**🟡 M1** Cypher sai: `[r:...*1..3]` → r là list → dùng `ALL(rel IN r WHERE rel.effective_date <= $as_of)` + lọc cạnh repealed. **M2** FK+CTE **cycle** (A amends B, B cites A) → `WITH RECURSIVE` cần `UNION`/CYCLE/visited-set; định nghĩa filter projection (confidence/review_status). **M3** linking lẫn act-date vs judgment-date; candidate-gen + cold-start (luật mới 0 citation) chưa định nghĩa. **M4** `document_as_of` chỉ order `ordinal` cấp trên, **bỏ cây `parent_id`** → ghép sai văn bản phân cấp.
**🟢 L1** steal-list sai path: LeSICiN là `refs/LeSICiN/helper.py` (không `model/helper.py`).

**Tests §8 không đủ** (chỉ dữ liệu sạch in-order) → **thêm adversarial:** overlap/out-of-order/same-date · split interval · correction-neighbour · tx-time-under-amendment · revival · guides-not-conflict · specialis-with-scope · later-general-vs-earlier-special · cold-start linking · graph cycle · per-hop temporal filter.

**Đúng (giữ):** Postgres SoR + index rebuildable; nửa-mở `[valid_from,valid_to)`; amendment trỏ eId ổn định; vocab `guides` riêng; inductive cho bản án mới.
