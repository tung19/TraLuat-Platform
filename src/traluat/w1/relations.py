"""Stage 5 — trích quan hệ quy phạm từ cue-phrase (RULE, không model).

Văn bản sửa đổi/thay thế/bãi bỏ dùng ngôn ngữ cố định → bắt được bằng luật:
  "sửa đổi, bổ sung Điều 5 của Nghị định số 99/2020/NĐ-CP" → amends
  "Nghị định này thay thế Nghị định số 43/2010/NĐ-CP"       → replaces
  "bãi bỏ … Nghị định số 99/2020/NĐ-CP"                     → repeals
  "căn cứ … / quy định tại … của Luật … số 59/2020/QH14"    → cites
  "quy định chi tiết / hướng dẫn thi hành …"                → guides

Mỗi quan hệ ra `review_status='needs_review'` khi nạp (ingest.load_relations_to_w2)
→ chạm materialize gate đã xây. KHÔNG bịa confidence (C2): confidence +
confidence_basis gắn CHÍNH cue-phrase đã khớp. Operative (amends/replaces/
repeals) đặt dưới ngưỡng AUTO-SAFE → BẮT BUỘC người duyệt; cites/guides là
cạnh đồ thị an toàn → confidence ≥ θ để auto khi gate cho phép.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

# số hiệu VB: 99/2020/NĐ-CP · 59/2020/QH14 · 15/2012/TT-BTC …
_RE_DOC_NUMBER = re.compile(r"\b(\d+/\d{4}/[A-ZĐ][A-ZĐ0-9]*(?:-[A-ZĐ0-9]+)*)\b")
_RE_DIEU_REF = re.compile(r"Điều\s+(\d+)")
_RE_NGAY = re.compile(r"kể từ ngày\s+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", re.IGNORECASE)

# (loại, [cue theo độ ưu tiên], confidence, auto-safe?) — cụ thể trước chung.
_CUES: list[tuple[str, list[str], float]] = [
    ("amends", ["sửa đổi, bổ sung", "sửa đổi", "bổ sung"], 0.75),
    ("replaces", ["thay thế"], 0.75),
    ("repeals", ["bãi bỏ", "hết hiệu lực"], 0.75),
    ("guides", ["quy định chi tiết", "hướng dẫn thi hành", "hướng dẫn"], 0.92),
    ("cites", ["căn cứ", "theo quy định tại", "quy định tại"], 0.92),
]


@dataclass
class RelationCandidate:
    relation_type: str           # amends|replaces|repeals|guides|cites
    dst_doc_number: str          # số hiệu VB đích (bắt buộc — tự-chiếu "VB này" bị loại)
    dst_dieu: int | None         # Điều cụ thể nếu có, else None (cấp văn bản)
    effective_date: dt.date | None
    confidence: float
    confidence_basis: str        # "rule:cue='…'" — truy vết, không bịa
    evidence_span: str


def _split_clauses(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text)
    # tách theo dòng rồi theo ranh câu (. ; :) — mỗi mệnh đề 1 cue + 1 đích
    out: list[str] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            out.extend(p.strip() for p in re.split(r"(?<=[.;:])\s+", ln) if p.strip())
    return out


def _effective_date(clause: str) -> dt.date | None:
    if (m := _RE_NGAY.search(clause)):
        d, mo, y = (int(g) for g in m.groups())
        try:
            return dt.date(y, mo, d)
        except ValueError:
            return None
    return None


def extract_relations(text: str, src_slug: str | None = None) -> list[RelationCandidate]:
    """Quét cue-phrase → RelationCandidate. Pure; không chạm DB."""
    cands: list[RelationCandidate] = []
    for clause in _split_clauses(text):
        low = clause.lower()
        hit = next(
            ((rtype, phrase, conf) for rtype, phrases, conf in _CUES
             for phrase in phrases if phrase in low),
            None,
        )
        if hit is None:
            continue
        rtype, phrase, conf = hit
        eff = _effective_date(clause)
        dieu = int(m.group(1)) if (m := _RE_DIEU_REF.search(clause)) else None
        for dm in _RE_DOC_NUMBER.finditer(clause):  # 1 mệnh đề có thể trỏ nhiều VB
            cands.append(RelationCandidate(
                relation_type=rtype, dst_doc_number=dm.group(1), dst_dieu=dieu,
                effective_date=eff, confidence=conf,
                confidence_basis=f"rule:cue='{phrase}'",
                evidence_span=clause[:240],
            ))
    return cands
