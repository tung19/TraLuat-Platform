# TraLuat — Bài học từ đọc code repo (áp vào layer)

> Tổng hợp từ đọc *code thật* (chỉ đọc, không chạy) 5 repo ưu tiên trong `refs/`. Ghi chú chi tiết file-cited: `research_notes/Repo deep read/{pakton,indigo,legalgraphrag_lmars}.md`.
> Đọc kèm `docs/layered-architecture.md` (L1–L14), `docs/technical-design.md`.

---

## 0. Một kết luận bao trùm

**Mọi repo tham khảo đều cho ta *bộ khung* tốt, nhưng KHÔNG cái nào có moat của TraLuat — và cả ba moat đó đều trống theo đúng cùng một kiểu:**

| Thứ mọi repo đều THIẾU | = Moat TraLuat | Xác nhận từ code |
|---|---|---|
| Lọc **hiệu lực-thời-gian** khi retrieval/verify | #1 | PAKTON: retrieval global, không metadata filter. LegalGraphRAG/L-MARS: verify tính áp dụng nhưng **không kiểm ngày hiệu lực** |
| **Bitemporal** (transaction-time) + **norm-graph** + **giải xung đột** | #1 | Indigo: chỉ valid-time; chỉ FK Amendment/Commencement hardcode, không norm-graph tổng quát; không lex superior/posterior/specialis |
| **Grounding/citation-verify** ép trích dẫn điều khoản | #2/#3 | PAKTON: câu trả lời free-text, không ép trích dẫn |
| **Multi-tenancy / cô lập** | (trust) | PAKTON: một index chung, auth chỉ trả email |
| Xử lý **tiếng Việt** | (nền) | PAKTON: BM25 tách theo khoảng trắng → vô dụng cho VN |

→ **Chiến lược xác nhận bằng code: tái dùng khung (PAKTON backend/agent + Indigo data-model pattern + LegalGraphRAG/L-MARS gate), tự xây đúng ba moat vào đúng các khe hở trên.**

---

## 1. Lấy gì từ đâu — theo layer

| Layer | Lấy từ | Cụ thể |
|---|---|---|
| **L2** structure | Bluebell | PEG grammar thụt-lề = thứ bậc; `eid.rs`/`xml.rs` sinh **eId ổn định** (`chp_1__sec_1__p_1`) để amendment/commencement trỏ vào |
| **L3** data model ★ | Indigo + Cobalt | FRBR Work/Expression; amendment→materialize expression; point-in-time query; Cobalt `FrbrUri.parse()` (pure Python) cho canonical ID |
| **L5** retrieval | PAKTON | `BaseRetriever` interface cắm bm25/vectordb/hybrid; **nhưng phải thêm effectivity + tenant filter** |
| **L6** grounding/verify ★ | L-MARS (+ LegalGraphRAG) | VerifyAgent 6-lớp cấp-khẳng-định + Faith-Search repair + abstain; cross-provider judging |
| **L7** LLM gateway | PAKTON | `get_default_llm(node)` per-node, `endpoint_url`→vLLM/self-host; **ta gom lại tập trung + thêm cache/cost/log** |
| **L8** reasoning/đa vai ★ | LegalGraphRAG | Researcher→Auditor→Adjudicator; **Auditor hard-gate** `verify_article()` + `prune_unsupported_cases()` |
| **L9** workflow | PAKTON | Interrogator loop `generate_question→get_answer→refine→write_report`; sub-agent-as-tool |
| **Backend** | PAKTON | FastAPI + Celery + SQLAlchemy + Alembic + SSE step-streaming — skeleton dùng ngay |

---

## 2. PAKTON — khung backend & agent (L7/L8/L9 + skeleton)

