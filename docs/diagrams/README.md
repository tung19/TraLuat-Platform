# Sơ đồ kiến trúc TraLuat

Lưu trữ trong repo (mở bằng trình duyệt, hoặc xem PNG).

| File | Nội dung |
|---|---|
| [`architecture.html`](architecture.html) · [.png](architecture.png) | **Cây phả hệ source** — 8 package (core/tools/w1-w6), 67 module, phụ thuộc 1 chiều (DAG). Cập nhật sau 4 refactor dọn kiến trúc. |
| [`request-flow-analyze.html`](request-flow-analyze.html) · [.png](request-flow-analyze.png) | **Luồng `POST /analyze`** — 12 chặng W5→W4→W3→W2 + nhánh fail-closed (deny/abstain) + bất biến pháp lý. |

## Nguyên tắc kiến trúc (một câu)
Phụ thuộc đi **một chiều lên trên, không có vòng**: `W2` (bitemporal core, nền) ← `W1`/`W3`/`tools` ← `W4` ← `W6` ← `W5` (biên API). `core` là cross-cutting. Mọi điểm-chờ-ngoài (model ML, API key, data thật) là một **Protocol port + stub chạy được** — cắm impl thật không đụng lõi.

> Vẽ lại: sửa `.html` rồi render bằng headless Chrome:
> `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --screenshot=architecture.png "file://$PWD/architecture.html"`
