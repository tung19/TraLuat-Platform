# Kết nối AI local và chỉ mục — 11/11/2026

Đã nối đường chạy API tới chỉ mục PostgreSQL, BGE-M3, model Ollama và NLI thật. Kiểm thử đầu cuối dùng dữ liệu giả trong database riêng; chưa nạp dữ liệu luật thật, chưa áp migration hay triển khai vào database dev/production.

## Luồng hiện có

`Câu hỏi + ngày áp dụng → xác thực/tenant → FTS + vector BGE → RRF → đối chiếu nội dung canonical → Ollama → kiểm từng claim/quote + hiệu lực + NLI → câu trả lời và nguồn`

- `app_from_env` nạp BGE/NLI một lần mỗi process, truyền cùng các adapter vào lookup, tóm tắt, reasoning, tư vấn và soạn đơn. Những nghiệp vụ sau vẫn cần acceptance riêng; việc nối adapter không chứng minh chất lượng tư vấn hoặc soạn thảo.
- Runtime đọc bảng `chunk`, không dựng/embedding toàn kho mỗi câu hỏi. Nhánh từ khóa dùng PostgreSQL FTS `simple`/`ts_rank_cd`, **chưa phải BM25 tiếng Việt**. Có cổng reranker tùy chọn nhưng chưa cấu hình cross-encoder thật.
- Vector được gắn danh tính model/revision; không so sánh vector khác model. Migration `0005_embedding_identity` giữ vector cũ nhưng để identity NULL: phải reindex để dùng nhánh semantic.
- Lọc phạm vi văn bản/ngôn ngữ/ngày; `scope_frbr_uris: []` nghĩa là không chọn văn bản nào. Chỉ mục lệch nội dung nguồn canonical bị loại trước khi gọi model.
- Model trả JSON gồm `text` và các `unit_eid/claim/quote`. Sai định dạng, timeout, nguồn thiếu, claim sai hoặc không được NLI hỗ trợ sẽ không thành câu trả lời hợp lệ. Lỗi transport/output local được trả có kiểm soát và audit `failed` ở các service sinh nội dung.
- API lookup/tóm tắt trả `sources`, `as_of`, `model`, `is_demo`; trang `/tools` hiển thị nguyên văn nguồn để mở đối chiếu. `/ai/status` yêu cầu token và cho biết model, kết nối, BGE/NLI, số tài liệu/chunk. Số chunk không phải chứng nhận độ phủ hay chất lượng dữ liệu.
- Duyệt và áp dụng `repeals/replaces` qua service sẽ reindex văn bản đích ở các ngôn ngữ hiện có trong **cùng transaction PostgreSQL** khi dùng IndexedRetriever. `amends` vẫn cần payload được duyệt, không tự đoán nội dung sửa.
- CLI reindex dùng cho dữ liệu nhập sau này. Import trực tiếp bằng pipeline/library phải gọi reindex sau khi đã duyệt và lưu dữ liệu.

## Model và cấu hình

Ba chế độ: `disabled` (mặc định nếu không đặt biến), `demo` (Echo tường minh), `local` (model thật). Không tự chuyển sang Echo hoặc cloud khi local lỗi. Ollama phải công bố model local qua `/api/show`; model cloud/remote bị từ chối. Backend `compatible` dành cho server riêng do người vận hành quản lý, mới kiểm bằng HTTP mock trong đợt này.

Profile đã chạy trên máy này:

| Vai trò | Model |
|---|---|
| Embedding 1024 chiều | `BAAI/bge-m3` |
| Sinh câu trả lời | `qwen2.5-coder:latest` qua Ollama |
| Kiểm quan hệ claim/nguồn | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` |

Qwen là model có sẵn dùng để kiểm chứng tích hợp, **không phải model pháp lý đã được nghiệm thu**. Trong phép thử cùng một nguồn giả, `mistral:latest` bỏ cụm “làm việc”; grounding đã chặn đầu ra đó. Không giảm tiêu chuẩn grounding để ép model trả lời. Tag `latest` có thể đổi; khi nghiệm thu cần cố định artifact/digest và bộ gold.

Adapter local dùng [API tương thích OpenAI của Ollama](https://docs.ollama.com/api/openai-compatibility). Không tải model mới trong đợt kiểm thử. BGE/NLI mặc định `TRALUAT_MODELS_OFFLINE=1`; thiếu model cache thì khởi động thất bại rõ ràng.

## Khởi động khi đã provision database và danh tính

Xem [hướng dẫn quyền DB/JWT](audit-fixes-2026-11-10.md#áp-dụng-migration-và-khởi-động). Các biến URL/secret dưới đây phải lấy từ môi trường triển khai, không dùng login quản trị làm login API.

```bash
uv sync --locked --extra geo --extra models