**Dùng lại (shape tốt):**
- **Skeleton backend**: FastAPI (`API/api.py`, Celery-async + **SSE streaming từng step/tool**), Celery (`tasks.py`, retry, warm Archivist per-worker), SQLAlchemy (User/Conversation) + 2 Alembic migration, Docker/compose/nginx. Ba kho tách: SQL(metadata)/Postgres-checkpointer(history)/vector(chunk).
- **Retriever interface** `retrievers/base.py BaseRetriever(Runnable, ABC)`: `name` + `tool` + `retrieve(query,**kwargs)->List[Document]`. Cắm qua cờ `enable_*`. *(Sửa lỗi "DocumentSearch" trùng tên tool giữa bm25/vectordb/hybrid.)*
- **LLM gateway per-node** `models/llm.py get_default_llm(node_name)` + `endpoint_url` cho self-host.
- **Interrogator loop** (`Interrogator/graph/builder.py`) + **sub-agent-as-@tool** (Archivist gọi Interrogator gọi Researcher) — công thức orchestration.
- Orchestration qua **AsyncPostgresSaver checkpointer** keyed theo thread_id.

**Phải tự xây (greenfield — đúng moat):**
- **L5**: retrieval **lọc hiệu lực `as_of_date` + scope tenant/jurisdiction** (PAKTON truyền 0 metadata filter).
- **L6**: lớp grounding/citation-verify (PAKTON không có).
- **L7**: gateway **tập trung** + cost + prompt-cache + log audit (hiện bị *lặp* trong cả 3 agent; `local.py` HF chỉ là stub).
- **L8/L9**: siết stop-condition (hiện dựa sentinel so khớp embedding, `max_num_turns` mặc định 1 — mong manh); dựng workflow Review/Draft thật.
- **Multi-tenancy** ở mọi tầng; **tokenizer tiếng Việt** thay BM25 `.split()`; sửa **scale** (HybridRetriever dựng lại BM25 in-memory mỗi query → không chạy nổi corpus quốc gia).
- ⚠️ Repo không có `.env` thật (chỉ `.example`) → không chạy được nếu thiếu creds; coi như *đọc để học*, không để chạy.

---

## 3. Indigo + Cobalt + Bluebell — data model moat (L3)

**Pattern lấy được (remodel sang SQLAlchemy, đừng chạy Django):**
- **Work/Expression** (`indigo_api/models/works.py`): `Work` keyed `frbr_uri` + lifecycle (publication/assent/commenced/repealed_by/repealed_date/parent_work/main_commencement). `expressions()`, `possible_expression_dates()` (gắn tag initial/amendment/consolidation), `create_expression_at()` (clone expression trước làm template).
- **Amendment** (`amendments.py`): cạnh có hướng có-ngày `amending_work→amended_work`; `date` = ngày vận hành = `expression_date` mới; **version mới được materialize** bởi `create_expression_at`. `AmendmentInstruction` áp cấp điều khoản (FSM new→applied, `provision_id` eId, snapshot before/after).
- **Point-in-time** (`documents.py`): `Document` = Expression keyed `(work, language, expression_date)`; **truy vấn as-of-T** = `get_for_frbr_uri`: `expression_date__lte=T order_by('-expression_date').first()`; `valid_until()` *tính* valid-to = ngày trước mốc kế tiếp. **Partial commencement** qua `Commencement.provisions` (JSON danh sách eId).
- **Cobalt** `uri.py`: regex FRBR URI, 3 phép chiếu work/expression/manifestation, **token ngày `@date`** mã hoá toán tử thời gian *ngay trong ID* → `FrbrUri.parse()` pure-Python **dùng trực tiếp** cho canonical ID của ta.
- **Bluebell** `grammar.pest`: PEG thụt-lề = thứ bậc, từ khoá map được sang VN (CHAPTER/SECTION/ARTICLE → Chương/Mục/Điều); **eId ổn định** cho amendment trỏ vào → đúng stage cấu trúc hoá L2.

