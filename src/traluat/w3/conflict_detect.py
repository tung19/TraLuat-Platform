"""FR-41 — PHÁT HIỆN xung đột quy phạm, rồi GIẢI bằng W2.resolve_conflict.

'Luật nói A, Thông tư nói B → cái nào thắng': tìm cặp điều (khác văn bản) cùng chủ
đề nhưng quy định ĐẠI LƯỢNG khác nhau (vd thời hạn 30 ngày vs 15 ngày) → nghi xung
đột → đẩy sang resolve_conflict (lex superior/posterior/abstain). Finding type thứ 3.

Slice-1 TẤT ĐỊNH: phát hiện mâu thuẫn SỐ (deterministic, chắc) + quan hệ 'conflicts'
đã-flag. Mâu thuẫn NGỮ NGHĨA (A cho phép, B cấm — không số) = defer, cắm qua
SemanticConflictDetector port (ML/NLI). KHÔNG tự quyết thắng — đó là resolve_conflict.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2 import repo
from ..w2.bitemporal import EffectStatus
from ..w2.models import Document, NormRelation, Unit
from .chunker import build_chunks

_APPLICABLE = {EffectStatus.IN_FORCE, EffectStatus.TRANSITIONAL_APPLIES}

_RE_QTY = re.compile(
    r"(\d[\d.]*)\s*(ngày|tháng|năm|tuần|giờ|tỷ|triệu|nghìn|đồng|%|phần trăm|lần)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STOP = {"và", "hoặc", "của", "các", "những", "được", "là", "khi", "theo", "cho",
         "với", "một", "này", "đó", "phải", "để", "từ", "trong", "tại", "về"}
_UNIT_WORDS = {"ngày", "tháng", "năm", "tuần", "giờ", "tỷ", "triệu", "nghìn",
               "đồng", "phần", "trăm", "lần"}


def _quantities(text: str) -> dict[str, set[int]]:
    """unit → tập số (vd {'ngày': {30}}). Để so lệch cùng đơn vị."""
    out: dict[str, set[int]] = {}
    for num, unit in _RE_QTY.findall(unicodedata.normalize("NFC", text).lower()):
        try:
            n = int(num.replace(".", ""))
        except ValueError:
            continue
        out.setdefault(unit.lower(), set()).add(n)
    return out


def _topic_tokens(text: str) -> set[str]:
    toks = _TOKEN_RE.findall(unicodedata.normalize("NFC", text).lower())
    return {t for t in toks if t not in _STOP and t not in _UNIT_WORDS
            and len(t) > 1 and not t.isdigit()}


@dataclass
class ConflictCandidate:
    eid_a: str
    eid_b: str
    kind: str          # numeric_divergence | explicit_relation
    evidence: str


@dataclass
class ConflictFinding:
    candidate: ConflictCandidate
    resolution: "repo.ConflictResult"


@runtime_checkable
class SemanticConflictDetector(Protocol):
    """Phát hiện mâu thuẫn NGỮ NGHĨA (A cho phép / B cấm — không số). Cắm NLI/model."""
    def detect(self, pairs: list[tuple[str, str, str, str]]) -> list[ConflictCandidate]:
        ...  # pairs = (eid_a, text_a, eid_b, text_b)


class NoSemantic:
    """Stub — chưa cắm model ngữ nghĩa (chỉ dò mâu thuẫn số)."""
    def detect(self, pairs: list[tuple[str, str, str, str]]) -> list[ConflictCandidate]:
        return []


def detect_conflicts(
    session: Session, scope_frbr_uris: list[str], as_of: dt.date, *,
    min_topic_overlap: int = 2, lang: str = "vi", semantic: SemanticConflictDetector | None = None,
) -> list[ConflictCandidate]:
    """Tìm cặp điều (KHÁC văn bản) nghi xung đột tại as_of. Chỉ áp-dụng-được.

    semantic = SemanticConflictDetector: bắt thêm mâu thuẫn NGỮ NGHĨA (không số) trên
    các cặp cùng chủ đề. None = chỉ dò mâu thuẫn số (tất định)."""
    # gom chunk áp-dụng-được theo từng VB
    per_doc: list[tuple[str, list]] = []
    for uri in scope_frbr_uris:
        chunks = [c for c in build_chunks(session, uri, as_of, lang)
                  if c.effect_status in _APPLICABLE]
        per_doc.append((uri, chunks))

    cands: list[ConflictCandidate] = []
    topical_pairs: list[tuple[str, str, str, str]] = []
    # mâu thuẫn SỐ: cặp xuyên văn bản, cùng chủ đề, lệch đại lượng cùng đơn vị
    for i in range(len(per_doc)):
        for j in range(i + 1, len(per_doc)):
            for ca in per_doc[i][1]:
                qa, ta = _quantities(ca.span_text), _topic_tokens(ca.span_text)
                for cb in per_doc[j][1]:
                    if len(ta & _topic_tokens(cb.span_text)) < min_topic_overlap:
                        continue
                    topical_pairs.append((ca.unit_eid, ca.span_text, cb.unit_eid, cb.span_text))
                    qb = _quantities(cb.span_text)
                    diverge = [u for u in qa.keys() & qb.keys() if qa[u] != qb[u]]
                    if diverge:
                        u = diverge[0]
                        cands.append(ConflictCandidate(
                            ca.unit_eid, cb.unit_eid, "numeric_divergence",
                            f"{u}: {sorted(qa[u])} vs {sorted(qb[u])}"))

    if semantic is not None:
        cands.extend(semantic.detect(topical_pairs))   # mâu thuẫn ngữ-nghĩa (model)
    cands.extend(_explicit_conflicts(session, scope_frbr_uris))
    return cands


def _explicit_conflicts(session: Session, scope_frbr_uris: list[str]) -> list[ConflictCandidate]:
    """Quan hệ 'conflicts' đã-flag (W1 cue / người nhập) trong phạm vi."""
    doc_ids = list(session.scalars(
        sa.select(Document.id).where(Document.frbr_uri.in_(scope_frbr_uris))))
    rows = session.execute(
        sa.select(NormRelation.src_unit_id, NormRelation.dst_unit_id).where(
            NormRelation.relation_type == "conflicts",
            NormRelation.src_doc_id.in_(doc_ids), NormRelation.dst_doc_id.in_(doc_ids),
        )
    ).all()
    out = []
    for su, du in rows:
        if su and du:
            a = session.scalar(sa.select(Unit.eid).where(Unit.id == su))
            b = session.scalar(sa.select(Unit.eid).where(Unit.id == du))
            if a and b:
                out.append(ConflictCandidate(a, b, "explicit_relation", "norm_relation:conflicts"))
    return out


def find_and_resolve_conflicts(
    session: Session, scope_frbr_uris: list[str], as_of: dt.date, *,
    min_topic_overlap: int = 2, question_type: str = "general", lang: str = "vi",
    pack=None, semantic: SemanticConflictDetector | None = None,
) -> list[ConflictFinding]:
    """Phát hiện → giải (lex superior/posterior/abstain). KHÔNG auto khi mơ hồ (#6).

    pack = JurisdictionPack (W6) → bơm thang bậc theo vùng tài phán; None = VN mặc định.
    semantic = SemanticConflictDetector → bắt thêm mâu thuẫn ngữ-nghĩa."""
    rank_fn = pack.rank_of if pack is not None else None
    findings = []
    for c in detect_conflicts(session, scope_frbr_uris, as_of,
                              min_topic_overlap=min_topic_overlap, lang=lang, semantic=semantic):
        res = repo.resolve_conflict(session, [c.eid_a, c.eid_b], as_of,
                                    question_type, rank_fn=rank_fn)
        findings.append(ConflictFinding(c, res))
    return findings
