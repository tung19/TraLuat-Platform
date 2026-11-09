# TraLuat — Kế hoạch tham khảo repo (clone & study)

> Trả lời câu hỏi: **repo nào đáng kéo về đọc để lấy kiến trúc/tính năng, repo nào chỉ cần đọc paper/README, repo nào bỏ.**
> Giai đoạn hiện tại: **tham khảo, chưa thương mại hoá → license KHÔNG chặn gì.** License ghi lại một dòng để dành cho lúc bán.
> Nguồn: đọc trực tiếp repo qua GitHub API (file tree, README, source chính). Đọc kèm `docs/layered-architecture.md` để biết layer L1–L14.

---

## 0. Tóm tắt quyết định

| Repo | Verdict | Lấy gì | Map layer |
|---|---|---|---|
| **PAKTON** | 🟢 CLONE & STUDY (cao) | Backend FastAPI+Celery+SQLAlchemy thật; 3 agent Archivist/Interrogator/Researcher; retriever interface cắm được | L7, L8, L9, L5 |
| **Indigo** (+Cobalt, Bluebell) | 🟢 CLONE & STUDY (cao) | Mẫu FRBR Work/Expression + amendment → materialize expression + point-in-time | **L3** (bitemporal/AKN) |
| **LegalGraphRAG** | 🟢 CLONE & STUDY (cao) | Auditor hard-gate `verify_article()`+`prune_unsupported_cases()`; agent split Researcher→Auditor→Adjudicator | **L8, L6**, L3 |
| **L-MARS** | 🟢 CLONE & STUDY (cao) | Citation-Faithfulness Audit cấp-khẳng-định (6 lớp) + Faith-Search repair loop | **L6**, L8 |
| **LeSICiN** | 🟢 CLONE & STUDY (cao cho L3) | Đồ thị dị cấu Act/Chapter/Section/Fact + cây thứ bậc điều luật + multi-label linking | **L3** (bản án↔điều luật) |
| **LegalBench-RAG** | 🟢 CLONE & STUDY | Chunker giữ span + eval precision/recall cấp ký tự + sweep chiến lược retrieval | L4, L5, L13 (eval-gate) |
| **eyecite** | 🟢 CLONE & STUDY (mẫu pipeline) | Pipeline clean→tokenize→resolve→annotate; bài học tách data↔engine | L2 (trích dẫn), L6 |
| **ACAL** | 🟡 CLONE & STUDY (vừa) | Lập luận bipolar có điểm số → giải thích/khả-tranh-luận; 10 persona vai | L8 (explainability) |
| **AALawyer** | 🟡 READ PAPER | Dual retriever **SCR+APR** (symbolic statute + analogical precedent) | L3, L5 |
| **AgentCourt** | 🟡 READ PAPER | Vòng reflection + experience-memory DB tự cải thiện | L8, L14 (flywheel) |
| **AgentsCourt/SimuCourt** | 🟡 READ PAPER + skim prompt | Vòng Judge refine (analysis→record→refine→final) | L8 |
| **Claude for Legal** | 🟡 SKIM README | Cách phân rã workflow + phrasing playbook/finding | L9, L14 |
| **CaseLink** | 🔴 READ PAPER (nếu rảnh) | Đồ thị case↔case (ít thêm so với LeSICiN) | — |
| **USLM** | 🔴 SKIM (tham chiếu schema) | So sánh schema; AKN tốt hơn | — |

→ **Kéo về máy 7 repo "🟢"**; còn lại đọc paper/README là đủ.

---

## 1. Nhóm "CLONE & STUDY" — kéo về đọc kỹ

### PAKTON — gần kiến trúc TraLuat nhất
- **Là gì:** hệ multi-agent contract-QA trên LangGraph, có **backend production thật** (`PAKTON Framework/`: FastAPI + Celery + SQLAlchemy/Alembic), không chỉ code thí nghiệm.
- **Lấy gì:**
  - *Archivist* — parse → index song song, parser bám cấu trúc điều khoản (lightrag + vectordb).
  - *Interrogator* — vòng `generate_question → get_answer → refine_answer → write_report` → map thẳng **Review + omission** (L9).
  - *Researcher* — `query_extractor → tools → reranking → response_generator`, retriever cắm được bm25/hybrid/vectordb qua interface `base.py` → mẫu cho **L5**.
  - Provider abstraction (openai/bedrock/google/local) → mẫu cho **LLM Gateway (L7)**.
