"""W1 stage-5 — trích quan hệ từ cue-phrase (pure, không cần DB)."""

import datetime as dt

from traluat.w1 import extract_relations

D = dt.date

AMEND_TEXT = """\
Căn cứ Luật Doanh nghiệp số 59/2020/QH14;
Điều 1. Sửa đổi, bổ sung Điều 3 của Nghị định số 99/2020/NĐ-CP.
Điều 2. Bãi bỏ Nghị định số 43/2010/NĐ-CP kể từ ngày 01/6/2023.
Điều 3. Nghị định này thay thế Nghị định số 99/2020/NĐ-CP.
"""


def _one(cands, rtype):
    xs = [c for c in cands if c.relation_type == rtype]
    assert len(xs) == 1, f"{rtype}: {xs}"
    return xs[0]


def test_extract_cue_phrases():
    cands = extract_relations(AMEND_TEXT)

    cite = _one(cands, "cites")
    assert cite.dst_doc_number == "59/2020/QH14" and cite.dst_dieu is None
    assert cite.confidence >= 0.9  # AUTO-SAFE: đủ ngưỡng graph-edge

    amend = _one(cands, "amends")
    assert amend.dst_doc_number == "99/2020/NĐ-CP" and amend.dst_dieu == 3
    assert amend.confidence < 0.9  # operative: DƯỚI ngưỡng → buộc người duyệt
    assert "sửa đổi, bổ sung" in amend.confidence_basis

    repeal = _one(cands, "repeals")
    assert repeal.dst_doc_number == "43/2010/NĐ-CP"
    assert repeal.effective_date == D(2023, 6, 1)  # bắt 'kể từ ngày 01/6/2023'

    replace = _one(cands, "replaces")
    assert replace.dst_doc_number == "99/2020/NĐ-CP" and replace.dst_dieu is None


def test_self_reference_not_extracted():
    # "Nghị định này" không có số hiệu → không sinh quan hệ (không bịa đích)
    assert extract_relations("Nghị định này có hiệu lực thi hành.") == []
