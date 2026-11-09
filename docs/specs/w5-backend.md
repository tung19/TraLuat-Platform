# W5 — Backend / Engineering (P1–P4, L7 serving, L11 API) — Đặc tả triển khai

> Module brief cho member mảng **W5 / P1–P4 + L7 serving + L11 API**. Chạy **song song** với W1/W2 ngay từ đầu (skeleton trước, không chờ KG).
> Nguồn pattern: **PAKTON `PAKTON Framework/`** (xương sống FastAPI+Celery+SQLAlchemy+Alembic dùng ngay). Đọc kèm `docs/implementation-architecture.md §W5` và `docs/compliance-vn.md`.
> **Nguyên tắc vàng:** lift nguyên **cơ học backend** của PAKTON, nhưng PAKTON là công cụ QA một-hợp-đồng, một-index, một-người-dùng — **KHÔNG có multi-tenancy, KHÔNG có data residency, KHÔNG observability/nhãn AI**. Đó là phần W5 phải tự xây và nó phải cắm **xuyên suốt**, không bolt-on.

---

## 0. Module này giao ra cái gì (deliverables)

1. **Skeleton dịch vụ chạy được** — FastAPI (REST + SSE step/tool streaming) + Celery worker (async, retry, warm agent per-worker) + SQLAlchemy + Alembic, đóng gói Docker/compose/nginx — **lift từ PAKTON `API/`**.
2. **Lớp multi-tenancy xuyên suốt** — `tenant_id` mọi nơi; cô lập cứng ở cả **ba kho** (SQL metadata / langgraph checkpointer / vector store); RLS hoặc schema-per-tenant; mã hoá key-per-tenant; **KB luật chia sẻ read-only** tách khỏi **dữ liệu khách cô lập, không train**.
3. **Tuân thủ VN ở tầng hạ tầng** — data residency trong VN + **zero-retention tùy chọn** (NĐ 356/2025); hook ghi chú ràng buộc pháp nhân VN + chứng nhận BCA (NĐ 356 Điều 21–22).
4. **Observability + nhãn AI** — OTel trace/metrics/cost LLM theo tenant; **gắn nhãn AI** mọi output ở gateway/API (Luật 71/2025 Điều 44).
5. **Hợp đồng API (L11)** — REST surface + luồng task async + điểm thực thi cô lập tenant, cho W6 (frontend/workflow) và W3/W4 (engine) tiêu thụ.

**Bất biến W5:** (1) không request nào vào worker mà thiếu `tenant_id` đã xác thực; (2) không câu trả lời nào rời API mà thiếu nhãn AI + trace_id; (3) dữ liệu khách không bao giờ lọt sang prompt/engine/log của tenant khác; (4) KB luật là **read-only shared**, dữ liệu khách là **isolated**; (5) **dữ liệu khách không bao giờ rời VN** (không ra Claude API nước ngoài) trừ khi tenant đã khai TIA.

> 🔴 **Audit fixes Critical ĐÃ ÁP** (chi tiết `docs/specs/spec-audit-fixes.md` W5): **(C1)** định nghĩa **classifier egress fail-closed** (phân loại cả *input thô*, không chỉ chunk; mặc định vLLM local; tắt cache/log ngoại trên nhánh KB) — xem §3.1; **(C2)** `FORCE ROW LEVEL SECURITY` + **app role non-owner** (RLS mặc định *fail-open* với owner/BYPASSRLS) — §2.3; **(C3)** checkpointer **không** được RLS lọc (pool riêng) → **validate prefix `tenant:<id>` mỗi read** — §2.3; **(C4)** **không truyền bytes hợp đồng qua Celery/Redis/RabbitMQ** (để object store, truyền ref; mã hoá/cô lập broker+cache; zero-retention phải chạm tới chúng) — §6; **(C5)** **audit quyết định route/egress** — §3.3; **(C6)** `task_status` phải **check sở hữu theo tenant** (IDOR) — §5.

---

## 1. Kiến trúc tiến trình (P1–P4) — lift từ PAKTON, giữ nguyên hình dạng

PAKTON đã có đúng topo ta cần (xác minh `API/docker-compose.yml:11-95`):

