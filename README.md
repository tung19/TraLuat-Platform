# TraLuat — Legal-AI Engine cho Việt Nam

> **Engine tạo ra sản phẩm pháp lý đã hoàn thành** (hợp đồng đã rà, báo cáo tuân thủ, thẩm định bản án), **trung lập hệ thống pháp luật** (thêm nước = cấu hình), nạp lát **FDI Việt Nam** trước. Mọi output neo tới điều–khoản + ngày hiệu lực, có người ký duyệt.
>
> Trạng thái: **đã có engine và kiểm thử tích hợp; chưa sẵn sàng production.** Hướng dẫn kiến trúc bên dưới cần đọc cùng mã hiện tại và báo cáo audit.

Đã nối **chỉ mục FTS + BGE → model Ollama local → kiểm trích dẫn/NLI → API và nguồn trên giao diện**. Xem [cấu hình, reindex sau nạp dữ liệu và kết quả kiểm thử 11/11/2026](docs/local-ai-wiring-2026-11-11.md). Chưa đặt cấu hình thì AI ở chế độ `disabled`; Echo chỉ dùng khi chọn `demo`.

> 👩‍💻 **Dev bắt đầu code?** Mở **[`CONTRIBUTING.md`](CONTRIBUTING.md)** (START HERE) — đọc gì · code từ file nào · thứ tự khởi công · Definition of Done. *(File `TraLuat-KienTruc.docx` chỉ để đọc tổng quan, KHÔNG code từ đó.)*

---

## 1. Khác biệt (vì sao tồn tại)

Không cạnh tranh ở "trang tra cứu". Bán **việc đã xong**, trên bốn trụ không đối thủ nào có đủ:

