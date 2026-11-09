# TraLuat — So sánh cách XỬ LÝ của các repo (rule ↔ ML ↔ LLM)

> Deep audit: từng repo tham khảo *xử lý* thế nào (data · model · grounding · storage · orchestration), so với stack TraLuat đã chốt (`specs/stack-db-and-models.md`).
> Nguồn: 8 bản deep-read + `storage_dataflow_check.md` (đã verify file+line).

---

## 1. Phổ xử lý — mỗi repo đứng một điểm, TraLuat cố ý gộp cả ba

```
PURE RULE ─────────── CLASSICAL ML ─────────── RETRIEVAL/EMBED ─────────── LLM-AGENT ─────────── PURE-LLM
 eyecite, Indigo        LeSICiN                 legalbenchrag          PAKTON,LegalGraphRAG,L-MARS   claude-for-legal
 (regex/grammar/HITL)   (GNN train, KHÔNG LLM)  (embed+rerank, ít LLM) (LLM làm suy luận/verify)    (100% prompt, KHÔNG engine)

TraLuat = HYBRID cả phổ: RULE (xung đột/in_force) + ML-local (embed/extract/OCR/link) + LLM-gateway (suy luận)
          → chọn tầng rẻ-nhất-đủ-dùng cho từng tác vụ.
```

**Nhận định lõi:** mỗi repo *chỉ ở một điểm* trên phổ. Academic repo (LegalGraphRAG/L-MARS) **dồn mọi thứ vào LLM** → đắt, chậm, khó audit, phi tất định. eyecite/Indigo **thuần rule** → chính xác, rẻ, nhưng không "hiểu" ngữ nghĩa. **TraLuat cố ý trộn** để lấy phần tốt nhất mỗi bên — đây là khác biệt xử lý căn bản, không repo nào làm.

---

## 2. Ma trận so sánh (đã verify)

| Dimension | eyecite | Indigo | LeSICiN | legalbenchrag | PAKTON | LegalGraphRAG | L-MARS | claude-for-legal | **TraLuat (chốt)** |
|---|---|---|---|---|---|---|---|---|---|
| **Cấu trúc hoá** | regex/tokenizer | **grammar (Bluebell) + HITL** | — | char-split | — | — | — | — | grammar + meta.json + LLM fallback |
| **ML (non-LLM)** | ❌ (rule) | ❌ | **GNN/HAN/Sent2Vec train** | embed+rerank | — | numpy embed | BM25 | ❌ | **nhiều, local** (bge-m3, extractor, OCR, NLI, link) |
| **LLM** | ❌ | ❌ | ❌ | ít (eval) | **nhiều** (provider-abstract) | **nhiều** (ERNIE/Qwen, per-element) | **nhiều** (cross-provider) | **100%** | có, **qua Gateway**, grounded |
| **Grounding/verify** | — | — | — | — | prompt + rerank | **Auditor element-wise** (LLM) | **6-lớp + faith-search** (LLM) | `[verify]` tag | **3 cổng: rule(có thật+in_force) + ML/LLM(hỗ trợ)** |
| **Storage** | — | **Postgres (XML in-column)** | file/torch_sparse | sqlite-vec | PG + Pinecone/Chroma | **NetworkX in-mem pickle** | stateless | markdown files | **Postgres SoR + pgvector + FK/CTE** |
| **Orchestration** | hàm thuần | Django + HITL | train loop | sweep script | **LangGraph + Celery** | hàm `analyze_case` | LangGraph | Claude harness | Temporal(nạp) + orchestration(serve) |
| **Hiệu lực-thời-gian** | ❌ | 🟡 valid-time 1 trục | ❌ | ❌ | ❌ | ❌ | 🟡 date-bounded repair | ❌ | ✅ **bitemporal (2 trục)** |
| **Multi-tenant** | ❌ | ❌ | ❌ | ❌ | ❌ (user_email) | ❌ | ❌ | ❌ | ✅ **cô lập cứng** |

---

## 3. Đọc ngang: ba kiểu xử lý & bài học

