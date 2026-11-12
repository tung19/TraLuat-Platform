# Mốc lưu công việc — 12/11/2026

Lưu theo yêu cầu “lưu lại hết đi”. Đây là checkpoint đang phát triển, không phải bản phát hành. Toàn bộ sửa audit, kết nối AI, tests và báo cáo được giữ lại. Chưa push hoặc triển khai vào database dev/production.

## Phần đã kiểm chứng trước checkpoint

- Sửa audit và kiểm tra quyền runtime/RLS, JWT, audit bền vững, bitemporal, grounding, ingestion/reference/template validation.
- API lookup/tóm tắt nối indexed FTS/BGE/RRF, Ollama local, NLI; trả nguồn trên giao diện. CLI reindex và reindex sau duyệt repeal/replaces đã có.
- Kết quả ngày 11/11: **383 core tests passed, 9 skipped; 8 tests model thật passed**. Các số này thuộc phiên bản trước các thay đổi đang dở dưới đây, không xác nhận toàn bộ checkpoint hiện tại.
- Log và hướng dẫn: [local-ai-wiring-2026-11-11.md](local-ai-wiring-2026-11-11.md), [reports/wiring-2026-11-11](../reports/wiring-2026-11-11/).

## Phần mới lưu, CHƯA hoàn tất nối hoặc kiểm thử tích hợp

Yêu cầu đang thực hiện: rà toàn source và nối các phần thư viện/pipeline chưa đến runtime.

1. `w1/source.py`: thêm tùy chọn `index`, `embedder`, `relations`; tạo chỉ mục trong savepoint của tài liệu, trích quan hệ sau khi nạp hết batch để có thể tìm văn bản đích xuất hiện phía sau; trả unresolved/indexed count. Chưa có CLI nhập liệu gọi các tùy chọn này, chưa có regression tests mới.
2. `core/knowledge_ops.py`: thêm `apply_reviewed_amendment` nhận nguyên văn thay thế của một unit có đích/ngày xác định; khóa relation, hash payload chống replay khác nội dung; cấm reject quan hệ đã áp. **Chưa gọi từ service/API**, chưa nối reindex vào đường amendment mới.
3. `w5/alerts.py`: thêm `sync_inbox` để phát sinh cảnh báo từ quan hệ đã commit cho tenant hiện tại dưới RLS, idempotent theo tenant/relation. **Chưa gọi từ `/alerts`**. Thiết kế này không gửi email/webhook và không cần quyền ghi chéo tenant.
4. Models và migration `0006_workflow_connections`: thêm hash payload amendment, thời điểm subscription, source relation của alert và unique index. **Chưa chạy migration/test PostgreSQL**; cần kiểm tương thích với schema tạo từ ORM và downgrade trước khi dùng.

Checkpoint đã qua Ruff `src tests scripts` và `git diff --check`. Chưa chạy lại full suite sau các thay đổi ở mục này. Không áp 0006 vào database thật cho đến khi kiểm chứng.

## Tiếp tục từ đây

- Hoàn tất và kiểm thử ba đường dữ liệu/amendment/inbox ở trên: quyền platform, rollback khi index lỗi, replay, hiệu lực, nhiều tenant và subscription tạo sau thay đổi.
- Nối API tạo/đọc tác vụ với `AnalysisTask` và Celery: commit job trước dispatch, handler được đăng ký thực, kiểm lại membership/quyền khi worker chạy, terminal-state idempotency, recovery cho job chưa gửi. Hiện `CeleryTaskQueue` vẫn scaffold và chưa có task endpoints. Không lưu bearer token vào payload.
- Nối NLIElementJudge, cấu hình checklist, lựa chọn multi-role vào runtime/API; không đánh đồng việc có adapter với chất lượng suy luận đã nghiệm thu.
- Đưa các tiện ích có sẵn (calculator, form, termbank, calendar) tới API có xác thực và validation; đảm bảo thiếu dữ liệu trả lỗi rõ ràng.
- Bổ sung CLI nhập JSONL đã duyệt → ingest/quan hệ/index; CLI rebuild projection Neo4j và eval nếu cần. Không gọi hook external trước commit; PostgreSQL vẫn là nguồn chuẩn.
- Rà temporal resolution, reranker tùy chọn và phần trả text khi draft/advisory abstain. Không giảm grounding để ép model trả lời.
- Cập nhật feature registry/báo cáo, chạy toàn bộ test trên database cô lập, chỉ báo đã nối cho những đường thực sự kiểm chứng.

## Môi trường và giới hạn

- Workspace: `/Users/tung/TungNT/Workplace/TraLuatPlatform`.
- `.venv` có model cache BGE/NLI; Ollama có `qwen2.5-coder:latest`, `mistral:latest`, `deepseek-r1:latest`. Qwen đã dùng trong smoke test, không phải model pháp lý đã nghiệm thu.
- Venv core riêng: `/private/tmp/traluat-fix-clean-venv` (có thể cần tạo lại nếu thư mục tạm bị dọn).
- Container audit `traluat-wire-20261111` đã được xóa sau kiểm thử. Tạo database/container test mới khi tiếp tục; không dùng `traluat-pg`/localhost:5433 hoặc Neo4j của người dùng làm fixture ghi dữ liệu.
- Không nạp corpus luật thật. Không tự gửi thông báo ra email/webhook. Không commit secret hoặc file `.env`; `.env.example` chỉ chứa mẫu cấu hình.
