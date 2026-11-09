# TraLuat — Quyết định stack: Database + ML + Local model + LLM

> Chốt cụ thể: dùng DB gì · xử lý ra sao · ML/local/LLM phân vai thế nào. Có lý do + độ đảo ngược.
> Dựa trên deep-check lưu trữ đối chiếu repo (`research_notes/Repo deep read/storage_dataflow_check.md`) và `technical-design.md §A.5, §B`.

---

## 1. DATABASE — dùng loại gì

**Nguyên tắc: Postgres-centric, hạn chế polyglot.** Một nguồn-sự-thật; chỉ mục là phái sinh rebuild được; chỉ thêm kho chuyên dụng khi *đo được* nút thắt. (Nguyên tắc "derived rebuildable" là lựa chọn được MỌI repo tán thành.)

| Vai trò | Chọn | Vì sao | Đảo ngược? |
|---|---|---|---|
| **Nguồn-sự-thật (SoR)** | **PostgreSQL** | bitemporal `unit_version` + toàn bộ canonical entity; toàn vẹn quan hệ; chín; dễ tuyển người. Indigo xác thực PG-as-SoR | — (nền) |
| **Vector (embedding)** | **pgvector** (trong chính Postgres) | khỏi thêm vector-DB riêng giai đoạn đầu | **Dễ** — sau `Embedder/VectorIndex` interface → Qdrant/Milvus khi scale |
| **Đồ thị quy phạm** | **FK + recursive CTE trên Postgres** trước; **Apache AGE/Neo4j chỉ khi cần multi-hop openCypher thật** | ⚠️ deep-check: *không repo nào dùng graph-DB*; Indigo mã hoá đồ thị sửa đổi bằng FK và chưa từng cần graph engine → **hoãn AGE** | **Dễ** — AGE là extension, bật sau |
| **Blob gốc** | **MinIO/S3-compatible, đặt tại VN** | PDF/scan + hash; residency NĐ 356/2025 | Dễ |
| **Cache** | **Redis** (hot) + **diskcache content-hash** (embed/rerank/LLM) | tất định + rẻ + hợp CI (pattern legalbenchrag) | Dễ |
| **Sparse search** | **Postgres FTS / BM25 lib** + tokenizer tiếng Việt | hybrid với pgvector; khỏi OpenSearch sớm | Vừa |
| **Geo (bản đồ)** | **PostGIS** (extension của chính Postgres) | FR-39 directory VPLS "gần bạn" + bản đồ; truy vấn khoảng cách/bán kính; không cần DB geo riêng | Dễ — extension, bật khi làm FR-39 |
| **Hàng đợi / orchestration** | **Temporal** (+ broker Postgres/Redis) | pipeline nạp durable, retriable, resume, checkpoint HITL | Vừa |

**⚠️ Ba "cược" deep-check cảnh báo (đội mạnh gánh được, nhưng phải biết):** **pgvector ở quy mô corpus quốc gia** (chưa repo nào validate — mitigate bằng interface + benchmark), **bitemporal** (mới, phức tạp — test kỹ), **multi-tenant isolation** (net-new — thiết kế from first principles). → **Điều chỉnh hành động duy nhất: bắt đầu graph bằng FK+CTE, đừng commit AGE sớm.**

### Xử lý ra sao (write/read)
- **Chỉ batch (Temporal) ghi SoR.** Online **chỉ đọc**. 
- **pgvector + graph luôn rebuild được** từ SoR → mất/đổi schema = dựng lại, không mất sự thật.
- **Phân luồng tenant:** KB luật shared read-only; dữ liệu khách cô lập (RLS/schema-per-tenant + mã hoá key-per-tenant), zero-retention tuỳ chọn. Mọi kho tại VN.

---

## 2. CÓ ML KHÔNG — Có, và cố ý nhiều

**Nguyên tắc: không phải cái gì cũng LLM.** Tác vụ chạy trên *hàng triệu đơn vị*, cần *xác định được + kiểm toán được + rẻ* → dùng **mô hình nhỏ fine-tune + rule**, KHÔNG dùng LLM:

> 🔬 **Đã deep-research chốt model (Nov 2026). Cột "Đo trên" = benchmark L13. ✅ chốt · 🔬 A/B · 🔨 tự build.** License kiểm per model card trước production.