```
Client ──HTTPS──► nginx ──► FastAPI (API/api.py)         ← P1: API gateway (đồng bộ, nhẹ)
                               │ send_task (Celery)
                               ▼
                      RabbitMQ (broker)  ◄── CELERY_BROKER_URL amqp://
                               │
                               ▼
                      Celery worker(s) (API/tasks.py)     ← P2: xử lý nặng (engine W3/W4)
                               │ kết quả
                               ▼
                      Redis (result backend) ◄── CELERY_RESULT_BACKEND redis://
```

**Ba kho tách (xác minh — TraLuat giữ nguyên, thêm tenant):**
| Kho | PAKTON | Vai trò | File xác minh |
|---|---|---|---|
| **SQL metadata** (P3) | Postgres qua SQLAlchemy | `users`, `conversations` + (TraLuat) tenant, document, audit | `API/database/config.py:25-37`, `models/{user,conversation}.py` |
| **Langgraph checkpointer** (P4) | `AsyncPostgresSaver` keyed theo `thread_id`, cùng Postgres | lịch sử/trạng thái hội thoại (resume, timeline) | `Archivist/src/Archivist/agent.py:14,118-137,307-321` |
| **Vector store** | Pinecone **hoặc** ChromaDB | embedding tài liệu | `Archivist/src/Archivist/indexers/vectordb.py:3,14,20` |

> **Lift nguyên:** cấu trúc service, Celery wiring, SSE streaming, SQLAlchemy session/context-manager, Alembic. **Thay engine ruột** (Archivist/Interrogator/Researcher của PAKTON) bằng grounding loop + Auditor của TraLuat (W3/W4) — W5 **không** đụng engine, chỉ cung cấp xương sống + cô lập + serving.

**Warm agent per-worker (giữ):** PAKTON khởi tạo agent **một lần mỗi worker** (`API/tasks.py:38-47` biến `archivist` global + hook `on_after_configure` `:321-328`) để không nạp lại model mỗi task. TraLuat giữ pattern này **nhưng** state per-request (tenant, as_of, retrieval) **không** được dính vào instance warm — tenant context truyền qua args/headers của task, không qua biến global.

**Retry (giữ):** mọi task `bind=True, default_retry_delay=5, max_retries=3`, `self.retry(exc=e, countdown=5)` (`API/tasks.py:49,77,186,273`). TraLuat thêm: **không retry** lỗi 4xx/validation (vd tenant treo, quota hết) — chỉ retry lỗi hạ tầng tạm thời.

---

## 2. Multi-tenancy xuyên suốt (phần PAKTON KHÔNG có — moat vận hành)

### 2.1 Mô hình tenant
```
tenant(id UUID PK, slug UNIQUE, name, status,                 -- active|suspended
       isolation_mode,                                        -- 'rls' | 'schema'  (chọn theo hạng khách)
       residency_region DEFAULT 'vn',
       retention_mode DEFAULT 'standard',                     -- 'standard' | 'zero'
       kms_key_id,                                            -- khoá bọc DEK của tenant
       created_at, updated_at)
tenant_user(tenant_id FK, user_id, email, role, UNIQUE(tenant_id,email))
             -- role ∈ {owner, lawyer, reviewer, viewer}  ← RBAC (PAKTON KHÔNG có)
```
- Mọi bảng dữ liệu khách (`conversations`, `documents`, `analysis_task`, `audit_log`, `chunk` client) **thêm cột `tenant_id` NOT NULL**. PAKTON `conversations` chỉ có `user_email` (`models/conversation.py:20-21`) → **TraLuat thêm `tenant_id` + index `(tenant_id, …)`** trong migration Alembic mới (kế thừa `001_initial`, `002_add_message_count`).
- **RBAC:** PAKTON lấy `role` từ JWT (`auth.py:24`) nhưng **không bao giờ dùng để phân quyền**. TraLuat thêm dependency `require_role(...)` gác theo `tenant_user.role`.

### 2.2 Hai lớp dữ liệu (ranh giới cứng)
| Lớp | Nội dung | Cô lập | Train? |
|---|---|---|---|
| **KB luật chia sẻ (shared, read-only)** | corpus QPPL/án lệ từ W1/W2 (`document/unit/unit_version/precedent/judgment/chunk` công khai) | **1 bản dùng chung** mọi tenant; chỉ đọc | — (dữ liệu công) |
| **Dữ liệu khách (isolated)** | hợp đồng upload, hội thoại, kết quả phân tích, embedding tài liệu khách | **cô lập cứng theo `tenant_id`** | **TUYỆT ĐỐI KHÔNG** train/fine-tune trên dữ liệu khách |