**Indigo THIẾU gì (phải tự thêm — đây là moat):**
- (a) **Không có norm-graph tổng quát có kiểu** — chỉ FK cứng Amendment/Commencement/repealed_by/parent_work → ta cần `norm_relation(type ∈ cites/guides/conflicts/...)`.
- (b) **Không giải xung đột** (không lex superior/posterior/specialis, không thứ bậc hiệu lực pháp lý) → ta thêm `authority.rank_level` + hàm giải xung đột.
- (c) **Chỉ valid-time, KHÔNG transaction-time** (chỉ created/updated + django-reversion) → **thêm trục `tx_from/tx_to TIMESTAMPTZ`** để trả lời "tại ngày *biết* K hệ thống tin gì" (phòng vệ pháp lý/audit).
- (d) **Hợp nhất thủ công** (ArbitraryExpressionDate); (e) **bãi bỏ thô** (cả Work; bãi bỏ một phần chỉ qua amendment).

→ Mapping đề xuất (từ notes): `document / document_version / unit / unit_version(valid_from,valid_to,tx_from,tx_to) / norm_relation / commencement / amendment_instruction`.

---

## 4. LegalGraphRAG + L-MARS — thiết kế hai cổng cho L6/L8

**LegalGraphRAG — Auditor HARD-GATE (L8, nửa áp-dụng của L6):**
- Orchestration là **hàm thường** `core/utils/util.py::analyze_case()` (không framework) → tách theo bị cáo → narrowing tuyến tính Researcher→Auditor→Adjudicator.
- **Auditor** (`core/agents/auditor.py`): `audit()` chạy `verify_article()` từng điều, giữ điều áp dụng được; `prune_unsupported_cases()` **loại án lệ** mà mọi điều nó viện dẫn đã bị bác (set-membership trên `law_ids` còn sống) → chặn analogy drift.
- **verify_article** (`core/judge/judge_law.py`): **kiểm từng yếu tố cấu thành** (NLI true/false theo checklist `judge_dep` + `related_laws`) rồi mới tổng hợp — KHÔNG phải yes/no tổng thể.
- **Adjudicator** tổng hợp phán quyết CHỈ trên tập đã verify.
- KG **4 tầng** (fact/feature/ontology/rule); **charge-anchored retrieval** (đoán ≤3 tội danh → đi tới điều liên quan).
- ❗ **Thiếu kiểm ngày hiệu lực** → khe cho moat #1.

**L-MARS — verifier cấp-khẳng-định + repair (L6):**
- `verify_agent.py`: **6 lớp** `supported / partially_supported / unsupported / citation_unreachable / no_citation / verifier_error`; **mỗi khẳng định chỉ đối chiếu nguồn nó tự trích** (chống rò chéo); phân biệt rõ "không trích" vs "trích hỏng/cũ" vs "lỗi verifier".
- **Faith-Search repair** (`faith_search/`): gom claim lỗi theo *kiểu lỗi* → **re-search có định hướng** (`router.py`: fabricated→lọc .gov; **temporally_invalid→truy vấn giới hạn ngày**; unsupported→nhắm lỗ hổng) → **sửa/đổi trích dẫn** → verify lại → **abstain** nếu vẫn yếu (include iff supported/partially & confidence≥0.6).
- **Cross-provider judging**: answerer ≠ verifier, lấy điểm *thấp nhất*.
- Với TraLuat: "nguồn trích" đổi từ URL (US) → **id+phiên bản điều luật VN** (dễ hơn match URL), và lớp `temporally_invalid` + repair theo ngày **chính là trục hiệu lực mà LegalGraphRAG thiếu**.

**Thiết kế TraLuat (ghép tốt nhất của cả hai) — hai cổng kẹp Adjudicator:**
1. **Cổng L8 (trước output):** Auditor hard-gate — mỗi điều phải qua **trích dẫn có thật + kiểm yếu tố cấu thành + NGÀY HIỆU LỰC (mới)**, rồi prune án lệ phụ thuộc.
2. **Cổng L6 (sau draft):** verifier 6-lớp + Faith-Search repair/abstain trên lập luận có trích dẫn của Adjudicator, cross-provider.
   → **Hiệu lực-thời-gian ép ở CẢ hai cổng.**

---

## 5. Bản lắp ráp — cả cụm vào TraLuat

