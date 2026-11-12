# Bằng chứng audit 10/11/2026

Báo cáo chính: [../audit-2026-11-10.md](../audit-2026-11-10.md).

- `core-tests.txt`: 256 test hiện có pass trên PostgreSQL audit riêng.
- `model-tests.txt`: 7 test BGE/NLI pass với model cache, offline.
- `ruff.json`: 126 diagnostics của source/tests hiện có.
- `repro_ai.py`, `repro_platform.py`: tái hiện lỗi bằng dữ liệu giả/mocks, không cần DB/network.
- `repro_data.py`: các ca W1/W2 thuần Python và PostgreSQL; URL bị giới hạn vào DB audit, mọi giao dịch rollback. Script lưu từ các ca đã kiểm chứng, bản lưu đã kiểm cú pháp.
- `repro_tools.py`: kiểm dữ liệu tham chiếu/template trên PostgreSQL audit riêng, rollback.
- `repro-ai-output.txt`, `repro-platform-output.txt`: output đã chạy lại từ bản script lưu trong repo.
- `additional-controls.md`: ghi chú static về model integrity, serving retrieval, benchmark, graph review gate.

Các repro là bằng chứng hành vi lỗi tại commit đã audit. Một số assertion cố ý xác nhận bug đang tồn tại; sau khi sửa code, cần chuyển chúng thành regression tests kỳ vọng hành vi đúng. Không coi việc repro chạy thành công là sản phẩm đúng.

Chạy từ gốc workspace, ví dụ:

```bash
PYTHONPATH=src .venv/bin/python reports/audit-2026-11-10/repro_ai.py
PYTHONPATH=src .venv/bin/python reports/audit-2026-11-10/repro_platform.py
```

Không chạy các script có DB vào database dev/production. Database audit cũ đã được dọn sau lượt kiểm chứng.