| Tác vụ | Model chốt | License | Tình trạng | Đo trên |
|---|---|---|---|---|
| Embedding | **DUAL-INDEX (★ E-fix)**: corpus embed bằng **CẢ 2** model → 2 index. Query VN → index **AITeamVN**; query EN/ZH → index **bge-m3**. Mỗi index self-consistent (query ⟷ doc CÙNG model) | Apache/MIT | 🔬 | Zalo (VN) + MLEB (cross-lingual) |
| ↳ vì sao dual, không route-1-index | route-1-index (VN doc=AITeamVN, query EN=bge-m3) → **2 không gian, dot-product vô nghĩa** → cross-lingual random. `chunk.embedding_model` phân biệt. | — | — | — |
| Rerank (VN) | **AITeamVN/Vietnamese_Reranker** (fine-tune bge-reranker-v2-m3); **bge-reranker-v2-m3** fallback | Apache-2.0/MIT | 🔬 ứng viên | Zalo 2021 |
| NER metadata (số hiệu/cơ quan/ngày) | **PhoBERT-base-v2** +CRF | MIT | ✅ (~98% F1 khả thi) | **PAP_NER** |
| ↳ domain lift | **ViLegalBERT** (`ntphuc149`, ACL'26 — CÓ THẬT, continual-pretrain PhoBERT) | Apache-2.0 | 🔬 A/B vs PhoBERT | PAP_NER |
| **Trích quan hệ sửa đổi/bãi bỏ** | encoder+classifier (PhoBERT/ViLegalBERT) | — | 🔨 **TỰ BUILD** · ★ F14-fix: weak-label bằng **LLM LOCAL (Qwen Apache)**, KHÔNG Claude API (tránh ToS train-on-output) · ★ D-fix: **recall-gated** — low-conf *không* bỏ im mà **flag human** (sót repeal = điều chết served live, tệ nhất); precision chỉ cho *auto-áp* | test tự-label theo **VLegal-Bench RE** |
| NLI/entailment (cổng "hỗ trợ") | **ViNLI/XNLI** fine-tune | — | 🔬 | ALQAC entailment |
| Liên kết bản án↔điều luật | bge-m3 + **GNN kiểu LeSICiN** | — | 🔨 rebuild | tự-label |
| OCR (xem §2b) | Docling + PaddleOCR + **Vintern** | MIT/Apache | 🔬 bench ~100 trang luật | held-out riêng |
| Giải xung đột · `in_force` · citation tồn tại | **RULE (không model)** | — | ✅ | — |

→ LLM chỉ cho **tổng hợp/suy luận ngôn ngữ**, luôn neo vào văn bản truy xuất.

### 2b. OCR pipeline (sửa plan cũ — Tesseract-vie KHÔNG làm default)
*Tesseract-vie yếu đúng chỗ cần (scan xấu, dấu, con dấu) → chỉ dùng backstop.*
```
Docling (MIT, khung cấu trúc: giữ Điều/Khoản + bảng TableFormer, offline, chunk RAG)
  ├ Tier-1 default: PaddleOCR (Apache, có confidence per-line) cho scan sạch
  └ Tier-2 VLM fallback (khi ocr_conf<~0.80 | có dấu/bảng | DPI thấp):
        • Vintern-1B-v3.5 / 3B (MIT — VLM CHUYÊN tiếng Việt, 1×T4)  ← chính
        • Qwen2.5-VL-7B (Apache) cho bảng/layout nặng
        ⚠️ tránh Qwen2.5-VL-3B (research-only) + Surya (weights revenue-cap)
ocr_conf: per-line softmax (Tier-1) · logprob + cross-check với Tier-1 (VLM) → flag doc thấp
```

### 2c. Benchmark L13 (chọn model theo SỐ, không theo tên)
- **VLegal-Bench** (CMC+VLSP, 12/2025) = thước đo **suy-luận-luật VN** chính (hơn VMLU chung) → **đây là eval harness L13**.
- + **PAP_NER** (NER) · **ALQAC** (retrieval/entailment) · **test tự-label** (quan hệ sửa đổi/bãi bỏ).
- ⚠️ **Phát hiện đắt giá:** model chung (Qwen/Llama thô) **= 0.00 F1 ở phát hiện xung đột hợp đồng** → **FR-41 (conflict) + omission BẮT BUỘC domain-tune + grounding**, cấm LLM thô.

---

## 3. CÓ LOCAL MODEL KHÔNG — Có, cho nguyên một tầng

**Chạy local/self-host (GPU trong VN):** toàn bộ ML ở Mục 2 — embedding, reranker, extractor, NLI, OCR, linking. Ba lý do:
1. **Chi phí & độ trễ** — chạy bulk trên hàng triệu đơn vị, gọi API ngoài là bất khả thi về tiền.
2. **Residency/cô lập (NĐ 356/2025)** — dữ liệu nhạy cảm **không rời** sang API ngoài.
3. **Tất định & kiểm soát** — fine-tune được trên luật VN, version được.

**LLM local (tuỳ chọn) — chốt:** **Qwen2.5-32B-Instruct** (Apache-2.0), AWQ 4-bit, **1×48GB GPU** (L40S/A6000/A100), serve qua **vLLM** (→ SGLang nếu cần prefix-cache/structured-output/multi-tenant), cắm Gateway bằng `endpoint_url`. **Vì sao 32B:** sweet spot accuracy (VLegal-Bench cho thấy domain-32B thắng model chung gấp 10–18×), **trilingual VN/EN/TQ tốt nhất** (gốc Alibaba → hợp FDI), 1 GPU affordable, in-VN. Rẻ hơn: Qwen2.5-7B/14B cho draft/route.
- **CMC-AI-Legal-32B** = **#1 VLegal-Bench** nhưng **CC-BY-NC-ND (cấm thương mại)** → *đích để đuổi* (tự fine-tune Qwen match), KHÔNG dùng trực tiếp.
- Tenant thường dùng Claude API; tenant nhạy cảm route sang Qwen local (egress guard W5).
- **★ F4-fix (cross-provider cho tenant local):** residency ép chạy local hết → nếu chỉ 1 model, answerer=verifier=Qwen = **self-verify ("tự vọng")**. → **cung cấp model local THỨ HAI khác họ** (vd Llama/Gemma cạnh Qwen) cho bước verify; HOẶC nếu 1 model → **chế độ suy giảm có khai báo**: siết **gate tất định** (gate1/2/3b) + **HITL bắt buộc** bù cho mất cross-provider.

---

## 4. CÓ LLM KHÔNG — Có, cho tầng suy luận, sau Gateway

**LLM cho:** grounded generation (Assistant), narrative Review, Draft song ngữ, suy luận Judgment Analysis, reasoner đa vai.
- **Mặc định: Claude API** — **Opus** (suy luận khó/Judgment/đa vai), **Sonnet** (khối lượng lớn: Review/Assistant). Model mới nhất Claude 5 (Opus 5.5/Sonnet 5.5); Gateway swappable.
- **Local (tenant nhạy cảm): Qwen2.5-32B** (xem §3) — trilingual, Apache-2.0, 1×48GB.
- **Luôn sau LLM Gateway** (W3/L7): swappable · prompt-cache · log I/O audit · **nhãn AI (Luật 71/2025)** · guard tenant.
- **Cross-provider judging** (L-MARS): answerer ≠ verifier, lấy điểm thấp nhất → giảm thiên lệch.
- **Không** tin kiến thức tham số của LLM: mọi phát ngôn qua grounding + verify 3 cổng hoặc **abstain**.

---

## 5. Intelligence orchestration — mỗi tầng gì / làm sao / thứ tự / rule base map đâu

**3 tầng:**
```
RULE (không model)   →  as_of · in_force · giải xung đột · citation tồn tại · threshold/abstain  (xác định, rẻ nhất)
ML nhỏ, phần lớn LOCAL →  embed · rerank · NER · trích quan hệ · NLI · OCR · linking            (bulk, residency, tất định)
LLM qua GATEWAY       →  sinh/suy luận ngôn ngữ, grounded, Claude API + Qwen local               (chỉ khi cần)
```

> 🔑 **Mô hình gốc:** 1 câu hỏi KHÔNG "chọn 1 tầng" — là **pipeline dùng cả 3 theo thứ tự**. **RULE bọc 2 đầu, LLM ở giữa, không bao giờ tin LLM thô:**
> `RULE (as_of + lọc hiệu lực) → [ ML retrieve → LLM generate ] → RULE/ML verify + abstain`

### A. INGEST pipeline (offline — xây KB) — thứ tự
| # | Bước | Tầng · Model |
|---|---|---|
| 1 | Ingest + dedup | RULE (hash) |
| 2 | OCR | **ML:** Docling+PaddleOCR+**Vintern** (+`ocr_conf`) |
| 3 | Cấu trúc + eId | RULE/parser (Bluebell) |
| 4 | NER metadata (số hiệu/ngày hiệu lực/cơ quan) | **ML:** PhoBERT (+VnCoreNLP word-seg) |
| 5 | Trích quan hệ sửa đổi/bãi bỏ | **ML + rule + LLM weak-label** |
| 6 | Bitemporal versioning | RULE (W2) |
| 7 | Căn song ngữ | **ML** |
| 8 | Embed + index | **ML:** bge-m3/VN embed → pgvector+BM25 |
→ Ra: **KB bitemporal + graph `norm_relation` + index + rule base** (pháp chế soạn authority_rank…).

### B. QUERY pipeline (online — trả lời) — thứ tự
| # | Bước | Tầng · Model | Rule base dùng |
|---|---|---|---|
| 1 | **`resolve_as_of`** (HYBRID) | **ML/LLM** trích ngày → **RULE** map câu-hỏi→mốc + hồi tố | resolve_as_of + hồi tố (Đ.7/Đ.156-K4) |
| 2 | **Retrieve** | **ML:** embed (route ngôn ngữ)+BM25→RRF→rerank; lọc `in_force@as_of`+tenant | in_force / effectivity |
| 3 | **resolve_conflict** | **RULE** | authority_rank@as_of · lex superior/posterior/specialis/treaty |
| 4 | **Generate** | **LLM** (Gateway: Claude / Qwen local) — chỉ từ cands | — |
| 5 | **Verify** (2 lớp) | gate1 tồn tại=RULE · gate2 in_force=RULE · gate3 supports=**ML-NLI rẻ TRƯỚC → LLM 6-class cross-provider** | in_force (gate2) |
| 6 | **Abstain / Answer** | **RULE** (threshold) + nhãn AI + hiển thị as_of + HITL | ngưỡng + rủi-ro-cao |

### C. Rule base map vào ĐÂU (lớp ràng buộc xuyên pipeline — KHÔNG chỉ tầng RULE)
`authority_rank` → bước 3 · `in_force/effectivity` → bước 2+3+5 · `resolve_as_of+hồi tố` → bước 1 · `required_clause_rule` → omission (W6) · `DocumentTypePack` → soạn đơn (FR-34). Chi tiết: `legal-rule-base.md`.

**Thứ tự chọn công cụ (sub-task):** rule được thì rule → không thì ML nhỏ local → cùng lắm mới LLM. Càng lên cao càng đắt/chậm/khó kiểm toán.

---

## 6. Tóm tắt quyết định
- **DB:** PostgreSQL (SoR) + pgvector + FK/CTE-graph (AGE sau) + MinIO + Redis/diskcache + Temporal — tất cả tại VN, derived rebuildable, tenant-isolated.
- **ML:** có, nhiều, chủ yếu **local** — embed/rerank **route theo ngôn ngữ** (VN: AITeamVN fine-tune bge-m3 — ứng viên; EN/ZH: bge-m3 thô; **đích = tự fine-tune trên corpus mình**), **PhoBERT-base-v2 / ViLegalBERT** (NER+quan hệ), ViNLI/XNLI, **Docling+PaddleOCR+Vintern** (OCR), LeSICiN-GNN (linking).
- **Eval L13:** adopt LegalBench-RAG method + BSARD design + Zalo 2021; **tự build effectivity/omission/conflict gold (moat)**; faithfulness = **citation-F1 tất định** (không RAGAS đơn độc); abstention 4-cell+Brier; LLM-judge answerer≠verifier cross-provider. *(W3 §4)*
- **Local model:** có — cả tầng ML; LLM local = **Qwen2.5-32B-Instruct** (Apache, AWQ, 1×48GB, vLLM) cho tenant nhạy cảm.
- **LLM:** có — Claude API (Opus/Sonnet) sau Gateway + Qwen local option, cross-provider verify, luôn grounded.
- **Benchmark L13 = VLegal-Bench** (+ PAP_NER/ALQAC/test tự-label) — chọn model theo số, không theo tên.
- **TỰ BUILD (không có sẵn):** dataset **quan hệ sửa đổi/bãi bỏ** + fine-tune domain cho conflict/omission (model chung = 0 F1 ở conflict). **CMC-AI-Legal-32B** = đích đuổi (license NC, không dùng trực tiếp).
- **Điều chỉnh từ deep-check:** hoãn AGE (dùng FK+CTE trước); benchmark pgvector ở scale; test bitemporal + tenant isolation kỹ.