Hệ quả: retrieval của W3 nhận **hai nguồn** — KB shared (namespace `kb`) + client store (namespace `tenant:<id>`) — và **không bao giờ** trộn client của tenant A sang tenant B.

### 2.3 Cô lập ở ba kho (thực thi)
1. **SQL metadata — RLS (mặc định):** mỗi phiên DB mở đầu bằng `SET LOCAL app.current_tenant = :tenant_id`; policy RLS `USING (tenant_id = current_setting('app.current_tenant')::uuid)` trên mọi bảng khách. Gói trong biến thể của `get_db_session()` (PAKTON `database/config.py:40-60`) → `get_tenant_db_session(tenant_id)`. **Schema-per-tenant** (`isolation_mode='schema'`, `search_path` riêng) cho khách hạng cao cần cô lập vật lý.
   - **★ Critical C2 — RLS mặc định FAIL-OPEN:** nếu app role **sở hữu bảng** (mặc định) hoặc có `BYPASSRLS`, mọi policy bị **bỏ qua im lặng** → thấy hết tenant. Khẳng định "query không set var → 0 dòng" ở §6 **chỉ đúng khi**: (a) `ALTER TABLE … FORCE ROW LEVEL SECURITY` trên mọi bảng khách, **và** (b) app chạy bằng **role NON-OWNER, không BYPASSRLS**, với policy mặc-định-deny. Bắt buộc cả hai; có acceptance test chạy bằng app-role để chứng minh không fail-open.
2. **Langgraph checkpointer — ★ Critical C3: RLS KHÔNG với tới được.** `AsyncPostgresSaver.from_conn_string` mở **pool riêng** (`agent.py:122`) → `SET LOCAL app.current_tenant` của SQLAlchemy **không lan sang** → bảng checkpoint **không bị policy lọc**. Bảo vệ phải ở **application**: `thread_id = tenant:<id>:<thread>` và **validate prefix `tenant:<id>` khớp tenant hiện tại ở MỌI read/write checkpointer** (không tin UUID khó đoán). Checkpointer dùng cùng role non-owner, và zero-retention thì tắt hẳn.
3. **Vector store:** **Pinecone namespace = `tenant:<id>`** / **Chroma collection = `cli_<tenant_id>`**; KB shared ở namespace/collection riêng `kb`. Mọi `retrieve()` bắt buộc truyền namespace — **đây là chỗ PAKTON thiếu hẳn** (`retrievers/base.py:37` chỉ có `retrieve(query, **kwargs)`, không metadata/tenant/as_of filter).

### 2.4 Mã hoá key-per-tenant
- **Envelope encryption:** mỗi tenant 1 **DEK**; DEK bọc bằng khoá KMS (`tenant.kms_key_id`). Nội dung tài liệu khách + transcript nhạy cảm mã hoá at-rest bằng DEK tenant.
- Xoá/rotate khoá tenant ⇒ crypto-shred (phục vụ quyền xoá của chủ thể, NĐ 356 + zero-retention).

### 2.5 LLM gateway guard (nối W3.3)
Gateway (L7, do W3 sở hữu interface) **phải** nhận `tenant_id` và **từ chối** khi context_chunks lẫn chunk của tenant khác (chỉ cho phép cùng `tenant:<id>` hoặc `kb`). W5 cung cấp **điểm chặn**: task truyền `tenant_id` xuống gateway; không có `tenant_id` ⇒ task fail ngay, không gọi LLM.

---

## 3. Tuân thủ VN ở tầng hạ tầng (NĐ 356/2025, Luật 71/2025 — `docs/compliance-vn.md`)

### 3.1 Data residency + ràng buộc pháp nhân (NĐ 356/2025)
- **Hosting trong VN:** toàn bộ Postgres/Redis/RabbitMQ/vector/LLM-endpoint cho dữ liệu khách đặt region VN (`tenant.residency_region='vn'`). LLM nhạy cảm → `endpoint_url` self-host/vLLM trong VN thay vì API nước ngoài (nối W3.3).
- **⚠️ Ràng buộc cấu trúc lớn nhất (NĐ 356 Điều 21–22):** bên cung cấp dịch vụ xử lý dữ liệu **phải là pháp nhân Việt Nam + có chứng nhận dịch vụ xử lý dữ liệu của Bộ Công an**. Đây là ràng buộc **pháp nhân vận hành**, không chỉ kỹ thuật — W5 ghi nhận như **cổng go-live** (không phải code), và cô lập hạ tầng phải sẵn sàng để chứng nhận. [cần primary-text — xem `compliance-vn.md §1`].
- **Chuyển xuyên biên giới (Luật 91/2025 Điều 20):** nếu bất kỳ phần xử lý/lưu nào ra cloud nước ngoài → hồ sơ **TIA** nộp BCA trong **60 ngày**; dữ liệu khách của SaaS **không** được miễn (Điều 20(6)). W5: cờ `residency_region` + chặn luồng dữ liệu khách ra ngoài VN trừ khi tenant đã bật & khai TIA.