1. **Hiệu lực-aware** — không bao giờ dẫn văn bản đã hết hiệu lực; xem luật đúng **tại một ngày T** (bitemporal). *(moat #1)*
2. **Phát hiện bỏ sót** — chỉ ra nghĩa vụ/điều khoản *còn thiếu* so với **luật bắt buộc tại thời điểm T**, không chỉ so playbook tĩnh. *(moat #2)*
3. **Song ngữ Việt–Anh ngang hàng** + neo trích dẫn tới điều–khoản + ngày hiệu lực. *(moat #3)*
4. **Thẩm định bản án** — đưa một bản án vào → *đáng ra xử thế nào · đúng/sai · căn cứ điều luật · neo án lệ* (second-opinion, human-in-the-loop). *(gần như first-of-its-kind)*

Deep research (2 report + 9 repo đọc sâu) xác nhận: **~70% hạ tầng tái dùng được từ repo mã nguồn mở; ~30% là moat tự xây — và 100% phần moat rơi đúng vào chỗ mọi repo để trống.**

---

## 2. Bản đồ tài liệu — đọc theo vai

### Người mới / stakeholder (hiểu toàn cảnh)
0. ⭐ [`docs/scope-and-priorities.md`](docs/scope-and-priorities.md) — **kim chỉ nam: xây trước / backlog / KHÔNG xây + bộ lọc 1-câu-hỏi** (đọc đầu tiên để không lan man).
0b. 🔒 [`docs/feature-registry.md`](docs/feature-registry.md) — **sổ cái 41 FR + 6 CN: toàn bộ tính năng + spec sở hữu + trạng thái.** · 🥊 [`docs/competitive-landscape.md`](docs/competitive-landscape.md) — đối thủ + moat nào còn trống.
1. [`docs/architecture.md`](docs/architecture.md) — tổng quan 4 tầng + 5 nguyên tắc.
2. [`docs/roadmap.md`](docs/roadmap.md) — 6 phase (dependency-ordered, mỗi phase có cổng số).
3. [`docs/platform-architecture-audit.md`](docs/platform-architecture-audit.md) — platform có gì · tính năng gì · xử lý/lưu trữ thế nào · bổ sung.
4. [`docs/end-to-end-flow.md`](docs/end-to-end-flow.md) — luồng data→AI→backend→frontend (và vì sao "chạy" thì đảo ngược).

### Kỹ sư triển khai (code từ đây)
- [`docs/implementation-architecture.md`](docs/implementation-architecture.md) — **6 module brief (W1–W6)** + ai code gì, thứ tự nào.
- `docs/specs/` — đặc tả cấp-triển-khai, có DDL/pseudocode/interface/acceptance/steal-list:
  | Spec | Mảng |
  |---|---|
  | [`w1-data-pipeline.md`](docs/specs/w1-data-pipeline.md) | Nạp + cấu trúc hoá + trích quan hệ |
  | [`w2-knowledge-graph.md`](docs/specs/w2-knowledge-graph.md) | **Đồ thị tri thức bitemporal (moat lõi)** |
  | [`w3-ai-retrieval-grounding.md`](docs/specs/w3-ai-retrieval-grounding.md) | Retrieval + grounding + eval |
  | [`w4-reasoning-engine.md`](docs/specs/w4-reasoning-engine.md) | Auditor hard-gate + reasoner đa vai |
  | [`w5-backend.md`](docs/specs/w5-backend.md) | FastAPI + multi-tenant + residency |
  | [`w6-platform.md`](docs/specs/w6-platform.md) | Workflow + JurisdictionPack + HITL |
  | [`stack-db-and-models.md`](docs/specs/stack-db-and-models.md) | DB · ML · local model · LLM |
  | [`deployment-infrastructure.md`](docs/specs/deployment-infrastructure.md) | Topology · GPU/vLLM · routing dữ liệu |
  | [`data-and-metadata-model.md`](docs/specs/data-and-metadata-model.md) | Metadata cho retrieval/reasoning/eval |
  | [`retrieval-and-storage-mechanisms.md`](docs/specs/retrieval-and-storage-mechanisms.md) | Cơ chế lưu trữ + truy xuất (verdict đem về) |
  | [`performance.md`](docs/specs/performance.md) | Hiệu năng: index · snapshot · cache · bound-hop · SLO |
  | [`w7-advisory-roles-viz.md`](docs/specs/w7-advisory-roles-viz.md) | Compliance-advisory · vai điều tra/kiểm sát/kiểm toán · loophole · workbench theo vai |
  | [`meta-json-assumed-schema.md`](docs/specs/meta-json-assumed-schema.md) | Schema meta.json **giả định** (chờ meta thật) |
  | [`reference-data-plane.md`](docs/specs/reference-data-plane.md) | **Data-handling chung**: Lakehouse → schema+contract → store → tầng (toolbox/map/đa-ngữ/template) + trigger luật-mới |
  | [`legal-rule-base.md`](docs/specs/legal-rule-base.md) | **Tri thức pháp lý VN cố định**: thang bậc (authority_rank versioned) · giải xung đột · hiệu lực/hồi tố · as_of · tách khỏi engine |
- 🔒 [`docs/security.md`](docs/security.md) — **threat model (STRIDE) + 5 quyết định security + checklist control + pentest** (perimeter: intake-sandbox · model-safetensors · platform-authz · log/backup · lakehouse-integrity).

> ⚠️ **ĐỌC TRƯỚC KHI CODE:** mọi spec đã qua **review phản biện độc lập** và còn **lỗi Critical phải sửa** — xem [`docs/specs/spec-audit-fixes.md`](docs/specs/spec-audit-fixes.md) (w1/w4/w5/w6) + mục audit inline trong `w2 §11`, `w3 §8`. Và **[`docs/engineering-principles.md`](docs/engineering-principles.md)** — 12 nguyên tắc (grounded · gated · versioned · fail-closed · human-escalated · test bằng dữ liệu bẩn) rút từ các lỗi đó; dùng làm checklist PR.

### Bối cảnh & bằng chứng
- [`docs/technical-design.md`](docs/technical-design.md) — Data/AI/Layer/Feature chi tiết.
- [`docs/layered-architecture.md`](docs/layered-architecture.md) — audit 15 layer (vì sao "4 tầng" chưa đủ).
- [`docs/repo-study-plan.md`](docs/repo-study-plan.md) · [`docs/repo-deep-read.md`](docs/repo-deep-read.md) · [`docs/repo-processing-comparison.md`](docs/repo-processing-comparison.md) — học gì từ repo nào (có steal-list file+line).
- [`docs/compliance-vn.md`](docs/compliance-vn.md) — ràng buộc pháp lý VN **đã verify**.
- `reports/` — 2 report nghiên cứu nền tảng. `research_notes/` — ghi chú chi tiết file-cited.

---

## 3. Kiến trúc tóm tắt

**15 layer / 5 mặt phẳng:** Platform (infra/tenancy/security/observability) · Data (acquisition→ingestion→**canonical bitemporal**→index) · Intelligence (retrieval→grounding→model-runtime→reasoning) · Application (workflow→jurisdiction-config→API→experience) · Governance (trust/eval-gate + knowledge-ops). Chi tiết: `layered-architecture.md`.

**Triết lý xử lý — ba tầng, đúng tool cho đúng việc:**
```
RULE (không model)   → xung đột · in_force · citation tồn tại   (rẻ nhất, xác định)
ML nhỏ, LOCAL        → embed · rerank · extract · NLI · OCR · link  (bulk · residency)
LLM qua GATEWAY      → suy luận/tổng hợp grounded (Claude + local)   (chỉ khi cần ngôn ngữ)
```
Quy tắc: rule được thì dùng rule → không thì ML nhỏ local → cùng lắm mới LLM.

**Stack đã chốt:** PostgreSQL (SoR bitemporal) + pgvector + đồ thị FK/CTE (AGE sau) + MinIO + Redis + Temporal; bge-m3 + extractor fine-tune (local); Claude Opus/Sonnet qua Gateway (+ vLLM local cho dữ liệu nhạy cảm). Tất cả tại VN.

---

## 4. Guardrails & tuân thủ (không thương lượng)

- **Hợp đồng đầu ra:** mọi câu trả lời = trích dẫn điều–khoản + **ngày hiệu lực** + confidence + song ngữ + **nhãn AI** + HITL. Không neo được → **abstain**, không bịa.
- **Human-in-the-loop:** công cụ cho chuyên gia, **không tư vấn trực tiếp cho công chúng**; Judgment Analysis là *second-opinion*, không "xử thay" (rủi ro cao — QĐ 33/2026).
- **Dữ liệu:** nguồn chính thống được phép dùng (raw data có án lệ + bản án + VBQPPL); **không cào** aggregator; dữ liệu khách **cô lập theo tenant, không train**; hosting tại VN (Luật 91/2025 + NĐ 356/2025).
- Chi tiết + mục cần đọc văn bản gốc: `compliance-vn.md`.

---

## 5. Repo tham khảo (`refs/`) — học, không copy mù

10 repo đã clone để đọc (xem verdict + file cần mở ở `repo-study-plan.md` / `repo-deep-read.md`):
`PAKTON` (khung agent+backend) · `indigo`+`cobalt`+`bluebell` (bitemporal/AKN) · `LegalGraphRAG` (Auditor) · `L-MARS` (citation verify) · `LeSICiN` (bản án↔điều luật) · `legalbenchrag` (eval) · `eyecite` (trích dẫn) · `claude-for-legal` (playbook workflow).

> License giai đoạn nghiên cứu không chặn; khi thương mại hoá, phần no-LICENSE phải *viết lại sạch* (ghi rõ trong `repo-study-plan.md`).

---

## 6. Bắt đầu thế nào

1. Đọc mục 1–3 README + `architecture.md` + spec mảng của bạn trong `docs/specs/`.
2. Mở các file steal-list trong `refs/` mà spec trỏ tới (có path+line).
3. **Thứ tự khởi công:** W5 (skeleton) + W1 (data) + **W2 (moat)** song song → W3 → W4 → W6.
4. Dựng **harness eval (L13) sớm** — có thước đo 3 chiều trước khi xây retrieval.
5. Acceptance đầu tiên phải xanh: **"văn bản tại ngày T"** trên 1 nghị định có sửa đổi (W2 §8).

*`src/traluat/` chứa engine và runtime đang phát triển; các model/provider thật, dữ liệu được duyệt và cổng phát hành vẫn cần được cấu hình riêng.*

---

## 7. Đang chờ (để khoá nốt)
- **`meta.json`** schema thật của raw data → chốt mapping W1 (hiện là placeholder).
- Mốc thời gian cụ thể → gắn calendar vào `roadmap.md` (đội tech mạnh & đông; pháp nhân VN đã được cho phép).
- Vài điểm pháp lý cần đọc **văn bản gốc** — danh sách ở `compliance-vn.md §5`.

## Chạy và kiểm thử sau audit

Cài package và phần geo cần cho migration: `uv sync --locked --extra geo`.
Runtime dùng factory `uvicorn traluat.w5.asgi:app_from_env --factory`; đặt `DATABASE_URL`
bằng login PostgreSQL **không superuser, không sở hữu bảng**, được cấp role `traluat_app`,
và đặt `JWT_SECRET` riêng tối thiểu 32 ký tự. Compose dùng biến `APP_DATABASE_URL` cho
API/worker, chỉ bind các cổng dịch vụ lên localhost; không tự tạo credential runtime.
Các bước cấp quyền, danh tính và giới hạn phát hành được ghi trong
[`docs/audit-fixes-2026-11-10.md`](docs/audit-fixes-2026-11-10.md).

Test PostgreSQL cần `TEST_DATABASE_URL` trỏ đến một database riêng đã tồn tại có tên
kết thúc `_test` hoặc bắt đầu `test_`. Harness chỉ migrate database được chỉ định,
**không DROP/CREATE database**. Không đặt biến này thì chỉ chạy test thuần, các test
DB sẽ skip; CI đặt thêm `REQUIRE_TEST_DATABASE=1` để thiếu DB là lỗi.

Reference suy từ luật cần `source_eid` đã nhập và còn áp dụng; sửa dữ liệu phải dùng
version mới, thay đổi chồng thời gian cần `reviewed_change=True` từ quy trình duyệt.
Dataset chưa có contract phải đăng ký contract trước khi nạp. Mẫu dùng chung chỉ
nhận bản trống đã duyệt (`public_reviewed=True`, `provenance='public_template'`);
không đưa hợp đồng đã điền hoặc dữ liệu khách vào kho mẫu công khai.
`scripts/seed_deadlines.py` chỉ publish khi người vận hành đã rà bundle minh họa
theo nguồn gốc và truyền `--reviewed`; source chưa nhập/không áp dụng vẫn bị quarantine.