- **Cảnh báo:** README nói vài component có thể thiếu trong push hiện tại → kiểm lúc clone.

### Indigo (+ Cobalt, Bluebell) — chuẩn vàng cho L3 bitemporal/AKN
- **Lấy gì (remodel sang FastAPI/SQLAlchemy, KHÔNG chạy Django):**
  - `works.py` — Work theo FRBR URI + lifecycle ban hành/hiệu lực/bãi bỏ, `possible_expression_dates()`.
  - `amendments.py` — amending_work → amended_work theo ngày, post_save **materialize expression mới** (đúng bước versioning [6] của ta).
  - `documents.py` — Expression tại `expression_date`+ngôn ngữ, **point-in-time** qua `expression_date__lte`, hiệu lực cấp điều khoản.
  - **Cobalt** (serialize Akoma Ntoso) + **Bluebell** (parser AKN) dễ tái dùng hơn cả app chính.

### LegalGraphRAG — mẫu L8 + L6 tốt nhất
- **Lấy gì:** **Auditor hard-gate** — `verify_article()` kiểm tính áp dụng từng điều, rồi `prune_unsupported_cases()` loại án lệ không viện dẫn điều còn sống. Agent split **Researcher→Auditor→Adjudicator**. Charge-anchored retrieval (đoán tội danh → đi tới điều liên quan) → tương tự "đoán vấn đề pháp lý → điều luật".
- **Lưu ý:** KG của họ **4 tầng** (fact/feature/ontology/rule), không phải "3" như brief ghi. Luật TQ hình sự nhưng **kiến trúc trung lập pháp hệ**.

### L-MARS — mẫu grounding/verify tốt nhất
- **Lấy gì:** `VerifyAgent` — **Citation-Faithfulness Audit cấp-khẳng-định**, taxonomy 6 lớp (supported / partially / unsupported / unreachable / no_citation / error) + **Faith-Search repair loop** (thấy yếu → đi tìm lại). → đúng cổng (3) "hỗ trợ khẳng định" của ta ở **L6**.

### LeSICiN — blueprint L3 cho liên kết bản án↔điều luật
- **Lấy gì:** đồ thị dị cấu (Act/Chapter/Topic/Section/Fact) + **cây thứ bậc điều luật** + mạng fact↔section + **multi-label link prediction inductive**. Thứ bậc map ~1:1 **Bộ luật→Chương→Mục→Điều→Khoản**. Luật Ấn (IPC) nhưng framing "định danh điều luật áp dụng" chuyển sang dân luật VN tốt hơn mọi repo tòa-mô-phỏng.

### LegalBench-RAG — harness eval retrieval
- **Lấy gì:** mô hình ground-truth theo **span ký tự** → precision/recall cấp ký tự (deterministic); **chunker giữ nguyên span** (tái dựng doc chính xác — cần cho trích dẫn cấp điều khoản); sweep chunk×size×rerank×top_k. → **L4/L5 + cổng eval L13**.

### eyecite — mẫu pipeline trích dẫn
- **Lấy gì:** pipeline 4 bước `clean → tokenize → resolve → annotate` (span-preserving, Aho-Corasick). **Bài học lớn: tách data khỏi engine** — pattern DB (reporters-db, US) không chuyển được; **dựng pattern DB tiếng Việt** (Luật/NĐ/TT/Điều/Khoản/Điểm) rồi tái dùng *hình dạng* pipeline ở **L2**.

---

## 2. Nhóm "READ PAPER / SKIM" — không cần kéo về