### 3.1b ★ Critical C1 — Classifier egress (dữ liệu khách KHÔNG ra Claude API)
Claude API ở **ngoài VN**. Phải có **một quy tắc route fail-closed** (ba doc trước mâu thuẫn per-prompt/per-tenant/cross-tenant — chốt tại đây):
- **Phân loại NGUỒN của *mọi phần prompt*** (không chỉ retrieved chunk — gồm **query/văn bản khách thô, few-shot, system**): nhãn `public_kb` | `client_sensitive`.
- **Bất kỳ phần nào `client_sensitive` → bắt buộc vLLM **local trong VN**.** Chỉ prompt **thuần `public_kb`** mới được ra Claude API. Prompt Review/Draft/Judgment (mang hợp đồng/bản án của khách) → **luôn local**.
- **Mặc định fail-closed:** không phân loại được → coi là `client_sensitive` → local.
- **★ R2-fix (chaos — circuit-breaker khi LOCAL DOWN):** residency là **phân vùng CỨNG**. Khi vLLM local OOM/down → **abstain + enqueue HITL/retry-khi-up**, **TUYỆT ĐỐI KHÔNG failover sang Claude** cho `client_sensitive` (failover = vi phạm NĐ 356 âm thầm). Tương tự verifier local thứ-2 down → vào **chế-độ-suy-giảm** (siết gate1/2/3b + HITL), không skip verify.
- **★ Phân loại theo PROVENANCE, không content-heuristic** (chống false-negative egress): gắn nhãn nguồn `public_kb`/`client_sensitive` **tại điểm nhập** (origin = KB vs tenant-upload), không đoán theo nội dung.
- **★ Audit WRITE-AHEAD:** ghi *ý định route* TRƯỚC khi gọi, xác nhận SAU — crash giữa chừng vẫn còn bằng chứng residency (NĐ 356 Đ29).
- Nhánh ra Claude API: **tắt prompt-cache + I/O logging phía nhà cung cấp** (chống lưu text ở nước ngoài); chỉ gửi dữ liệu công. **Prompt-cache phải partition theo tenant** (key gồm tenant) — chống rò chéo qua cache.
- **Người gác:** một `EgressPolicy` tập trung ở gateway; test rò (gửi prompt lẫn client text → phải chặn khỏi Claude) + **test local-down (kill vLLM → prompt nhạy cảm phải bị deny/queue, KHÔNG egress)** là **acceptance bắt buộc** (§7).

### 3.2 Zero-retention (tùy chọn theo tenant)
`tenant.retention_mode`:
- `standard`: lưu document/transcript/kết quả theo chính sách (mã hoá key-per-tenant).
- `zero`: **xử lý phù du** — nội dung tài liệu khách chỉ tồn tại trong vòng đời task (temp, như PAKTON `tasks.py:231-245` tạo/`os.remove` temp file), **không** persist vào vector store/checkpointer; chỉ giữ **metadata tối thiểu + audit** (không chứa nội dung). Checkpointer tắt cho thread zero-retention.

### 3.3 Audit & breach (NĐ 356 Điều 29)
- `audit_log(id, tenant_id, actor, action, resource, trace_id, ts, meta_jsonb)` — **không chứa nội dung nhạy cảm**, giữ **≥5 năm**. Append-only ép ở DB (app role chỉ `INSERT`, không `UPDATE/DELETE`).
- **★ Critical C5 — ghi quyết định route/egress:** mỗi lần gọi LLM log `{data_class, residency, llm_destination: local|claude}` → chứng minh được *dữ liệu khách ở lại VN* (NĐ 356 Đ29). Không log nội dung, chỉ quyết định.
- Hook báo vi phạm **72h** (sự cố vị trí/sinh trắc) → alert pipeline (W6 ops) đọc từ audit/metrics.

