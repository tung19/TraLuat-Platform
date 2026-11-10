# ADR-0001 — Graph engine: Postgres CTE vs Neo4j vs Apache AGE (deep audit)

> Trạng thái: **Quyết định** · Bối cảnh: người dùng hỏi "xu hướng dùng Neo4j, sao không?". Audit phản biện cả 3 hướng + chính đề xuất "Neo4j projection" của tôi.

## 1. Workload đồ thị THẬT (đo, không đoán)
- **Node:** ~ số điều–khoản (vài trăm nghìn khi full corpus) + văn bản. **Edge:** `norm_relation` (cites·amends·repeals·replaces·guides·conflicts·hierarchy).
- **Query thực tế đang chạy:** (a) reachability dẫn-chiếu/hướng-dẫn **1–3 hop** (`multihop`, R_chg), (b) `neighborhood` 1-hop cho viz, (c) conflict-pair (FR-41). **KHÔNG** dùng: GDS (PageRank/community), variable-length path sâu, pattern-match phức tạp.
- **Tính chất quyết định:** mọi edge query **lọc `effective_date ≤ as_of`** (bitemporal) và chạy **cùng snapshot** với kho "văn bản tại ngày T".

## 2. Steelman "dùng Neo4j" (công bằng — không gạt)
Thật sự thắng ở: **Cypher** biểu đạt · **GDS** (centrality tìm luật "landmark", community gom lĩnh vực, weighted shortest-path) · **variable-length path** `[:CITES*1..5]` · **GraphRAG** graph-guided retrieval · **Bloom** viz · hệ sinh thái + **nhân lực** (trend = dễ tuyển). Đây là lý do chính đáng cho sản phẩm **graph-native**.

## 3. Phản biện — kể cả đề xuất "Neo4j làm projection" của chính tôi
> 🔴 **F1 — Cross-store consistency PHÁ bất biến bitemporal.** Một request suy luận đọc **kho bitemporal (Postgres)** + **đồ thị (Neo4j)**. Tôi vừa sửa bug **B1 (pin known_as_of)** để chunk và gate thấy *cùng một snapshot tx-time*. Với 2 store, **không thể pin snapshot nguyên tử** → cửa sổ bất-nhất: đồ thị có thể trỏ edge mà kho chưa/đã đổi. Với "văn bản tại ngày T" (moat #1) đây là **regression đúng cái vừa vá**.
> 🔴 **F2 — Projection = vẫn có bug stale (Round-7 lặp lại, nặng hơn).** L4 pgvector từng để **chunk stale** sau amendment/R5 (đã vá bằng rebuild per-doc *trong cùng DB/transaction*). Neo4j projection ở **DB tách** → stale khó vá hơn: sync async có cửa sổ trễ; sync nguyên tử = **dual-write** (2PC/saga) — đúng thứ tôi bảo tránh. "Rebuild được" không xoá được cửa sổ bất-nhất.
> 🟠 **F3 — Tenant/residency phải làm LẠI.** Postgres đã có FORCE RLS + residency VN (NĐ 356). KB luật là *public shared* nên graph công KHÔNG cần RLS — OK. Nhưng nếu sau này có **graph riêng của khách** (quan hệ hợp đồng), Neo4j tenant-isolation (RBAC Enterprise) yếu hơn RLS → bề mặt rò chéo mới.
> 🟠 **F4 — Lợi ích LATENT, chi phí NGAY.** GDS/deep-path/Cypher-ergonomics đều là nhu cầu **tương lai**; sync + 2 ops surface + consistency window là chi phí **tức thì**. Lắp hạ tầng cho nhu cầu chưa tới = premature.
> 🟡 **F5 — "Trend" ≠ "requirement".** Neo4j phổ biến ở sản phẩm *graph-native* (social/fraud/recommendation — đồ thị LÀ sản phẩm). Ở đây đồ thị là **index phụ trên SoR bitemporal pháp lý**. Cargo-cult stack = thêm rủi ro không có payoff tương ứng.

## 4. Lựa chọn thứ 3 bị bỏ quên: **Apache AGE** (Cypher TRONG Postgres)
Nếu cái muốn là **Cypher + GraphRAG + trend-alignment** mà KHÔNG muốn dual-store:
- **AGE** = extension graph của Postgres → **một DB, một transaction, một SoR**. Có Cypher. **F1/F2/F3 biến mất** (không cross-store, không sync, dùng chung RLS/residency/pin-snapshot).
- Thua Neo4j ở: GDS library bớt phong phú, viz (Bloom) không có, scale cực lớn. Nhưng với workload §1, **AGE ≻ Neo4j** cho tới khi có trigger thật.

## 5. Quyết định
1. **GIỮ `PostgresGraphStore` (CTE)** làm mặc định — đủ cho reachability 1–3 hop hiện tại, zero-dep, cùng snapshot bitemporal.
2. **Dựng `GraphStore` port NGAY** (hygiene, rẻ): `multihop`/`neighborhood`/`cypher` — để đổi engine không đụng Researcher/API `/graph` (như bge-m3/XNLI đã cắm). *Đây là phần tôi code.*
3. **KHI có Cypher/GraphRAG nhu cầu → ưu tiên AGE** (một SoR) trước Neo4j.
4. **KHÔNG thêm Neo4j bây giờ.** Chỉ adopt khi chạm **trigger đo được** (§6).

## 6. Decision triggers (adopt Neo4j/AGE khi — và chỉ khi)
- [ ] Cần **GDS thật**: PageRank "luật trọng tâm" · community lĩnh vực · weighted influence path (không chỉ reachability).
- [ ] Multi-hop **> 5 hop** hoặc pattern-match phức tạp mà CTE thành viết-tay khổ + chậm (benchmark trước).
- [ ] **GraphRAG** nơi cấu trúc đồ thị *lái* context retrieval (không chỉ tìm điều liên quan).
- [ ] CTE thành **bottleneck đo được** (p95 > SLO trên corpus thật) — profile, đừng đoán.
- Chạm ≥1 trigger → ưu tiên **AGE** (giữ 1 SoR); chọn **Neo4j** chỉ khi cần GDS/viz/scale mà AGE không kham + chấp nhận F1/F2 (chạy projection read-only + cột-mốc consistency rõ ràng).

## 7. Hệ quả
- Không nợ kiến trúc (một SoR, pin-snapshot bitemporal nguyên vẹn).
- `GraphStore` port = sẵn sàng cắm AGE/Neo4j khi trigger tới — rẻ, không khoá tương lai.
- Rủi ro đã nêu (F1/F2) được *document* làm điều kiện bắt buộc giải trước khi bật projection.
