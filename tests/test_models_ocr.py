"""Model THẬT VietOCR — OCREngine port (recognizer cấp dòng tiếng Việt). @slow.

Skip nếu chưa cài extra 'models' (vietocr) hoặc thiếu font Unicode."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

pytest.importorskip("vietocr")

_FONT = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
if not _FONT.exists():
    pytest.skip("thiếu font Unicode để render ảnh test", allow_module_level=True)

from traluat.w1.ocr_vietocr import VietOCREngine


@pytest.fixture(scope="module")
def ocr():
    return VietOCREngine()


def _render(text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (760, 70), "white")
    ImageDraw.Draw(img).text((12, 12), text, font=ImageFont.truetype(str(_FONT), 40), fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_ocr_vietnamese_line(ocr):
    out = ocr.extract(_render("Điều 1. Phạm vi điều chỉnh"))
    assert "Điều 1" in out and "Phạm vi" in out        # đọc đúng dấu tiếng Việt
