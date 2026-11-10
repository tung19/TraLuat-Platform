"""VietOCREngine — impl THẬT của OCREngine port (VietOCR, OCR tiếng Việt chuyên dụng).

VietOCR = recognizer cấp DÒNG (VGG+Transformer). Full-page cần detector dòng (CRAFT/
PaddleOCR) ở trước — defer; port này nhận ảnh một-dòng/vùng đã cắt. Nhẹ (~150MB),
CPU đủ nhanh. (Chọn VietOCR vì Vintern-1B remote-code chưa tương thích transformers 5.)

Import lười. `line_images` cho nhiều dòng đã cắt → nối lại.
"""

from __future__ import annotations

import io

_MODEL = "vgg_transformer"


def _pillow_compat() -> None:
    # vietocr cũ dùng Image.ANTIALIAS (bỏ từ Pillow 10) → trỏ về LANCZOS.
    from PIL import Image
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.LANCZOS  # type: ignore[attr-defined]


class VietOCREngine:
    def __init__(self, model_name: str = _MODEL, device: str = "cpu") -> None:
        _pillow_compat()
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        cfg = Cfg.load_config_from_name(model_name)
        cfg["device"] = device
        cfg["predictor"]["beamsearch"] = False
        self._p = Predictor(cfg)

    def _predict(self, img) -> str:
        return self._p.predict(img).strip()

    def extract(self, image_bytes: bytes, lang: str = "vi") -> str:
        """OCR 1 ảnh (một dòng/vùng đã cắt)."""
        from PIL import Image
        return self._predict(Image.open(io.BytesIO(image_bytes)).convert("RGB"))

    def extract_lines(self, line_images: list[bytes], lang: str = "vi") -> str:
        """OCR nhiều dòng đã cắt → nối bằng xuống dòng (chờ detector ở trước)."""
        return "\n".join(self.extract(b, lang) for b in line_images)
