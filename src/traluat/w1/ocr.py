"""OCR port (L1) — điểm cắm engine OCR thật (Vintern). Stub để chạy ngay.

OCR cần model ML (safetensors-only, pickle-RCE) → defer impl thật; ở đây chỉ port
+ stub. `ingest_source` gọi `extract` khi văn bản chỉ có ảnh.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OCREngine(Protocol):
    def extract(self, image_bytes: bytes, lang: str = "vi") -> str: ...


class NoOCR:
    """Chưa cấu hình OCR — fail rõ ràng (không giả vờ)."""

    def extract(self, image_bytes: bytes, lang: str = "vi") -> str:
        raise NotImplementedError("OCR chưa cấu hình — cắm engine Vintern/thật")


class PassthroughOCR:
    """Stub test/demo — trả text cố định đã nạp (không đụng model)."""

    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, image_bytes: bytes, lang: str = "vi") -> str:
        return self._text
