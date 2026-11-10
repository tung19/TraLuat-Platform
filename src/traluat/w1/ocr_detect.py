"""WP6 · OCR full-page — detector dòng + ghép recognizer → OCREngine hoàn chỉnh.

VietOCR (ocr_vietocr) chỉ nhận DÒNG đã cắt; ảnh TRANG luật cần detector đứng trước
để tìm các dòng. Thiết kế cắm-được:

  LineDetector (port) → list[bytes] các dòng đã cắt
  FullPageOCR(detector, recognizer)  ← chính nó LÀ OCREngine (cắm thẳng vào
  `ingest_source(ocr=...)` không đụng lõi)

- `PaddleLineDetector`: impl THẬT (paddleocr detection, lazy; defer tới khi cài model).
- `GridLineDetector`: baseline tất định không ML — chia trang thành dải ngang đều
  (demo/khởi động + test wiring; thay bằng Paddle/CRAFT khi có model).
"""

from __future__ import annotations

import io
from typing import Protocol, runtime_checkable


@runtime_checkable
class LineDetector(Protocol):
    def detect(self, image_bytes: bytes, lang: str = "vi") -> list[bytes]: ...


class GridLineDetector:
    """Chia ảnh trang thành `rows` dải ngang đều → bytes PNG mỗi dải. Không ML (tất
    định) — baseline/demo; cho văn bản dòng-đều. Thay bằng detector thật khi cần."""

    def __init__(self, rows: int = 1) -> None:
        if rows < 1:
            raise ValueError("rows ≥ 1")
        self.rows = rows

    def detect(self, image_bytes: bytes, lang: str = "vi") -> list[bytes]:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        band = max(1, h // self.rows)
        out = []
        for i in range(self.rows):
            top = i * band
            bottom = h if i == self.rows - 1 else (i + 1) * band
            buf = io.BytesIO()
            img.crop((0, top, w, bottom)).save(buf, format="PNG")
            out.append(buf.getvalue())
        return out


class PaddleLineDetector:
    """paddleocr text-detection → cắt bounding-box dòng → bytes (theo thứ tự trên→dưới).
    Lazy import; nêu rõ nếu thiếu `paddleocr`. (Defer: cần model download.)"""

    def __init__(self, *, ocr=None, lang: str = "vi") -> None:
        if ocr is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("PaddleLineDetector cần `paddleocr` (+ model)") from e
            ocr = PaddleOCR(use_angle_cls=False, det=True, rec=False, lang="vi")
        self._ocr = ocr

    def detect(self, image_bytes: bytes, lang: str = "vi") -> list[bytes]:  # pragma: no cover
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        boxes = self._ocr.ocr(arr, det=True, rec=False)[0] or []
        # sort theo y (trên→dưới) rồi cắt từng box
        def _top(b):
            return min(p[1] for p in b)
        crops = []
        for box in sorted(boxes, key=_top):
            xs = [p[0] for p in box]; ys = [p[1] for p in box]
            buf = io.BytesIO()
            img.crop((int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))).save(
                buf, format="PNG")
            crops.append(buf.getvalue())
        return crops


class FullPageOCR:
    """OCREngine đầy đủ: detect dòng → recognize từng dòng → ghép. Chính nó là OCREngine
    nên cắm thẳng `ingest_source(ocr=FullPageOCR(det, VietOCREngine()))`."""

    def __init__(self, detector: LineDetector, recognizer) -> None:
        self.detector = detector
        self.recognizer = recognizer

    def extract(self, image_bytes: bytes, lang: str = "vi") -> str:
        lines = self.detector.detect(image_bytes, lang)
        return "\n".join(
            self.recognizer.extract(ln, lang) for ln in lines).strip()