# Connection quản trị migration, sau khi đối soát dữ liệu cũ.
DATABASE_URL="$MIGRATION_DATABASE_URL" .venv/bin/alembic upgrade head

# Ollama phải đang chạy và đã có model được chọn.
export TRALUAT_AI_MODE=local
export TRALUAT_LOCAL_BACKEND=ollama
export TRALUAT_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export TRALUAT_LOCAL_MODEL=qwen2.5-coder:latest
export TRALUAT_MODELS_OFFLINE=1
export TRALUAT_EMBED_MODEL=BAAI/bge-m3
export TRALUAT_NLI_MODEL=MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7

# DATABASE_URL: non-owner runtime login; JWT_SECRET/issuer/audience đã cấu hình.
.venv/bin/uvicorn traluat.w5.asgi:app_from_env --factory --host 127.0.0.1 --port 8000
```

`.env.example` chỉ là mẫu, Uvicorn không tự nạp file này. Có thể export các biến hoặc dùng trình quản lý môi trường. `TRALUAT_MODEL_DEVICE=cpu` ép CPU; mặc định model tự chọn thiết bị. Có thể cố định `TRALUAT_EMBED_REVISION` và `TRALUAT_NLI_REVISION` bằng revision đã cache.

Compose hiện hỗ trợ truyền cấu hình AI và `TRALUAT_API_EXTRAS=geo,models`. Nếu chạy API trong container, endpoint Ollama trên host phải là `http://host.docker.internal:11434/v1`, không phải `127.0.0.1`. Cần provision/mount model cache trong container trước khi bật offline. Đợt này kiểm API trên host, chưa nghiệm thu container AI; không coi việc đổi biến là đã triển khai xong.

## Sau khi nạp dữ liệu được duyệt

Chạy bằng connection có quyền ghi KB, cùng model/revision embedding với API:

```bash
DATABASE_URL="$KB_WRITER_DATABASE_URL" .venv/bin/python -m traluat.tools.reindex --all
# Hoặc một/một số văn bản:
DATABASE_URL="$KB_WRITER_DATABASE_URL" .venv/bin/python -m traluat.tools.reindex --frbr 'FRBR_CUA_VAN_BAN'
# Lặp với --lang en nếu kho có bản EN đã được duyệt.
```

CLI không crawl, seed dữ liệu giả hoặc chạy migration. `--lexical-only` tạo chỉ mục từ khóa và thay thế vector của phạm vi reindex; chỉ dùng khi chủ ý chạy không có embedding. Mỗi văn bản là một transaction. Vector sai kích thước/không hữu hạn/rỗng bị chặn trước khi xóa chỉ mục cũ.

Kiểm tra qua token hợp lệ có membership trong DB:

```bash
curl -sS http://127.0.0.1:8000/ai/status -H "Authorization: Bearer $ACCESS_TOKEN"
curl -sS http://127.0.0.1:8000/lookup \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"Câu hỏi cần tra cứu", "as_of":"2026-11-11"}'
```

Kho rỗng hoặc không đủ căn cứ sẽ abstain. Không cần nạp dữ liệu giả vào kho thật để làm giao diện có câu trả lời.

## Bằng chứng và giới hạn

- Core trên venv sạch và PostgreSQL 16/vector/PostGIS cô lập: **383 passed, 9 skipped**.
- BGE/NLI thật và API + Qwen thật, dùng cache offline: **8 passed**. Cùng một câu hỏi giả trả đúng phiên bản 15 ngày làm việc tại 2022 và 30 ngày làm việc tại 2024; câu hỏi ngoài nguồn abstain.
- Test hồi quy có lỗi provider/JSON, không fallback cloud, scope rỗng, chỉ mục cũ, model embedding khác, vector lỗi, audit bền vững, reindex sau duyệt repeal và nguồn API.
- Log: [reports/wiring-2026-11-11](../reports/wiring-2026-11-11/). Ruff và kiểm tra cú pháp JS chạy riêng.

Đây là bằng chứng đường nối hoạt động, không phải điểm chính xác pháp lý. Còn cần corpus/gold được duyệt, benchmark hỏi đáp nhiều loại câu hỏi, cross-encoder/BM25 nếu cần, nghiệm thu summary/reasoning/drafting, payload amendment, outbox/fan-out, identity/KMS/residency và kiểm tải. Không áp dữ liệu test hoặc migration vào PostgreSQL dev 5433 trong đợt này.