### 3.4 Nhãn AI ở gateway/API (Luật 71/2025 Điều 44, NĐ 142/2026)
- **Mọi** response sinh bởi AI mang: (a) cờ `ai_generated=true` + thông báo "đang tương tác với AI"; (b) **thẻ máy-đọc** (header `X-AI-Generated: true` + trường `ai_label` trong JSON/SSE event). Áp ở **một chỗ** — response envelope của API (mở rộng `response_template.py` của PAKTON) — để không node nào quên.
- Grace period 12–18 tháng (xem `compliance-vn.md §2`) → cờ bật được theo ngày hiệu lực.

---

## 4. Observability (L11 — PAKTON chỉ có logger thường)

PAKTON có `API/logger.py` (log format tùy biến) nhưng **không** trace/metrics/cost. TraLuat thêm:
- **OpenTelemetry trace:** span gốc mỗi request (middleware FastAPI) → propagate `trace_id` qua Celery header → span cho mỗi task, mỗi lần gọi retrieval/LLM/verify. `trace_id` vào `audit_log` + trả về client (gắn vào response envelope).
- **Metrics (Prometheus `/metrics`):** latency request/task, độ sâu hàng đợi Celery, tỉ lệ success/failure/retry, **token & cost LLM theo `tenant_id` + node** (gắn nhãn `tenant`, `node`, `model`).
- **Cost accounting:** mỗi lời gọi gateway ghi `(tenant_id, model, prompt_tokens, completion_tokens, cost_usd)` → bảng/metric để tính chi phí theo tenant (billing + phát hiện lạm dụng).
- **Structured log:** mọi dòng kèm `trace_id` + `tenant_id` (giữ format PAKTON `logger.py`, thêm 2 field).

---

## 5. Hợp đồng API (L11) — REST surface

**Xác thực & resolve tenant:** `Authorization: Bearer <JWT>` (Supabase, HS256, toggle `ENABLE_AUTHENTICATION` — giữ `auth.py:92-101,164-198`). TraLuat **mở rộng `SupabaseUser`**: đọc `tenant_id` từ `app_metadata.tenant_id` (claim) → dependency `get_tenant_context()` trả `(user, tenant, role)`; chặn nếu `tenant.status != active`. **Mọi** endpoint dữ liệu khách phụ thuộc dependency này.

```
# Tài liệu khách (tenant-scoped, mã hoá key-per-tenant)
POST   /v1/documents                 multipart (file+metadata) → {task_id}     # lift /index/document/ (api.py:411)
GET    /v1/documents                 list (RLS theo tenant)
GET    /v1/documents/{id}
DELETE /v1/documents/{id}            # zero-retention/crypto-shred

# Phân tích async (ruột = engine W3/W4; W5 lo enqueue + stream + nhãn + cô lập)
POST   /v1/analysis/review           {doc_id, as_of_date?} → {task_id}         # Review hợp đồng
POST   /v1/analysis/judgment         {text|doc_id, as_of_date?} → {task_id}    # Judgment Analysis
POST   /v1/analysis/draft            → {task_id}
POST   /v1/analysis/compliance-diff  → {task_id}
POST   /v1/query/sse                 SSE: stream từng step/tool + token          # lift /query/stream_steps/sse (api.py:247)

# Task & hội thoại (tenant-scoped)
GET    /v1/tasks/{task_id}           trạng thái + kết quả                        # lift /task_status (api.py:558)
GET    /v1/conversations             list (RLS)                                  # lift (api.py:607)
GET    /v1/conversations/{thread_id} + /messages                                # lift (api.py:677,732)
DELETE /v1/conversations/{thread_id}                                            # lift (api.py:810)

# KB luật chia sẻ (read-only, KHÔNG tenant-scoped nội dung, vẫn cần auth)
GET    /v1/kb/documents  GET /v1/kb/units/{eid}?as_of=YYYY-MM-DD   # neo "văn bản tại ngày T" (W2)

# Quản trị tenant (role=owner) + vận hành
POST   /v1/admin/tenants  /v1/admin/tenants/{id}/keys/rotate  /v1/admin/tenants/{id}/retention
GET    /health            # giữ api.py:858
GET    /metrics           # Prometheus (mới)
```

**Response envelope (mở rộng `response_template.py`):** mọi payload bọc `{status, task_id, trace_id, ai_label:{generated:bool, notice}, data}`. Header kèm `X-AI-Generated`, `X-Trace-Id`.

---

