"""WP6 · OCR full-page — detector dòng + FullPageOCR (wiring, không cần ML/PG)."""

from __future__ import annotations

import io

import pytest

from traluat.w1 import FullPageOCR, GridLineDetector, OCREngine


class _FakeDetector:
    def __init__(self, crops):
        self._crops = crops

    def detect(self, image_bytes, lang="vi"):
        return self._crops


class _ByteRecognizer:
    """Recognizer giả: text = chính nội dung crop (đủ để kiểm ghép dòng)."""
    def extract(self, image_bytes, lang="vi"):
        return image_bytes.decode()


def test_full_page_joins_detected_lines():
    ocr = FullPageOCR(_FakeDetector([b"Dieu 1", b"Dieu 2", b"Dieu 3"]), _ByteRecognizer())
    assert ocr.extract(b"<page>") == "Dieu 1\nDieu 2\nDieu 3"


def test_full_page_is_ocrengine():
    # FullPageOCR thoả port OCREngine → cắm thẳng ingest_source(ocr=...)
    ocr = FullPageOCR(_FakeDetector([b"x"]), _ByteRecognizer())
    assert isinstance(ocr, OCREngine)


def test_grid_detector_splits_rows():
    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), "white").save(buf, format="PNG")
    crops = GridLineDetector(rows=3).detect(buf.getvalue())
    assert len(crops) == 3
    assert all(c[:4] == b"\x89PNG" for c in crops)              # mỗi dải là PNG hợp lệ


def test_grid_single_row_passthrough():
    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 20), "white").save(buf, format="PNG")
    assert len(GridLineDetector(rows=1).detect(buf.getvalue())) == 1


def test_grid_plus_recognizer_endtoend():
    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 60), "white").save(buf, format="PNG")

    class _Counter:
        def __init__(self): self.n = 0
        def extract(self, b, lang="vi"):
            self.n += 1
            return f"dong{self.n}"

    rec = _Counter()
    out = FullPageOCR(GridLineDetector(rows=2), rec).extract(buf.getvalue())
    assert out == "dong1\ndong2" and rec.n == 2                 # detect→recognize→ghép