```
[L2 cấu trúc hoá]   Bluebell grammar → eId ổn định
        │
[L3 data model]     Indigo Work/Expression + amendment-materialize + point-in-time
        │           + (TỰ THÊM) tx-time bitemporal · norm_relation graph · giải xung đột
        │           + Cobalt FrbrUri cho canonical ID
        ▼
[L5 retrieval]      PAKTON BaseRetriever  + (TỰ THÊM) effectivity filter + tenant scope + tokenizer VN
        ▼
[L8 reasoning]      LegalGraphRAG Researcher→Auditor→Adjudicator (Auditor hard-gate, verify_article element-wise, prune)
        ▼
[L6 grounding]      L-MARS VerifyAgent 6-lớp + Faith-Search repair + abstain + cross-provider
        ▼           (CẢ L8 và L6 đều ép as_of_date — khe hở mọi repo bỏ trống)
[L7/L9/backend]     PAKTON gateway per-node (→gom tập trung) · Interrogator loop · FastAPI+Celery+SQLAlchemy skeleton
        │           + (TỰ THÊM) multi-tenancy xuyên suốt
```

---

## 6. "Steal-list" — file cụ thể để đối chiếu khi code

| Cần dựng | Mở file này trong `refs/` |
|---|---|
| Canonical ID (FRBR URI) | `cobalt/.../uri.py` (`FrbrUri.parse`) |
| Work/Expression + lifecycle | `indigo/indigo_api/models/works.py` (`Work`, `expressions`, `possible_expression_dates`, `create_expression_at`) |
| Amendment → version mới | `indigo/indigo_api/models/amendments.py` (`Amendment`, `AmendmentInstruction`, post_save) |
| Point-in-time as-of-T | `indigo/indigo_api/models/documents.py` (`get_for_frbr_uri`, `valid_until`) |
| Cấu trúc hoá + eId | `bluebell/.../grammar.pest`, `eid.rs`, `xml.rs` |
| Retriever interface | `PAKTON/PAKTON Framework/Researcher/.../retrievers/base.py` |
| LLM gateway | `PAKTON/.../models/llm.py` (`get_default_llm`) |
| Agent loop / workflow | `PAKTON/.../Interrogator/.../graph/builder.py` |
| Backend skeleton | `PAKTON/.../API/api.py`, `tasks.py`, Alembic migrations |
| Auditor hard-gate | `LegalGraphRAG/core/agents/auditor.py`, `core/judge/judge_law.py` (`verify_article`, `prune_unsupported_cases`) |
| Agent orchestration | `LegalGraphRAG/core/utils/util.py` (`analyze_case`) |
| Citation verifier 6-lớp | `L-MARS/lmars/verify_agent.py` |
| Faith-Search repair | `L-MARS/lmars/faith_search/workflow.py`, `router.py`, `aggregator.py` |

---

# NHÓM 2 — LeSICiN · eyecite · legalbenchrag

## 7. LeSICiN — liên kết bản án↔điều luật (L3, cho Judgment Analysis)

*(Repo pre-LLM 2022: PyTorch + Sent2Vec + torch_sparse; data nằm trên Zenodo, không trong repo → toàn bộ `model/` là đối tượng viết lại.)*

**Pattern lấy được:**
- **Đồ thị dị cấu 5 node** (`model/helper.py::generate_graph`): Act/Chapter/Topic/Section/Fact = 2 đồ thị con ghép — **cây thứ bậc điều luật** (Act→Chapter→Topic→Section) + **mạng viện dẫn** (Fact→Section). Cạnh lưu `torch_sparse.SparseTensor` theo `(src_type, rel, trg_type)`.
- **Inductive stance (ý giá trị nhất)** (`model.py` forward + `run.py` loader wiring): bản án *mới* không vào graph, không train lại — chỉ mã hoá text rồi **match** vào node Điều luật thường trú (qua MatchNet học được, không dot-product). `if fact_batch.sample_metapaths: ... else: struct_logits=None`.
- **Ba head chấm điểm** (`submodules.py` MatchNet): attr (text↔text), **align (text↔cấu trúc — trội nhất)**, struct (cấu trúc↔cấu trúc); inference = 0.25·attr + 0.75·align → *khớp cả nội dung lẫn thứ bậc*.
- **Multi-label + mất cân bằng**: BCEWithLogitsLoss + `pos_weight` per-label (không negative sampling tường minh).