## 6. Luồng task async + thực thi cô lập (đặc tả hành vi)

```
1. API nhận request → get_tenant_context()        # xác thực JWT, resolve tenant+role
   ├─ tenant.status != active  → 403
   ├─ role không đủ (require_role) → 403
   └─ quota/rate theo tenant → 429 nếu vượt
2. API đóng gói task:
   celery_app.send_task(name, args=[...],
       headers={tenant_id, trace_id, as_of_date, residency_region, retention_mode},
       queue=Config.SERVICE_QUEUE)               # giữ pattern api.py:462-467
   → trả 202 {task_id, trace_id}
3. Worker nhận task:
   ├─ KHÔNG có tenant_id trong header  → fail ngay, không chạy engine  (bất biến #1)
   ├─ mở get_tenant_db_session(tenant_id)  → SET LOCAL app.current_tenant  (RLS)
   ├─ nạp DEK tenant (giải mã nội dung), chọn vector namespace tenant:<id> + kb
   ├─ chạy grounding loop (W3/W4): retrieve(as_of, tenant, kb) → generate → verify 3 cổng
   │    (LLM gateway guard: chunk phải thuộc tenant:<id> hoặc kb, nếu khác → từ chối)
   ├─ retention_mode='zero' → không persist nội dung vào vector/checkpointer; chỉ metadata+audit
   └─ áp nhãn AI + trace vào kết quả
4. Stream: /v1/query/sse phát từng step/tool (giữ event_stream api.py:305-398) + token,
   mỗi event mang ai_label; kết thúc 'complete'.
5. Ghi: audit_log(tenant, actor, action, trace_id) + metrics(cost, tokens, latency theo tenant).
```

**Tenant-isolation enforcement (tóm tắt điểm chặn):**
| Tầng | Cơ chế | Fail-closed |
|---|---|---|
| API | `get_tenant_context` dependency | thiếu/treo tenant → 403 |
| Task | `tenant_id` trong Celery header bắt buộc | thiếu → task FAILURE, không gọi engine |
| SQL | RLS `app.current_tenant` (hoặc schema) | query không set var → 0 dòng |
| Vector | namespace `tenant:<id>` / collection riêng | thiếu namespace → từ chối retrieve |
| Gateway | guard chunk cùng tenant/kb **+ EgressPolicy** (C1) | lẫn tenant → raise; client_sensitive → local, không ra Claude |
| At-rest | DEK key-per-tenant | khoá sai → không giải mã được |
| **Broker/Redis (★C4)** | **KHÔNG truyền bytes hợp đồng qua Celery** — để object store, truyền `doc_ref`; mã hoá+auth broker/Redis; zero-retention xoá cả hai | bytes không bao giờ nằm trần ở broker/result backend |
| **Task result (★C6)** | `GET /v1/tasks/{id}` **check `task.tenant_id == current tenant`** trước khi trả | task của tenant khác → 403 (không IDOR) |

---

## 7. Acceptance tests (phải xanh)

1. **Skeleton sống:** upload tài liệu → `POST /v1/documents` trả `task_id`; `GET /v1/tasks/{id}` chuyển PENDING→SUCCESS; `POST /v1/query/sse` stream từng step/tool rồi `complete`. (Chứng minh lift PAKTON chạy.)
2. **Cô lập 2 tenant (then chốt):** tenant A upload tài liệu X; tenant B `GET /v1/documents`, truy vấn, SSE — **không** thấy X, không retrieve trúng chunk của A (kiểm cả SQL-RLS, vector-namespace, checkpointer). Đổi `tenant_id` trong JWT của B để thử lấy tài nguyên A → 403/0 dòng.
3. **KB shared vs client isolated:** cả A và B đều truy được KB luật (cùng kết quả cho cùng `as_of`); không tenant nào ghi được vào KB (read-only); dữ liệu khách không lẫn.
4. **Nhãn AI:** mọi response sinh-AI có `ai_label.generated=true` + header `X-AI-Generated`; SSE mỗi event mang nhãn. Response không-AI (vd list document) không gắn nhãn sai.
5. **Zero-retention:** tenant `retention_mode='zero'` chạy phân tích → sau khi task xong, **không** còn nội dung tài liệu trong vector store/checkpointer/temp; chỉ còn metadata + audit (không nội dung).
6. **Observability:** mỗi request có `trace_id` xuyên API→task→LLM; `/metrics` xuất token & cost theo `tenant_id`; audit_log ghi đủ action + trace_id.
7. **RBAC:** `role=viewer` bị 403 khi gọi `POST /v1/analysis/*` ghi; `owner` gọi `/v1/admin/*` được, các role khác bị chặn.
8. **Retry kỷ luật:** lỗi hạ tầng tạm thời → retry tối đa 3 (giữ PAKTON); lỗi validation/tenant-treo → **không** retry, trả lỗi ngay.
9. **★ egress (C1):** prompt Review mang text hợp đồng của tenant → EgressPolicy route **local vLLM**, **không** gọi Claude; prompt thuần KB-luật → được ra Claude. Prompt không phân loại được → mặc định local. Audit ghi `llm_destination`.
10. **★ RLS fail-open (C2):** chạy query **bằng app-role thật** (không owner) *không* set `app.current_tenant` → **0 dòng** (chứng minh FORCE RLS + role non-owner); thử bằng role owner để lộ fail-open → test phải bắt.
11. **★ task IDOR (C6):** tenant B gọi `GET /v1/tasks/{task_id_của_A}` → **403**, không lộ kết quả.
12. **★ broker/zero-retention (C4):** phân tích tenant zero-retention → kiểm **broker/Redis/temp** không còn bytes hợp đồng; chỉ truyền `doc_ref`.

