# START HERE — Hướng dẫn cho đội dev

> Mở file này đầu tiên khi bắt đầu code TraLuat. Nó nói: **đọc gì → code từ file nào → theo thứ tự nào → xong là thế nào.**
>
> ⚠️ **File `TraLuat-KienTruc.docx` là bản tổng quan để ĐỌC/chia sẻ — KHÔNG code từ đó.** Code từ `docs/specs/`.

---

## Bước 1 — Mọi dev đọc nền chung (bắt buộc, trước khi viết dòng nào)
1. [`README.md`](README.md) — điểm vào.
2. [`docs/scope-and-priorities.md`](docs/scope-and-priorities.md) — **xây gì trước / backlog / KHÔNG xây** + bộ lọc 1-câu-hỏi.
3. 🔒 [`docs/feature-registry.md`](docs/feature-registry.md) — **sổ cái 33 FR + 6 CN = chống bỏ sót tính năng.** Mỗi FR có spec sở hữu + trạng thái. *Đóng module → mọi FR của nó `DONE` hoặc `DEFER` (có lý do), không được biến mất.*
4. [`docs/engineering-principles.md`](docs/engineering-principles.md) — **12 nguyên tắc = checklist review PR**.
5. [`docs/compliance-vn.md`](docs/compliance-vn.md) — ràng buộc cứng (residency VN · tenant · nhãn AI · ẩn danh bản án).
5b. 🔒 [`docs/security.md`](docs/security.md) — **threat model + 5 quyết định security (intake-sandbox · safetensors/pin · platform-authz · log/backup · lakehouse-integrity) + checklist control** + pentest. Đọc trước khi code intake/model/auth/egress.
7. Tham khảo kiến trúc: [`docs/architecture.md`](docs/architecture.md) · [`docs/layered-architecture.md`](docs/layered-architecture.md) · [`docs/end-to-end-flow.md`](docs/end-to-end-flow.md) · [`docs/competitive-landscape.md`](docs/competitive-landscape.md).

---

## Bước 2 — Nhận MỘT mảng, code từ spec của nó (nguồn chính)

| Mảng | Code từ | Phụ thuộc |
|---|---|---|
| Data pipeline | [`docs/specs/w1-data-pipeline.md`](docs/specs/w1-data-pipeline.md) | — |
| **Đồ thị tri thức (moat lõi)** | [`docs/specs/w2-knowledge-graph.md`](docs/specs/w2-knowledge-graph.md) | — |
| AI/ML (retrieval + grounding) | [`docs/specs/w3-ai-retrieval-grounding.md`](docs/specs/w3-ai-retrieval-grounding.md) | W2 |
| Reasoning engine | [`docs/specs/w4-reasoning-engine.md`](docs/specs/w4-reasoning-engine.md) | W2, W3 |
| Backend / Engineering | [`docs/specs/w5-backend.md`](docs/specs/w5-backend.md) | song song |
| Platform / Workflow | [`docs/specs/w6-platform.md`](docs/specs/w6-platform.md) | W3, W5 |
| *(backlog — chưa code)* | `docs/specs/w7-advisory-roles-viz.md` | sau |

Mỗi spec đã **self-contained**: deliverables · design/DDL/pseudocode · interface giữa các W · **acceptance tests** · **steal-list (file+line trong `refs/`)** · **banner 🔴 fix Critical** ở đầu.

---