**① Kiểu RULE/GRAMMAR (eyecite, Indigo)** — chính xác, tất định, rẻ, audit tốt; nhưng không hiểu ngữ nghĩa, cần HITL cho ca khó.
→ **TraLuat lấy:** grammar trích dẫn (eyecite) + consolidation/versioning + HITL (Indigo) cho tầng *xác định* (W1/W2). Đúng chỗ cần chắc chắn 100%.

**② Kiểu CLASSICAL ML (LeSICiN)** — train một lần, inference rẻ, tất định, chạy bulk; nhưng pre-LLM, cứng, khó cập nhật.
→ **TraLuat lấy:** mẫu đồ thị + inductive matching, *hiện đại hoá* bằng bge-m3 + retrieval. Đúng chỗ cần bulk + tất định (linking, extract).

**③ Kiểu LLM-AGENT (PAKTON, LegalGraphRAG, L-MARS)** — hiểu ngữ nghĩa, linh hoạt, lập luận; nhưng đắt, chậm, phi tất định, dễ ảo giác, khó audit; **tất cả đều thiếu hiệu lực-thời-gian**.
→ **TraLuat lấy:** pattern Auditor + verify + faith-search, nhưng **(a)** đặt cổng rule (in_force) *trước* để khỏi tốn LLM cho điều hết hiệu lực; **(b)** neo bắt buộc; **(c)** cross-provider. Đúng chỗ *chỉ* cần ngôn ngữ/suy luận.

**④ Kiểu PURE-LLM (claude-for-legal)** — triển khai nhanh, playbook tốt; nhưng không engine, mọi thứ là kiến thức model gắn `[verify]`.
→ **TraLuat lấy:** cấu trúc playbook/workflow, **thay ruột** bằng engine grounding. Đúng chỗ tầng mặt tiền.

---

## 4. Khác biệt xử lý căn bản của TraLuat

1. **Phân tầng theo chi phí/tất định** (rule → ML-local → LLM): academic repo gọi LLM cho cả việc đáng ra chỉ cần rule (vd LegalGraphRAG gọi LLM per-element để kiểm áp dụng) → TraLuat chặn trước bằng rule `in_force`, rẻ hơn bậc.
2. **Local-first cho ML** (residency + bulk): repo dùng API ngoài (OpenAI embed) hoặc model nhỏ không quan tâm residency; TraLuat đẩy ML về local vì NĐ 356/2025 + chi phí.
3. **Một Postgres SoR + derived rebuildable**: repo hoặc polyglot prototype (PAKTON 4 kho) hoặc in-memory (LegalGraphRAG/LeSICiN) → không bền cho corpus quốc gia; TraLuat hợp nhất về Postgres, index là phái sinh.
4. **Hiệu lực + tenant xuyên suốt**: hai dimension *không repo nào có* → trục xử lý riêng của TraLuat, cắm vào cả retrieval, verify, storage.

---

## 5. Rủi ro thành thật (cái giá của hybrid)
- **Phức tạp hơn mọi repo đơn lẻ:** TraLuat phải vận hành 3 tầng model + bitemporal + tenant — không repo nào gánh cùng lúc. Đội mạnh gánh được, nhưng *tích hợp* là phần khó, không phải từng mảnh.
- **Chưa repo nào validate:** bitemporal, tenant-isolation, pgvector-ở-scale, graph-trên-Postgres → đây là phần phải tự chứng minh bằng acceptance test + benchmark, không có tiền lệ để copy.
- **Phân tầng sai tầng = mất lợi thế:** nếu lỡ để LLM làm việc của rule/ML (như academic repo), mất đúng ưu thế chi phí/tất định/audit. Kỷ luật "rule→ML→LLM" phải được enforce ở review code.

> **Một dòng:** các repo mỗi cái *giỏi một kiểu xử lý*; TraLuat **chọn đúng kiểu cho đúng việc** và thêm hai trục (hiệu lực, tenant) không ai có — đổi lại là gánh nặng tích hợp mà chỉ đội mạnh kham nổi.