---

## 8. Build tasks (thứ tự cho member)

1. **Lift skeleton PAKTON** `API/` → FastAPI + Celery + SQLAlchemy + Alembic + Docker/compose/nginx chạy được với stub engine (trả echo). Giữ SSE step/tool, task_status, retry, warm-worker.
2. **Tenant core:** bảng `tenant`/`tenant_user` + migration thêm `tenant_id` vào bảng khách; `get_tenant_context` + `require_role`; mở rộng `SupabaseUser` đọc `tenant_id`.
3. **Cô lập 3 kho:** `get_tenant_db_session` + RLS policy; namespace vector theo tenant + KB `kb` read-only; namespace checkpointer. → chạy acceptance 2,3.
4. **Nhãn AI + response envelope** (mở rộng `response_template.py`) + áp ở API/SSE → acceptance 4.
5. **Observability:** OTel middleware + propagate qua Celery + `/metrics` + cost accounting + audit_log → acceptance 6.
6. **Tuân thủ:** `residency_region` + `retention_mode='zero'` (xử lý phù du, tắt persist) + key-per-tenant envelope encryption → acceptance 5.
7. **RBAC + quota/rate** per-tenant → acceptance 7,8. Nối gateway guard của W3.3.

---

## 9. Steal-list (file ĐÃ XÁC MINH trong `refs/PAKTON/PAKTON Framework/`)

| Cần | File (dòng) | Ghi chú |
|---|---|---|
| FastAPI app + endpoints | `API/api.py` — app `:27`; SSE step/tool `:247`; upload `:411`; task_status `:558`; conversations CRUD `:607,677,732,810`; health `:858` | lift routes, thêm `/v1` + tenant dep |
| SSE event stream | `API/api.py:305-398` | giữ format `data: {...}\n\n`, thêm `ai_label` mỗi event |
| Celery (retry, warm worker) | `API/tasks.py` — celery app `:24`; routes `:30`; warm archivist `:38-47,321-328`; retry `:49,77,186,273`; temp-file upload `:231-245` | giữ nguyên; thêm tenant header + fail-closed |
| Auth Supabase JWT toggle | `API/auth.py` — `SupabaseUser:17`; `verify_jwt_token:46,92-101`; `get_current_user:164-198` | mở rộng đọc `tenant_id`; dùng `role` để RBAC |
| Config env | `API/config.py` (`ENABLE_AUTHENTICATION:33`, Celery `:38-40`), `API/database/config.py:22` | thêm KMS/residency/retention env |
| SQLAlchemy session/engine | `API/database/config.py:25-37,40-60,79` | fork thành `get_tenant_db_session` + RLS var |
| Models | `API/database/models/{user.py:15-25,conversation.py:15-28}` | thêm `tenant_id` + bảng tenant |
| Repositories | `API/database/repositories/conversation_repository.py` | mọi query lọc theo tenant (RLS làm nền) |
| Alembic | `API/alembic/env.py`, `versions/001_initial.py`, `002_add_message_count.py` | thêm migration tenant + RLS policy |
| Langgraph Postgres checkpointer | `Archivist/src/Archivist/agent.py:14,118-137,307-321` | namespace thread theo tenant; tắt khi zero-retention |
| Vector indexer (Pinecone/Chroma) | `Archivist/src/Archivist/indexers/vectordb.py:3,14,20` | namespace/collection per-tenant + KB `kb` |
| Retriever interface (thiếu filter) | `Researcher/src/Researcher/retrievers/base.py:18,37` | **thêm** `as_of` + `tenant`/namespace (W3) |
| Response template | `API/response_template.py` | mở rộng envelope: `trace_id` + `ai_label` |
| Docker/compose/nginx | `API/{Dockerfile,docker-compose.yml:11-95}`, `deployment/nginx/{nginx.conf,pakton.site}`, `deployment/development/*` | services: rabbitmq, redis, api, worker, postgres:15-alpine, chroma |

