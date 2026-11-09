# TraLuat — Audit tích hợp (migration-fit): ghép repo có work well không?

> Trả lời: **"ghép mỗi repo một ít" có work well không khi migrate về một kiến trúc?**
> Nguồn: `research_notes/Repo deep read/integration_fit_audit.md` (đọc deps/khung thật trong `refs/`, file-cited). Đọc kèm `CONTRIBUTING.md`, `docs/specs/w5-backend.md`.

---

## 0. Kết luận một dòng
**Ghép *PATTERN* onto MỘT schema canonical (W2) + MỘT runtime (FastAPI+Celery+SQLAlchemy) = WORK WELL.** **Glue *CODEBASE* (import nhiều repo rồi wire) = VỠ.** Mối nối an toàn *duy nhất* = schema canonical + các interface (`TemporalRepository`/`RetrievalService`/`GroundingService`/`LLMGateway`). Chỉ **đúng 2 repo pip-merge được**: **eyecite (BSD) + cobalt (LGPL, pure Python)**; còn lại là remodel / rebuild / service riêng.

---

## 1. Bảng seam → verdict
| Repo | Lấy gì | Verdict | Rủi ro nếu glue thô |
|---|---|---|---|
| **PAKTON** | skeleton runtime + mẫu agent | **WIRE-AS-LIB** (runtime) + **REMODEL** (engine) | `retrieve(query,**kwargs)` không có `as_of`/tenant; LangChain `Document` blob ≠ `chunk`/`unit_version`; không tenant/RBAC |
| **Indigo** | mẫu FRBR/bitemporal/point-in-time | **REMODEL-PATTERN** | **Django 5 không chung process với FastAPI**; AKN-XML-trong-cột ≠ `unit_version` quan hệ |
| **cobalt** | `FrbrUri.parse` (canonical ID) | **WIRE-AS-LIB** | pure Python (re/iso8601/lxml) — ok; **ép Python ≥3.12 + LGPL** |
| **bluebell** | ý tưởng eId ổn định | **REMODEL-PATTERN** | Rust+pyo3 (abi3-py312), LGPL — chỉ cần *ý tưởng*, không nhúng |
| **eyecite** | pipeline trích dẫn 4 bước | **WIRE-AS-LIB** (sạch nhất) + **REBUILD-FOR-VN** | BSD-2, ≥3.10, deps nhẹ; nhưng `reporters_db` US → dựng pattern VN |
| **legalbenchrag** | harness eval + chunker | **RUN-AS-SERVICE** | **langchain 0.2 đụng 0.3 của PAKTON** → không chung env; MIT |
| **LeSICiN** | mẫu linking inductive | **REBUILD-PATTERN** | **no-LICENSE** + torch_sparse không co-install |
| **LegalGraphRAG** | Auditor hard-gate | **REBUILD-PATTERN** | **no-LICENSE** + NetworkX in-mem |
| **L-MARS** | verifier 6 lớp + faith-search | **REBUILD-PATTERN** | **no-LICENSE** |

---

## 2. Dependency reality (bằng chứng — đây là chỗ "work well" hay không)
- **Python floor tách bộ:** PAKTON 3.11.11 (`API/Dockerfile:10`); cobalt/bluebell/indigo/legalbenchrag cần **≥3.12**; eyecite ≥3.10. → **pin runtime chuẩn 3.12.**
- **🔴 Rủi ro lớn nhất — bức tường langchain 0.2 vs 0.3:** PAKTON `0.3.20`/core `0.3.41` vs legalbenchrag `0.2.13`/`0.2.30` → **không thể cùng một env** → legalbenchrag phải chạy **service riêng** (hoặc chỉ port ý tưởng, không import).
- **pydantic:** tất cả **v2** → *không* có xung đột v1/v2 (lo lắng này không xảy ra); chỉ lệch pin (2.8 vs 2.10).
- **torch:** PAKTON reranker torch 2.9 vs **LeSICiN torch_sparse** (CUDA/ABI-locked, không co-install) vs LegalGraphRAG ≥2.6 → thêm lý do LeSICiN chỉ **rebuild pattern**.

---

## 3. Năm thứ VỠ nếu glue codebase (đừng làm)
1. **Một `requirements` hợp nhất bất khả thi** (đụng pin langchain).
2. **Django + FastAPI không chia sẻ process/ORM** (Indigo).
3. **torch_sparse không cài được** cạnh torch của PAKTON.
4. **3 repo no-LICENSE không được copy** (LeSICiN/LegalGraphRAG/L-MARS).
5. **Mọi retrieval path lift nguyên đều query GLOBAL, không `as_of`/tenant** → *âm thầm phá* bất biến hiệu lực + cô lập tenant (nguy hiểm nhất vì *im lặng*).

---

## 4. Chiến lược migration an toàn (để work well)
1. **Một runtime, pin Python 3.12** (FastAPI+Celery+SQLAlchemy skeleton của PAKTON là xương).
2. **Một schema canonical (W2) = mối nối duy nhất.** Mọi dữ liệu từ repo nào cũng *map vào* schema này, không giữ format gốc (AKN-XML / LangChain Document / torch graph đều phải transform).
3. **Mọi truy xuất qua interface có `as_of` + `tenant`** — KHÔNG lift thẳng `retrieve(query,**kwargs)` của PAKTON. Đây là chỗ dễ "work" trên demo nhưng *sai* trên production.
4. **Pip-merge chỉ 2:** eyecite (sau khi thay pattern VN) + cobalt. Cô lập bằng interface, pin version.
5. **legalbenchrag = service eval riêng** (hoặc port ý tưởng span/chunker/diskcache sang code ta — khỏi kéo langchain 0.2).
6. **3 repo no-LICENSE: đọc để học, viết lại sạch** (clean-room) — không copy dòng nào.
7. **Phần ngôn ngữ (US/Trung/Ấn) rebuild cho VN** — không migrate trực tiếp pattern DB/model.
8. **Acceptance test tích hợp:** mỗi seam có test chứng minh dữ liệu map đúng vào canonical schema + truy xuất mang `as_of`/tenant (không global).

---

## 5. Trả lời thẳng "có đảm bảo work well không?"
- **CÓ — nếu** đi theo pattern-merge (mục 4): kiến trúc ta thiết kế *đã đúng cách*, các interface + canonical schema chính là lớp chống-vỡ.
- **KHÔNG — nếu** cố glue codebase: vỡ ở 5 chỗ mục 3, và nguy hiểm nhất là **retrieval global lọt qua** (chạy được nhưng sai hiệu lực/tenant — lỗi im lặng).
- **Việc cụ thể cần làm ngay** khi "ghép": với mỗi mảnh lấy về, phân loại đúng verdict (bảng §1), và **viết transform mapping sang schema W2** + **test seam** — đừng để mảnh nào giữ data-model/retrieval gốc.
