# TraLuat — Kiến trúc nền tảng

> Tài liệu kiến trúc cho engine pháp lý AI portable, nạp lát Việt Nam (FDI) trước.
> Đọc kèm: `docs/roadmap.md`, `reports/Legal AI engine prior art.md`, `reports/Vietnam judgment and precedent engine.md`.
> Trạng thái: bản thiết kế (design), chưa code. Mọi số hiệu văn bản pháp luật trong tài liệu cần đối chiếu văn bản gốc trước khi hiện thực.

---

## 0. Một câu định nghĩa

TraLuat là **engine tạo ra sản phẩm pháp lý đã hoàn thành** (hợp đồng đã rà, báo cáo tuân thủ, thẩm định bản án), **trung lập về hệ thống pháp luật** (thêm một nước = cấu hình, không viết lại), trong đó **mọi output đều neo tới điều–khoản + ngày hiệu lực và được một con người có chuyên môn ký duyệt.**

Khác biệt sống còn không nằm ở LLM — ai cũng gọi được API. Nó nằm ở **tầng dữ liệu hiệu lực-thời-gian** và **hợp đồng đầu ra có bảo đảm trích dẫn**. Kiến trúc này được tổ chức để bảo vệ đúng hai thứ đó.

---

## 1. Năm nguyên tắc thiết kế (ràng buộc mọi quyết định bên dưới)

1. **Portable-by-design, VN-first-by-load.** Engine không biết "luật Việt Nam"; nó biết "một jurisdiction được mô tả bằng cấu hình khai báo". VN là jurisdiction đầu tiên được nạp. Không nhúng giả định VN vào lõi.
2. **Effectivity-first (hiệu lực là công dân hạng nhất).** Mọi quy phạm, án lệ, bản án đều mang khoảng thời gian hiệu lực. Truy vấn mặc định là "tại ngày T". Không có khái niệm "văn bản" tách khỏi "phiên bản tại thời điểm".
3. **Grounded-by-default (hợp đồng đầu ra).** Engine **không được** trả lời nếu không neo được về điều–khoản có thật + còn hiệu lực. Không neo được thì **abstain** (từ chối trả lời) chứ không bịa. Đây là hợp đồng kỹ thuật, không phải khuyến nghị.
4. **Human-in-the-loop, không phải human-optional.** Output là *bản nháp để chuyên gia duyệt*, có audit trail đầy đủ. Đặc biệt với năng lực thẩm định bản án — nơi tuyên bố "sai" là tuyên bố nặng.
5. **Reuse > Build, nhưng Build đúng moat.** Tái sử dụng tối đa thứ có license sạch (Apache/MIT/BSD/MPL/CC BY 4.0). Chỉ tự xây ở ba moat không ai giải: đồ thị hiệu lực, phát hiện bỏ sót gắn-thời-điểm, song ngữ căn chỉnh khái niệm (+ năng lực thẩm định bản án).

---

## 2. Tổng quan bốn tầng

