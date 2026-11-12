# Kiểm chứng kết nối AI local — 2026-11-11

Phạm vi code và hướng dẫn: [local-ai-wiring-2026-11-11.md](../../docs/local-ai-wiring-2026-11-11.md).

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Toàn bộ core suite, venv sạch, PostgreSQL cô lập | 383 passed, 9 skipped | [core-tests.log](core-tests.log) |
| API với Qwen + BGE + NLI thật; BGE/NLI unit/integration | 8 passed | [local-model-tests.log](local-model-tests.log) |
| Ruff `src tests scripts` | Pass | Tool output của đợt chạy |
| `git diff --check` | Pass | Tool output |
| `uv lock --check --offline` | Pass, 141 packages | Tool output |
| Node kiểm cú pháp 7 inline scripts | Pass | Tool output; chưa kiểm tương tác browser |
| Docker Compose config | Pass | Chỉ kiểm config bằng giá trị placeholder; chưa chạy container AI |

Test dùng PostgreSQL 16 + vector + PostGIS trong container tạm `traluat-wire-20261111`, tmpfs, localhost:55433. Chỉ database này được migration/test ghi dữ liệu. Dữ liệu luật trong phép thử hoàn toàn giả, tên `synthetic:*`; không phải luật đã được duyệt. Database dev localhost:5433 không được migrate hoặc nạp dữ liệu trong đợt này. Container tạm được dọn sau kiểm thử.

Model local hiện có: `qwen2.5-coder:latest`, `BAAI/bge-m3`, `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`. BGE/NLI chạy từ cache với `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`; không tải model mới. Hai câu trả lời theo ngày và câu hỏi ngoài nguồn được kiểm tra qua HTTP API với login DB non-owner/JWT hợp lệ. `mistral:latest` được thử trước đó nhưng mất cụm “làm việc”, bị grounding chặn; không dùng để báo đạt.

Lệnh kiểm chứng (URL được provision riêng):

```bash
TEST_DATABASE_URL="$ISOLATED_TEST_DATABASE_URL" REQUIRE_TEST_DATABASE=1 \
  /private/tmp/traluat-fix-clean-venv/bin/python -m pytest -q tests

TEST_DATABASE_URL="$ISOLATED_TEST_DATABASE_URL" REQUIRE_TEST_DATABASE=1 \
  RUN_LOCAL_AI_TESTS=1 LOCAL_TEST_MODEL=qwen2.5-coder:latest \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m pytest -q -s tests/test_models_local_pipeline.py \
  tests/test_models_bge.py tests/test_models_nli.py
```

Core skip test local-model opt-in và các extra không cài trong venv sạch; model được kiểm riêng ở dòng thứ hai. Warning Starlette/httpx không làm test lỗi. Chưa nghiệm thu corpus pháp lý thật, tải lớn, model quality, OCR/Neo4j/KMS hoặc nghiệp vụ soạn thảo/phân tích bằng gold thật. Các thay đổi vẫn ở workspace, chưa commit/push.