## Bước 3 — Spec dùng chung (tra khi cần)
- [`docs/specs/stack-db-and-models.md`](docs/specs/stack-db-and-models.md) — chọn DB / ML / LLM.
- [`docs/specs/deployment-infrastructure.md`](docs/specs/deployment-infrastructure.md) — topology · GPU/vLLM · **egress routing** (dữ liệu khách không ra Claude).
- [`docs/specs/data-and-metadata-model.md`](docs/specs/data-and-metadata-model.md) — metadata cho retrieval/reasoning/eval.
- [`docs/specs/retrieval-and-storage-mechanisms.md`](docs/specs/retrieval-and-storage-mechanisms.md) + [`docs/specs/performance.md`](docs/specs/performance.md) — cơ chế + index/SLO.
- [`docs/specs/spec-audit-fixes.md`](docs/specs/spec-audit-fixes.md) — **đọc TRƯỚC khi tin một spec**: lỗi Critical + thứ tự sửa.
- [`docs/integration-audit.md`](docs/integration-audit.md) — **đọc TRƯỚC khi ghép repo**: seam → verdict (WIRE-AS-LIB/REMODEL/SERVICE/REBUILD) + 5 thứ vỡ nếu glue thô + pin Python 3.12 + langchain 0.2↔0.3 clash.
- [`docs/specs/integration-adapters.md`](docs/specs/integration-adapters.md) — **hợp đồng ghép**: adapter cho từng seam (vào format gốc → ra canonical/interface, ép as_of+tenant) + seam-test + checklist.
- [`docs/specs/meta-json-assumed-schema.md`](docs/specs/meta-json-assumed-schema.md) — hợp đồng meta.json (giả định tới khi có bản thật).
- [`docs/specs/reference-data-plane.md`](docs/specs/reference-data-plane.md) — **data-handling cho mọi tính năng cần data tham chiếu** (toolbox/map/đa-ngữ/template): Lakehouse → schema+API contract → adapter → store → tầng truy xuất + trigger luật-mới (DATA-auto / RULE-human).
- 🔒 [`docs/specs/legal-rule-base.md`](docs/specs/legal-rule-base.md) — **tri thức pháp lý VN cố định** (thang bậc/xung đột/hiệu lực/hồi tố/as_of): declarative, versioned, neo primary-text, **tách khỏi engine** (nguyên tắc #13). Engine chỉ ĐỌC; migrate code KHÔNG migrate luật.
- `refs/` — 10 repo tham khảo để mở đúng file steal-list.

---

## Bước 4 — Thứ tự khởi công & quy trình mỗi dev

> 🧭 **Order-list MASTER = `docs/roadmap.md §NÊN LÀM NGAY`.** Mục dưới đây là *build-order chi tiết mỗi mảng*; khi vênh, theo roadmap.

**Thứ tự khởi công (từ roadmap + scope):**
```
Song song:  W5 (skeleton) + W1 (data) + W2 (moat)   →  W3  →  W4  →  W6
Làm SỚM:    harness eval (L13) — có thước đo trước khi xây retrieval
Acceptance xanh ĐẦU TIÊN: "văn bản tại ngày T"  (W2 §8)
W7: backlog — KHÔNG code cho tới khi lõi W1–W6 qua cổng benchmark
```

**Quy trình một dev:**
1. Đọc Bước 1 → kiểm mảng mình có thuộc "xây trước" trong `scope-and-priorities` không.
2. Mở spec mảng mình → đọc **banner 🔴 (fix Critical)** + **acceptance tests** trước.
3. Mở các file `refs/...` mà **steal-list** của spec trỏ tới (path+line).
4. Code tới khi **acceptance test xanh**.

**Cách lấy code từ `refs/` — MIGRATE rồi NÂNG CẤP (nhanh hơn viết từ trắng, nhưng phải tốt HƠN repo):**
> ⚠️ **Repo trong `refs/` phần lớn là research-grade/prototype — KHÔNG phải chuẩn vàng.** Mục tiêu migration **không phải** "chạy giống repo", mà là **"tốt hơn repo"**. Bê y nguyên = thừa hưởng luôn cái dở.
```
① Port skeleton/code từ repo (theo verdict integration-audit §1: WIRE-AS-LIB dùng thẳng / PORT bê skeleton / REBUILD viết lại)
② AUDIT chất lượng code gốc — ĐỪNG giả định "repo = tốt". Soi:
     - đúng/sai (bug ẩn: retrieval bỏ as_of/tenant · `"true" in text` khớp "untrue" · stop-condition mong manh…)
     - có đạt 15 nguyên tắc (engineering-principles) không? đặc biệt grounded/gated/fail-closed
     - 🔒 **SECURITY-PASS (bắt buộc, security.md §2):** pin upstream commit + diff upstream + grep `eval/exec/subprocess/os.system/dynamic-import/network/cred` + SCA deps repo → chặn implant/CVE (audit cũ chỉ soi correctness, không soi malicious)
     - chỗ nào ẩu, hard-code US, thiếu test, thiếu edge-case → ghi ra
③ Gắn ADAPTER + VIẾT LẠI phần dở (không chỉ map — sửa cho đúng chuẩn mình, chèn as_of/tenant/abstain)
④ SEAM-TEST ĐỐI-KHÁNG (bắt buộc): ép as_of sai + tenant khác + input bẩn + input rỗng
⑤ Edit tới khi: seam-test xanh **VÀ** code đạt 12 nguyên tắc (tốt hơn bản gốc, không chỉ bằng)
```
> **Bước ② + ⑤ là điểm khác biệt:** repo là *vật liệu tham khảo*, không phải code để thờ. Nếu đoạn gốc ẩu/sai → **nâng lên chuẩn TraLuat**, không copy cái ẩu. Các audit trước đã chứng minh: bug lọt vào spec đều là do **bê thẳng pattern repo mà không audit** (danh sách: `spec-audit-fixes.md`). Chuẩn chất lượng là **12 nguyên tắc**, KHÔNG phải mức của repo nguồn.

---

## Definition of Done (một task xong khi)
- [ ] 🔒 **Cập nhật `feature-registry.md`:** FR mình đụng đã đổi trạng thái (`WIP`/`DONE`/`DEFER`). PR đụng FR mà không cập nhật dòng này ⇒ **không merge**.
- [ ] **Acceptance tests** của spec xanh (gồm **adversarial test**, không chỉ happy-path).
- [ ] Giữ **hợp đồng đầu ra**: trích dẫn điều–khoản + **ngày hiệu lực** + confidence + nhãn AI + HITL (hoặc **abstain** nếu không neo được).
- [ ] Đã áp **fix Critical** liên quan (banner 🔴 của spec + `spec-audit-fixes.md`).
- [ ] Qua **review PR theo 12 nguyên tắc** (`engineering-principles.md`); đặc biệt #2 (constraint DB), #7 (test bẩn), #10 (tenancy/compliance fail-closed + có test).
- [ ] Không vi phạm ràng buộc `compliance-vn.md` (residency · tenant · nhãn AI · ẩn danh).

## Cổng phát hành toàn hệ
Không mở tính năng **backlog (W7)** cho tới khi **benchmark 3 chiều (L13) đạt**: *đúng điều–khoản · đúng hiệu lực · bắt bỏ sót* — thắng baseline LLM.

---

## Đang chờ (chặn một phần W1)
- **`meta.json` schema thật** → chốt mapping W1 (hiện dùng `meta-json-assumed-schema.md`).
- Mốc thời gian cụ thể → gắn lịch vào `roadmap.md`.

> Một câu: **đọc Word & `docs/` để *hiểu* → code từ `docs/specs/wX` + steal-list `refs/` → tuân `engineering-principles` → theo thứ tự `scope-and-priorities` → done khi acceptance xanh + giữ hợp đồng đầu ra.**