```
┌───────────────────────────────────────────────────────────────────────┐
│  TẦNG 4 — TRUST & GOVERNANCE                                           │
│  HITL · audit trail · confidence/abstention · tenant isolation ·       │
│  tuân thủ PDP (NĐ 356/2025) · gắn nhãn AI (Luật 71/2025)              │
├───────────────────────────────────────────────────────────────────────┤
│  TẦNG 3 — WORKFLOW & REASONER                                          │
│  Review · Draft · Assistant · Judgment Analysis · Compliance Diff      │
│  Reasoner đa vai (Luật sư ⇄ Kiểm sát ⇄ Thẩm phán ⇄ Bộ ngành)          │
│  + Auditor hard-gate (kiểm trích dẫn + hiệu lực + thẩm quyền)          │
├───────────────────────────────────────────────────────────────────────┤
│  TẦNG 2 — RETRIEVAL & GROUNDING                                        │
│  RAG cấp điều–khoản · hiệu lực-aware · hybrid · multi-hop ·            │
│  Citation Verifier (có thật + còn hiệu lực + hỗ trợ khẳng định)        │
├───────────────────────────────────────────────────────────────────────┤
│  TẦNG 1 — DATA & SCHEMA  (moat lõi)                                    │
│  Schema chuẩn trung lập pháp hệ · đồ thị hiệu lực bitemporal ·         │
│  đồ thị quan hệ quy phạm · án lệ · bản án · term base song ngữ         │
│  ← Pipeline nạp: OCR → cấu trúc hoá → trích metadata → versioning      │
└───────────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc phụ thuộc:** tầng trên chỉ đáng tin khi tầng dưới vững. Reasoner đa vai (tầng 3) xây **sau** khi Data + Grounding (tầng 1–2) đã qua benchmark. Xây tòa trước khi có móng = ảo giác có cấu trúc.

---

## 3. Tầng 1 — Data & Schema (moat lõi, "một kiến trúc, một schema")

### 3.1 Schema chuẩn — trung lập pháp hệ

Mô hình dữ liệu canonical, **không nhúng đặc thù VN**, căn chỉnh theo chuẩn mở để portable:

- **Khung tài liệu:** Akoma Ntoso (OASIS LegalDocML) cho cấu trúc văn bản; **FRBR/LRMoo** tách `Work → Temporal Version → Language Version → Manifestation`. Chính lớp *Temporal Version* và *Language Version* là nơi hiệu lực-thời-gian và song ngữ gắn vào.
- **Định danh & ngày:** mô phỏng **ELI** — mỗi đơn vị có slot `{point-in-time}`, và các mốc `date_ban_hành`, `date_hiệu_lực`, `date_áp_dụng`, `date_hết_hiệu_lực` (phân biệt "ngày hiệu lực" vs "ngày áp dụng" đúng như luật VN).
- **Quy tắc:** **LegalRuleML** cho các quy phạm mang tính deontic (nghĩa vụ/cấm/cho phép/quyền) + hiệu lực của quy tắc — nền cho omission detection và compliance.

**Các thực thể cốt lõi:**

| Thực thể | Vai trò | Ghi chú moat |
|---|---|---|
| `Jurisdiction` | Một hệ thống pháp luật (VN, rồi SG, …) | Nền portability |
| `IssuingAuthority` + thứ bậc | Cơ quan ban hành + cấp thẩm quyền | Bắt buộc cho giải xung đột *lex superior* |
| `LegalDocument` | VBQPPL (có `type` trong tháp thứ bậc) | Luật/Nghị định/Thông tư/VB địa phương… |
| `StructuralUnit` (đệ quy) | Phần→Chương→Mục→**Điều→Khoản→Điểm** | Đơn vị neo trích dẫn nhỏ nhất |
| `TemporalVersion` | Phiên bản của một đơn vị theo thời gian | **Moat 1** |
| `NormRelation` | Cạnh: cites / amends / repeals / replaces / guides / conflicts / hierarchy | **Moat 1** (đồ thị quan hệ quy phạm) |
| `Precedent` (Án lệ) | Tình huống + giải pháp + điều luật diễn giải | Tự hủy khi điều luật nền đổi (Điều 9(1) NQ 04/2019) |
| `Judgment` (Bản án) | Tòa, ngày, tình tiết, phán quyết, viện dẫn | Đầu vào cho Judgment Analysis |
| `Concept` / `Term` | Node khái niệm ↔ thuật ngữ VN/EN + loại tương đương | **Moat 3** (full/partial/non-equivalent) |
| `ClauseType` | Taxonomy điều khoản hợp đồng (căn chỉnh CUAD 41 loại) | Nền omission |
| `RequiredClauseRule` | "Hợp đồng loại X, tại jurisdiction J, ngày T → bắt buộc có điều khoản Y" | **Moat 2** (bỏ sót gắn-thời-điểm) |

### 3.2 Lưu trữ: bitemporal + graph + vector (hybrid)

- **Nguồn sự thật (source of truth): kho bitemporal.** Hai trục thời gian: *valid-time* (khoảng luật có hiệu lực) và *transaction-time* (khi hệ thống ghi nhận/biết). Bitemporal giải đúng bài "sửa đổi hồi tố" và "sau này mới biết ngày hiệu lực khác" — version một trục không làm được. Ứng viên: **XTDB (MPL-2.0)**; hoặc Postgres bitemporal (SQL:2011) nếu muốn một hệ.
- **Đồ thị quan hệ quy phạm + citation graph:** graph store (Neo4j theo brief, hoặc graph layer trên Postgres) để multi-hop (dẫn chiếu, thứ bậc, sửa đổi).
- **Vector index:** embedding đa ngữ **bge-m3 (MIT)** trên chunk cấp điều–khoản (kèm header cấu trúc) — phục vụ retrieval hybrid.

> Ba kho này là **chỉ mục phái sinh của cùng một schema canonical**, không phải ba nguồn sự thật. Pipeline ghi vào kho bitemporal, rồi derive graph + vector.

### 3.3 Pipeline nạp dữ liệu ("khâu xử lý data theo 1 kiến trúc, 1 schema")

```
Nguồn gốc hợp pháp (vbpl.vn, Công báo, anle/congbobanan — theo thỏa thuận)
   │
   ▼