- **ACAL** 🟡 — neuro-symbolic A-QBAF: LLM phát luận điểm + điểm, argumentation lưỡng cực tổng hợp ra quyết định có điểm số; 10 persona vai; có human-review. Giá trị: **giải thích & khả-tranh-luận** (L8). Demo-grade. (Tác giả VN — có thể liên hệ.)
- **AALawyer** 🟡 — repo rất lộn xộn (vendored LLaMA-Factory); **lấy khái niệm từ paper**: dual retriever **SCR** (symbolic statute) + **APR** (analogical precedent) → map L3/L5.
- **AgentCourt** 🟡 — dormant; một ý đáng lấy: **vòng reflection + experience-memory DB** tự cải thiện (`EMDB/db.py`) → flywheel L14.
- **AgentsCourt/SimuCourt** 🟡 — dormant, code rối; học **vòng Judge refine** từ paper + file prompt.
- **Claude for Legal** 🟡 — plugin/skill markdown; học **cách phân rã workflow + phrasing finding/playbook** để tái mã hoá vào agent (L9/L14).
- **CaseLink** 🔴 — đồ thị case↔case; thêm ít so với LeSICiN cho VN.
- **USLM** 🔴 — chỉ schema XSD US; AKN (Indigo/Cobalt) là mẫu chính tốt hơn.

---

## 3. Năm ưu tiên tái hiện (reimplement) cho TraLuat

Theo thứ tự giá trị, map vào layer:

1. **Auditor verify-then-prune + agent split** (từ LegalGraphRAG) → **L8 + L6**.
2. **Citation-Faithfulness Audit cấp-khẳng-định + Faith-Search repair** (từ L-MARS) → **L6**.
3. **Đồ thị bản án↔điều luật + cây thứ bậc + inductive linking** (từ LeSICiN) → **L3**.
4. **Dual retriever SCR + APR** (từ AALawyer) → **L3/L5**.
5. **Argument-strength scoring cho giải thích** (từ ACAL) → **L8**.

Cộng nền kỹ thuật: **PAKTON** cho khung agent+backend (L7/L8/L9), **Indigo/Cobalt/Bluebell** cho data model bitemporal/AKN (L3), **LegalBench-RAG** cho eval (L13), **eyecite** cho pipeline trích dẫn (L2).

---

## 4. Các đính chính từ đợt soi repo (ghi lại để khỏi sai về sau)

- **Indigo là LGPL-3.0** (copyleft nhẹ), không phải GPL-3; không repo nào trong họ Indigo là AGPL.
- **LegalGraphRAG KG có 4 tầng** (fact/feature/ontology/rule), brief ghi "3".
- **ACAL là Canadian AI 2026**, không phải ACL 2026. Repo **ACL 2026 Main** là **AALawyer**.
- **L-MARS là poster workshop** (ICML AI4Law), không phải main-conf.
- arXiv **2605.28120** (LegalGraphRAG) **chưa xác minh** — README comment-out link arXiv, trỏ ResearchGate; kiểm trước khi trích.
- **Không repo nào là tiếng Việt / dân-luật-native.** Repo *statute-centric* (LeSICiN, AALawyer-SCR, LegalGraphRAG charge-anchored) chuyển sang VN tốt nhất; repo *courtroom-sim* (AgentCourt, AgentsCourt) chuyển kém nhất.
- Chỉ **LegalGraphRAG và L-MARS** vừa còn active vừa engineer sạch.

---

## 5. Gợi ý thao tác clone (khi bạn muốn)

```bash
mkdir -p refs && cd refs
# Nhóm kéo về đọc kỹ (đặt mỗi repo một thư mục riêng, KHÔNG chạy trực tiếp)
git clone https://github.com/petrosrapto/PAKTON
git clone https://github.com/laws-africa/indigo
git clone https://github.com/laws-africa/cobalt
git clone https://github.com/laws-africa/bluebell
git clone https://github.com/XMUDeepLIT/LegalGraphRAG
git clone https://github.com/boqiny/L-MARS
git clone https://github.com/Law-AI/LeSICiN
git clone https://github.com/zeroentropy-ai/legalbenchrag
git clone https://github.com/freelawproject/eyecite
```
> Lưu ý an toàn: đây là code tải về — đọc trước khi chạy; nếu cần chạy thử thì chạy trong môi trường cô lập, không chạy interpreter/build từ trong thư mục repo. Giai đoạn này mục tiêu là **đọc để học**, không phải tích hợp.
