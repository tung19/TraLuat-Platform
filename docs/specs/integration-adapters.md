# TraLuat — Lớp Adapter/Transform cho từng seam (hợp đồng ghép repo)

> Mỗi mảnh repo chạm hệ **chỉ qua một adapter** biến output gốc → **schema canonical (W2) / interface**, và **ép bất biến** (`as_of` + `tenant` + verify) tại chỗ đó. Adapter = *anti-corruption layer*: chặn data-model ngoại rò vào lõi.
> Đọc kèm `docs/integration-audit.md` (verdict từng repo), `docs/specs/w2-knowledge-graph.md` (schema đích), `CONTRIBUTING.md`.

---

## 0. Nguyên tắc adapter (mọi seam tuân)
1. **Một nơi duy nhất/seam.** Không rải mapping khắp code; mỗi repo = 1 module `adapters/<repo>.py`.
2. **Vào = format gốc, Ra = canonical** (`document/unit/unit_version/norm_relation/chunk/...` của W2) hoặc kiểu của interface (`TemporalRepository/RetrievalService/GroundingService/LLMGateway`). **Không** để format gốc (AKN-XML, LangChain `Document`, torch graph, eyecite `Citation`) đi sâu hơn adapter.
3. **Ép bất biến tại adapter:** gắn `as_of`, `tenant_id`, `review_status`, `confidence`; không có → `needs_review`/abstain (không bịa).
4. **Mỗi seam có seam-test:** chứng minh (a) map đúng canonical, (b) truy xuất mang `as_of`+`tenant` (không global), (c) không rò format gốc.

---

## 1. eyecite — **WIRE-AS-LIB** (citation engine)  · seam: trích dẫn → `norm_relation`/canonical ID
```
INPUT  eyecite.get_citations(text) → [Citation{groups{...}, metadata{...}, span}]
XFORM  adapters/eyecite_vn.py:
         - thay reporters_db (US) bằng vn-legal-db (pattern VN) — REBUILD-FOR-VN
         - Citation → {dst_doc_number, dst_unit_eid?, relation_type, evidence_span}
         - resolve "điều này/nêu trên" theo eId cấu trúc (KHÔNG dùng antecedent US)
OUTPUT NormRelationRecord(src_unit_eid, dst_frbr/eid, relation_type,
         effective_date, evidence_span, confidence=<công thức>, review_status='needs_review')
INVARIANT confidence phải định nghĩa (eyecite không có) → mặc định needs_review; W2 chỉ áp khi approved
TEST   câu "Điều 3 Khoản 2 của Nghị định 99/2015/NĐ-CP" → 1 relation đúng eId; "khoản này" resolve đúng; US reporter pattern KHÔNG lọt
```

## 2. cobalt — **WIRE-AS-LIB** (FRBR URI)  · seam: ID → canonical URN
```
INPUT  cobalt.FrbrUri.parse(uri)  (pure Python; ép Python≥3.12, LGPL)
XFORM  adapters/cobalt_uri.py: FrbrUri ↔ TraLuat canonical ID (trl:vn/...); map country/doctype/subtype/date/lang
OUTPUT document.frbr_uri, unit path, @date/lang
INVARIANT giữ cobalt sau interface; nếu bỏ LGPL sau này → chỉ cần thay module này
TEST   round-trip parse→build; ngày/ngôn ngữ/loại map đúng
```

## 3. Indigo — **REMODEL-PATTERN** (bitemporal)  · seam: W1→W2 ingestion contract
```
KHÔNG chạy Indigo (Django). Adapter = chính SQLAlchemy models + apply_amendment của W2.
INPUT  W1 records (DocumentRecord/UnitRecord/UnitVersionRecord/NormRelationRecord)
XFORM  mô phỏng Work/Expression/Amendment của Indigo:
         - Work→document ; Expression→unit_version(valid_from,valid_to,tx_from,tx_to)
         - Amendment→apply_amendment() (SPLIT interval, tx-version — xem w2 §11 C1/C2)
         - AKN-XML-trong-cột (Indigo) KHÔNG dùng → ta phân rã thành unit quan hệ
OUTPUT canonical bitemporal store
INVARIANT EXCLUDE no-overlap; materialize chỉ khi norm_relation.review_status='approved'
TEST   w2 §8 (as-of trước/trong/sau sửa đổi, cùng-ngày, out-of-order, tx-time)
```

## 4. legalbenchrag — **RUN-AS-SERVICE / PORT**  · seam: eval harness + chunker
```
langchain 0.2 đụng 0.3 của PAKTON → KHÔNG chung env. Hai lựa chọn:
  (a) service eval riêng (env riêng), gọi qua HTTP; hoặc
  (b) PORT ý tưởng sang code ta (khỏi kéo langchain): span-model rời-nhau + char-level P/R + chunker giữ-span + diskcache
XFORM  adapters/eval_harness.py: chunk theo unit cấu trúc VN (giữ span) → (unit_version_id, span);
         tags 3 chiều {correct-article, correct-effectivity, catch-omission}
OUTPUT báo cáo P/R + cổng CI (L13)
INVARIANT cache key GỒM tenant+as_of (embedding cache chia sẻ); không rò langchain 0.2 vào runtime chính
TEST   chunk.content == text[span]; metric cấp-ký-tự đúng; CI fail khi dưới threshold
```