**Map TraLuat:** Act→Bộ luật, Chapter→Chương, Topic→Mục, Section→Điều/Khoản, Fact→bản án, citation→điều áp dụng.
**Hiện đại hoá:** Sent2Vec/HAN→**bge-m3**; MAGNN+RotatE→hetero-GNN nhẹ/ancestor-sum; **dense BCE toàn label→retrieval (bi-encoder + cross-encoder rerank)** (corpus VN không nhét vừa classification dày).
**Phải THÊM (LeSICiN hoàn toàn thiếu):** hiệu lực-thời-gian — version node theo hiệu lực, lọc ứng viên theo *ngày bản án*, thêm cạnh sửa đổi/bãi bỏ. Yếu điểm: graph một-snapshot tĩnh, không scale quá vài trăm label.

---

## 8. eyecite — pipeline trích dẫn (L2, feed L6)

**Pattern lấy được — pipeline 4 bước = 4 hàm API** (`eyecite/__init__.py`): `clean` → `get_citations` (find+tokenize) → `resolve` → `annotate`.
- **Finding** (`find.py`): tokenize thành list vị-trí trộn word thường + `Token` có kiểu, dispatch theo kiểu token. **Tokenizer dùng pyahocorasick làm PREFILTER literal-string** chọn ứng viên regex (`tokenizers.py::default_tokenizer`), span thật do regex sinh.
- **Tách data↔engine (bài học chốt, xác nhận):** engine *gần như không chứa* tri thức US — mọi pattern sinh từ package ngoài `reporters_db`/`courts_db` (`tokenizers.py:14-15`, `helpers.py:8`); `_populate_reporter_extractors()` nở template regex ($volume/$reporter/$page) thành TokenExtractor. → **engine dùng lại nguyên; pattern DB phải dựng lại cho VN.**
- **Resolution** (`resolve.py`): một lượt mang `resolved_full_cites` + `last_resolution`; id.→trước đó, supra→khớp tên bên, short→reporter+volume. 5 resolver *injectable*. → mẫu cho giải "điều này/nêu trên/cùng Luật".
- **Annotation giữ span** (`annotate.py`): `SpanUpdater` diff text sạch↔gốc bằng fast-diff-match-patch → remap offset qua bisect, **markup không hỏng offset gốc**. Dùng trực tiếp cho neo trích dẫn cấp điều khoản.

**Map TraLuat:** dựng package riêng **`vn-legal-db`** (nguồn Luật/NĐ/TT/QĐ/án lệ + ký hiệu cơ quan ban hành ~ courts-db) + **grammar VN mới**: `Điều X Khoản Y Điểm Z của {Luật/NĐ/TT} số…/năm…`, `án lệ số…/AL`, back-ref "điều này/nêu trên", và **phát hiện "được sửa đổi/bãi bỏ bởi"** (→ feed norm_relation ở L3).
**eyecite KHÔNG có (phải tự xây cho L6):** kiểm ngày hiệu lực/còn hiệu lực, lý luận phiên bản, kiểm *tồn tại* điều được trích, đồ thị sửa đổi.

---

## 9. legalbenchrag — harness eval + chunker (L4/L5/L13)