---

## 10. Match-check (đối chiếu STEP 1 với PAKTON thực tế + `research_notes/Repo deep read/pakton.md`)

Đã mở và xác minh trực tiếp mã nguồn (read-only, không chạy). Tất cả khớp với prior notes `pakton.md §1,§7`:

- ✅ **Backend thật nằm dưới `PAKTON Framework/`** — `API/` là backend production (FastAPI+Celery+SQLAlchemy+Alembic+Docker/compose/nginx). Khớp `pakton.md §1`.
- ✅ **`API/api.py`:** FastAPI (`:27`), **Celery-async** (`send_task` `:462`), **SSE step/tool streaming** (`/query/stream_steps/sse:247`, event_stream `:305-398`), **document upload** (`/index/document/:411`), **task_status** (`:558`), **conversation CRUD** (`:607,677,732,810`). Đủ.
- ✅ **`API/tasks.py`:** Celery (`:24`), **retry** `max_retries=3`/`self.retry` (`:49,77,186,273`), **warm agent per-worker** (global `archivist` `:38-47` + `on_after_configure` `:321-328`).
- ✅ **SQLAlchemy models** `User`/`Conversation` (`models/user.py:15`, `conversation.py:15`) + **Alembic** (`001_initial`, `002_add_message_count`) + **auth Supabase JWT HS256 toggleable** (`auth.py`, `ENABLE_AUTHENTICATION` `config.py:33`) + **Docker/compose/nginx** (`docker-compose.yml:11-95`, `deployment/nginx/`).
- ✅ **Three-store split** xác nhận: SQL metadata (SQLAlchemy/Postgres) / **langgraph Postgres checkpointer** (`AsyncPostgresSaver` `agent.py:14,118-137`) / **vector store** (Pinecone hoặc ChromaDB `indexers/vectordb.py:3`).
- ✅ **GAP đã xác nhận bằng grep:**
  - **KHÔNG multi-tenancy/org-scoping/RBAC:** grep `tenant|organization|org_id|rbac|permission|authorize|workspace` toàn `PAKTON Framework/` chỉ trúng chuỗi HTTP "unauthorized" (`auth.py`), 1 docstring "unauthorized access" (`api.py:566`), 1 "organizations" trong prompt mẫu (`Researcher/.../prompts.py:44`). `role` có trên `SupabaseUser` (`auth.py:24`) nhưng **không bao giờ dùng phân quyền**. `conversations` chỉ khoá theo `user_email`, **không** tenant.
  - **KHÔNG effectivity/tenant filter trong retrieval:** `retrievers/base.py:37` là `retrieve(query, **kwargs)` — **không** `as_of`/`valid_from`/`tenant`/metadata-filter; grep `as_of|valid_from|valid_to|effectiv|in_force|temporal` chỉ trúng chữ "effective"/"temporal" trong docstring, không có cơ chế lọc hiệu lực nào.

**Không có mismatch nào** so với prior notes. Hai điểm làm rõ thêm (không mâu thuẫn, chỉ chính xác hơn để build):
1. PAKTON vector store là **Pinecone *hoặc* ChromaDB** chọn qua config (`indexers/vectordb.py:3,36`), compose mặc định mount **Chroma** (`docker-compose.yml:48,79,95`) — nên namespace-per-tenant của TraLuat phải viết cho cả hai backend (Pinecone namespace vs Chroma collection).
2. Checkpointer **fallback về không-persist** khi thiếu `DATABASE_URL` (`agent.py:136`) — tiện để map thẳng sang chế độ **zero-retention** của TraLuat (tắt checkpointer theo tenant).