## 5. LegalGraphRAG — **REBUILD-PATTERN** (Auditor)  · seam: L8 reasoning (clean-room)
```
no-LICENSE → viết lại sạch, KHÔNG copy. Không có format gốc để map.
XFORM  Auditor consume candidate_articles (canonical Article{unit_eid,version_date,text,elements})
         - verify_article element-wise (parse bool structured — w4 C1/C2)
         - cổng in_force(as_of) (w4 C3) + prune
OUTPUT AuditResult(verified_articles/precedents, trail)
INVARIANT KHÔNG dùng NetworkX in-mem gốc; chạy trên graph/KB canonical; mọi LLM qua LLMGateway(tenant)
TEST   w4 §7 (element-wise, cổng hiệu lực, prune, empty-set→abstain)
```

## 6. L-MARS — **REBUILD-PATTERN** (verifier)  · seam: L6 grounding (clean-room)
```
no-LICENSE → viết lại sạch. Adapter = GroundingService.verify_answer.
XFORM  draft (có trích dẫn inline eid@version) → verify 6 lớp + faith-search + abstain
         - "nguồn trích" = unit_eid+version (KHÔNG URL như L-MARS)
         - temporally_invalid backed bằng in_force thật (không phải web-search)
OUTPUT VerifiedAnswer(support_level/failure_type/severity/confidence)
INVARIANT cross-provider verifier; cost có trần
TEST   w3 §5 (trích sai/hết hiệu lực → hạ lớp/abstain)
```

## 7. LeSICiN — **REBUILD-PATTERN** (linking)  · seam: L3 LinkingService (clean-room)
```
no-LICENSE + torch_sparse không co-install → viết lại sạch, hiện đại hoá.
XFORM  LinkingService.link_judgment(facts, as_of):
         - bge-m3 (thay Sent2Vec/HAN) + light GNN/ancestor-sum (thay MAGNN) + retrieval (thay BCE-toàn-label)
         - inductive: bản án mới chỉ encode+match, không train lại
OUTPUT [UnitMatch] (điều luật áp dụng), lọc theo ngày bản án
INVARIANT candidate lọc theo as_of; cold-start luật mới (0 citation) xử lý tường minh
TEST   bản án mẫu → điều đúng, loại điều hết hiệu lực tại ngày vụ việc
```

## 8. PAKTON — **WIRE runtime + REMODEL engine**  · seam: retriever + Document
```
Lift skeleton (FastAPI/Celery/SQLAlchemy). NHƯNG:
XFORM  - KHÔNG lift thẳng retrieve(query,**kwargs); bọc thành RetrievalService.retrieve(query, as_of, tenant, ...)
         - LangChain Document/chunk metadata → canonical chunk(unit_version_id, lang, text, struct_header)
         - LLM per-node → LLMGateway tập trung (+ guard tenant + nhãn AI)
OUTPUT chunk canonical + answer theo hợp đồng đầu ra
INVARIANT mọi retrieve mang as_of+tenant (không global); không rò LangChain Document vào W2
TEST   w5 §7 (cô lập tenant), w3 (effectivity filter)
```

## 8b. Lakehouse template → TemplateExemplarStore (FR-34)  · seam: đơn-mẫu → TES index
```
Nguồn  Lakehouse (Delta/Iceberg) — data-eng sở hữu: curate + ẩn danh template đơn từ.
TRIGGER CDC event HOẶC scheduled sync (data-eng phát) → adapters/lakehouse_template.py
XFORM  lakehouse row/schema → canonical TemplateDoc{template_id, doc_type, jurisdiction,
         version, text, struct, provenance, license}  (KHÔNG để schema lakehouse đi quá adapter)
         → embed + index vào TES (pgvector+BM25, W3)
OUTPUT  TemplateDoc canonical trong TES
INVARIANT - idempotent upsert theo (template_id, version) — trigger lặp không nhân bản
          - template = KHO DÙNG CHUNG (không tenant_id, không RLS) NHƯNG giữ provenance+license
          - ★ ranh giới PII: adapter CHẶN mọi field có dữ liệu vụ việc/đương sự lọt vào TES
            (template phải đã ẩn danh ở lakehouse; nghi ngờ → quarantine, không index)
TEST    (a) map đúng TemplateDoc; (b) upsert idempotent (chạy 2 lần = 1 bản);
        (c) không field PII nào vào TES; (d) retrieve(doc_type, as_of) trả mẫu đúng loại
```

---

## 9. Bản đồ seam (một hình)
```
eyecite ─┐
cobalt  ─┤ WIRE-AS-LIB  ──▶ adapters/ ──▶┐
Indigo  ─┐                               │
bluebell─┤ REMODEL      ──▶ (code ta)  ──┤
PAKTON  ─┘ (runtime+engine)              ├─▶  SCHEMA CANONICAL (W2) + INTERFACES  ──▶ lõi
legalbenchrag ─ SERVICE/PORT ──────────▶┤        (mối nối DUY NHẤT)
LeSICiN/LegalGraphRAG/L-MARS ─ REBUILD ─▶┘
```

## 10. Checklist mỗi khi "ghép" một mảnh
- [ ] Xác định verdict (WIRE/REMODEL/SERVICE/REBUILD) từ `integration-audit.md`.
- [ ] Viết `adapters/<repo>.py` — vào format gốc, ra **canonical/interface**.
- [ ] Ép `as_of` + `tenant` + `review_status`/`confidence` tại adapter.
- [ ] **Không** để format gốc (AKN-XML/LangChain Document/torch/eyecite Citation) đi quá adapter.
- [ ] no-LICENSE → clean-room, không copy dòng nào.
- [ ] Pin version; nếu đụng dep (langchain 0.2) → tách service.
- [ ] **Seam-test** xanh: map đúng canonical + truy xuất có as_of/tenant + không global + không rò format gốc.

> Một câu: **adapter là đê chắn — mỗi repo đổ vào một cửa, biến thành canonical + gắn as_of/tenant, rồi mới vào lõi. Không có cửa nào khác.**