**Pattern lấy được:**
- **Ground-truth = span ký tự, bắt buộc rời-nhau & sắp-xếp** (`benchmark_types.py`: `Snippet{file_path, span}`, `validate_snippet_list`, `sort_and_merge_spans`) → **precision/recall cấp ký tự không nhập nhằng**.
- **Chunker giữ span với 2 assert bảo toàn** (`methods/baseline.py`): `sum(len)==len(content)` và `"".join(splits)==content`; span gán bằng offset chạy → **mỗi ký tự thuộc đúng một chunk**, `chunk.content == content[span0:span1]` (phân hoạch zero-drift = điều kiện neo trích dẫn chính xác). Hai chiến lược `naive` + `rcts` (RecursiveCharacterTextSplitter).
- **Metric cấp ký tự** (`run_benchmark.py::QAResult`): overlap span = `max(0, min(ends)-max(starts))`, tính theo ký tự (chunk trúng một phần → tính tỉ lệ); aggregation lọc theo `tags`.
- **Provider-abstraction + diskcache content-hash** (`utils/ai.py`) mọi lời gọi embed/rerank/LLM → chạy lại rẻ & tất định (hợp CI). Seam cắm: `RetrievalMethod` ABC (`ingest/sync/query/cleanup`).
- **Sweep** `retrieval_strategies.py`: tích Descartes chunk×size×rerank×top_k; idiom **"retrieve wide, rerank narrow"** (`embedding_topk=300`).

**Map TraLuat:** **dùng gần như nguyên** mô hình span + validator + metric + kỷ luật chunk + diskcache CI.
**Thích ứng:** biên chunk theo **đơn vị cấu trúc VN** (Điều/Khoản/Điểm) giữ nguyên phân hoạch offset + mang `unit_id` trong metadata; model tiếng Việt + **chuẩn hoá NFC** trước `.find()`; **thêm eval lọc-hiệu-lực as-of-date**; **benchmark 3 chiều** (đúng điều–khoản = P/R sẵn · đúng hiệu lực = mới · bắt bỏ sót = recall per-required-clause) qua cơ chế `tags`.
**Phải THÊM:** cổng CI pass/fail + baseline diff (repo chỉ xuất CSV, **không có cổng** — đúng L13 ta tự nối). Lưu ý: contract/English-centric, không có thứ bậc luật/sửa đổi.

---

## 10. Steal-list nhóm 2 (bổ sung)

| Cần dựng | Mở file này trong `refs/` |
|---|---|
| Đồ thị bản án↔điều luật + inductive match | `LeSICiN/model/helper.py` (`generate_graph`), `model/submodules.py` (MatchNet), `model/model.py` (forward inductive) |
| Pipeline trích dẫn 4 bước | `eyecite/__init__.py`, `find.py`, `resolve.py`, `annotate.py` (`SpanUpdater`) |
| Tách data↔engine (dựng vn-legal-db) | `eyecite/tokenizers.py` (`_populate_reporter_extractors`), `helpers.py` |
| Ground-truth span + metric cấp ký tự | `legalbenchrag/legalbenchrag/benchmark_types.py`, `run_benchmark.py` (`QAResult`) |
| Chunker giữ span (zero-drift) | `legalbenchrag/.../methods/baseline.py` (`sync_all_documents`) |
| Cache tất định cho CI | `legalbenchrag/.../utils/ai.py` (diskcache) |

---

## 11. Việc tiếp theo gợi ý (cập nhật sau nhóm 2)
1. **L3 trước:** remodel Indigo pattern thành SQLAlchemy (+ tx-time, norm_relation) → chứng minh "văn bản tại ngày T" trên một nghị định có sửa đổi. Thêm **grammar trích dẫn VN kiểu eyecite** để từ văn bản tự sinh cạnh `norm_relation` (sửa đổi/bãi bỏ).
2. **Harness eval sớm (L13):** port mô hình span + metric cấp-ký-tự + chunker giữ-span của legalbenchrag làm *cổng CI từ đầu* — benchmark 3 chiều. Có cổng trước, mới xây retrieval.
3. **L6 Auditor+Verifier** rút gọn từ LegalGraphRAG+L-MARS, ép `as_of_date`.
4. **Judgment Analysis (L3→L8):** đồ thị bản án↔điều luật kiểu LeSICiN (inductive, bge-m3, retrieval thay BCE) + lọc theo ngày bản án.
5. **Skeleton backend PAKTON** làm xương, thay retriever bằng bản effectivity+tenant-aware.