[1] Ingest & phân loại     → nhận diện loại văn bản, khử trùng lặp, lưu bản gốc + hash
[2] OCR / Parse            → PDF scan→text (OCR tiếng Việt có dấu + bảng); PDF-text/DOC/HTML→text
[3] Cấu trúc hoá           → tách Phần/Chương/Điều/Khoản/Điểm theo Akoma Ntoso
[4] Trích metadata         → số hiệu, ngày ban hành, NGÀY HIỆU LỰC, cơ quan, căn cứ
[5] Trích quan hệ          → "Điều X sửa đổi/bãi bỏ bởi…" → cạnh NormRelation   ★ moat
[6] Versioning & hợp nhất  → dựng TemporalVersion; tái dựng văn bản tại ngày T   ★ moat
[7] Căn chỉnh song ngữ     → map điều–khoản VN ↔ EN; dựng Concept/Term           ★ moat
[8] Indexing               → chunk + embed (bge-m3) + nạp graph
   │
   ▼  (checkpoint con người ở [5][6][7] — độ tin thấp vào hàng chờ duyệt)
Schema canonical  →  chỉ mục bitemporal + graph + vector
```

Bước **[5][6]** chính là moat #1 và là phần "không ai giải" (xác nhận qua research). Bước **[2]** là nơi chi phí ẩn lớn nhất nếu 4TB nhiều scan.

### 3.4 Taxonomy các trụ dữ liệu cần phủ

Xem chi tiết trong hội thoại audit; tóm tắt nhóm bắt buộc: **VBQPPL (gồm Thông tư + VB địa phương)**, **Án lệ + Bản án**, **Công văn/Công báo/Thủ tục hành chính**, **Điều ước quốc tế & FTA** (cho FDI), **Dữ liệu tham chiếu** (cơ quan/thẩm quyền/đơn vị hành chính/biểu thuế), **Hợp đồng mẫu**, **Song ngữ**. Bốn tầng *phái sinh* (hiệu lực, liên kết bản án↔điều luật↔án lệ, term base, chỉ mục) **không có sẵn trong data thô — phải tự dựng.**

---

## 4. Tầng 2 — Retrieval & Grounding

- **RAG cấp điều–khoản:** chunk theo đơn vị cấu trúc + header, không cắt mù theo độ dài.
- **Hybrid retrieval:** BM25 + dense (bge-m3) hợp nhất bằng RRF + neural reranker. (Pattern này thắng cho tiếng Việt — đa ngữ sẵn.)
- **Hiệu lực-aware filter:** mọi truy xuất mang tham số `as_of_date`; mặc định chỉ trả đơn vị *còn hiệu lực tại ngày đó*. Đây là điểm khác biệt với RAG thường.
- **Multi-hop:** đi theo NormRelation + citation graph (dẫn chiếu, văn bản hướng dẫn, thứ bậc).
- **Citation Verifier (hợp đồng đầu ra):** mỗi trích dẫn phải qua 3 cổng —
  1. **Có thật** (đơn vị tồn tại trong KB),
  2. **Còn hiệu lực** tại `as_of_date` (tra kho bitemporal),
  3. **Hỗ trợ khẳng định** (NLI/entailment giữa câu trả lời và văn bản nguồn).
  Trượt bất kỳ cổng nào → hạ confidence hoặc abstain. *Lưu ý: không có công cụ mở nào làm cổng (3) ở mức khớp-nguyên-văn cho statute VN — phải tự xây; eyecite là US-only, không dùng được.*

---

## 5. Tầng 3 — Workflow & Reasoner

### 5.1 Workflow (các tính năng tạo "việc đã xong")

| Workflow | Vào → Ra | Moat dùng |
|---|---|---|
| **Review** | Hợp đồng → rủi ro + **điều khoản bỏ sót** + checklist tuân thủ (có trích dẫn) | #2 |
| **Draft** | Yêu cầu → hợp đồng/văn bản **song ngữ** có trích dẫn | #3 |
| **Assistant** | Câu hỏi → trả lời có trích dẫn + ngày hiệu lực, song ngữ | #1 |
| **Judgment Analysis** | Bản án → *đáng ra xử thế nào · đúng/sai · căn cứ điều luật · neo án lệ* | bản-án |
| **Compliance Diff** | Tình huống xuyên biên giới → khác biệt nghĩa vụ giữa jurisdiction | #1 + portability |

**Omission detection (moat #2)** chạy kiểu hai lượt: *retrieval-rồi-review* — tìm điều khoản nếu có; nếu không thấy, đối chiếu `RequiredClauseRule` tại ngày T để flag "thiếu". Điểm khác biệt sống còn với mọi vendor: so với **luật bắt buộc tại thời điểm T**, không chỉ so với playbook tĩnh do người dùng cấu hình.

**Judgment Analysis (năng lực khác biệt nhất)** dùng doctrinal hook **"áp dụng-hoặc-giải-thích"** án lệ (NQ 04/2019): nếu có án lệ đúng tình huống mà bản án không áp dụng và không giải thích → điểm vênh *chính danh*. Định vị: **second-opinion có neo cho chuyên gia**, không phải máy xử thay tòa.

### 5.2 Reasoner đa vai (xây SAU nền) — Luật sư ⇄ Kiểm sát ⇄ Thẩm phán ⇄ Bộ ngành

Bốn vai tranh biện, mỗi vai một động cơ; điểm sống sót qua tranh biện mới là kết luận. Pattern tái hiện từ research (**LegalGraphRAG**: Researcher→Auditor→Adjudicator; **AALawyer**: analogical precedent retrieval) — **viết lại sạch trong nhà** vì các repo đó không có LICENSE. Vendor trực tiếp được: **PAKTON (Apache-2.0)** cho contract-QA đa agent.

**Auditor là cổng cứng bắt buộc:** trước khi bất kỳ vai nào phát ngôn ra ngoài, Auditor kiểm **trích dẫn + thẩm quyền + ngày hiệu lực**. Đây là cách biến "4 LLM tự tin" thành "4 vai bị ràng buộc bởi luật thật".

---

## 6. Tầng 4 — Trust & Governance

- **Confidence + abstention:** mỗi output có điểm tin cậy; dưới ngưỡng → từ chối/đẩy lên người.
- **Audit trail:** mỗi khẳng định ↔ nguồn + ngày + dấu vết truy xuất (reproducible). Bắt buộc cho môi trường pháp lý.
- **HITL queue:** hàng chờ duyệt cho mục độ tin thấp; chữ ký người duyệt lưu lại.
- **Tenant isolation:** cô lập dữ liệu khách; **không dùng dữ liệu khách để huấn luyện**.
- **Tuân thủ VN (ánh xạ trực tiếp sang kiến trúc, không phải checkbox đạo đức):**
  - **NĐ 356/2025/NĐ-CP** (hiệu lực 1/1/2026) — xử lý trên cloud nay có thể tính là chuyển dữ liệu xuyên biên giới → đẩy về **hosting trong VN/khu vực + zero-retention + hồ sơ đánh giá tác động chuyển dữ liệu**.
  - **Luật AI 134/2025/QH15** (hiệu lực 1/3/2026) — điều chỉnh theo *vai trò* (provider/deployer) → cần xác định nghĩa vụ theo vai.
  - **Luật 71/2025 (CNCNS)** — **gắn nhãn nội dung do AI tạo** từ 1/1/2026 → mọi output máy sinh phải có nhãn.
  - *Mọi số hiệu/ngày trên lấy từ tóm tắt hãng luật — **phải đối chiếu văn bản gốc** trước khi code chạm dữ liệu thật.*

---

## 7. Portability — "thêm một nước = cấu hình"

Khác biệt kiến trúc phòng thủ được (không vendor nào công bố): **jurisdiction là cấu hình khai báo**, không phải code. Một `JurisdictionPack` gồm:

- Tháp thứ bậc văn bản + quy tắc thẩm quyền (cho lex superior/posterior/specialis).
- Ngữ pháp trích xuất quan hệ sửa đổi/bãi bỏ (mẫu câu đặc thù ngôn ngữ).
- Lịch hiệu lực & quy tắc áp dụng/hồi tố.
- Nguồn dữ liệu + quyền sử dụng.
- Term base song ngữ.
- (Nếu có) hệ thống án lệ + cổng bản án.

Lõi engine (bitemporal, graph, retrieval, grounding, workflow) **không đổi**. VN là pack đầu tiên; ASEAN là phép thử portability (roadmap Phase 5).

---

## 8. Tech stack & bản đồ REUSE / BUILD / INTEGRATE

**Stack:** Python · FastAPI · kho bitemporal (XTDB/Postgres) + graph (Neo4j) + vector (pgvector/Qdrant, bge-m3) · LLM qua API + lớp grounding/verify tự xây · multi-tenant.

| REUSE (license sạch) | BUILD (moat — tự xây) | INTEGRATE (tier-3, không đóng moat) |
|---|---|---|
| Chuẩn: Akoma Ntoso, ELI, LegalRuleML, FRBR/LRMoo | Trích xuất sửa đổi/bãi bỏ + tái dựng điều tại ngày T + giải xung đột quy phạm (moat 1) | **Claude for Legal** (Apache-2.0) — fork playbook/checklist/luồng review vào tầng workflow |
| XTDB (MPL-2.0); bge-m3, LegalBench-RAG (MIT); CUAD/ContractNLI/MAUD (CC BY 4.0) | Omission so với luật bắt buộc tại ngày T (moat 2) | Lấy *cấu trúc* skill (markdown+JSON), thay ruột bằng grounding của mình |
| ViLegalBERT (Apache-2.0, "research", dùng thận trọng) | Term base + căn chỉnh khái niệm VN-EN + verify khớp-nguyên-văn (moat 3) | Không dùng như backend — nó chạy trên Claude Cowork, không phải FastAPI |
| PAKTON (Apache-2.0) cho contract-QA đa agent | Judgment Analysis + liên kết bản án↔điều luật↔án lệ + trích dẫn định dạng VN | — |
| Schema nhãn ALQAC 2026 (A_WIN/PARTIAL/B_WIN + điều luật-chứng cứ) | Reasoner đa vai + Auditor hard-gate (viết lại từ pattern, repo gốc no-LICENSE) | — |

**Tuyệt đối tránh:** repo no-LICENSE (AgentCourt, LegalGraphRAG, L-MARS, ACAL — chỉ đọc để học); dataset NC (VLQA — chỉ benchmark nội bộ); dữ liệu aggregator (thuvienphapluat/luatvietnam/lawnet — cấm tái dùng).

---

## 9. Hợp đồng đầu ra (mọi câu trả lời phải thoả)

Mỗi output của engine mang kèm:
1. **Trích dẫn** tới điều–khoản–điểm cụ thể (không phải "theo Luật X" chung chung).
2. **Ngày hiệu lực** của mỗi căn cứ + `as_of_date` đã dùng.
3. **Điểm tin cậy** + cờ abstain nếu không neo được.
4. **Bản song ngữ** ngang hàng (với Review/Assistant/Draft).
5. **Nhãn nội dung do AI tạo** (Luật 71/2025) + bút tích người duyệt (HITL).

Đây là bất biến (invariant) của hệ thống — nếu một workflow không giữ được hợp đồng này, nó chưa được phép phát hành.
