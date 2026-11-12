"""Acceptance (W2 §8) + adversarial fixtures (engineering-principles #7).

Chứng minh moat #1 'văn bản tại ngày T' + các ca chaos audit đã bắt:
half-open biên · chưa-hiệu-lực · bãi bỏ · same-date order · idempotent ·
overlap fail-loud · chuyển tiếp · hồi tố (applies_from).
"""

from datetime import date

import pytest

from traluat.w2 import (
    BitemporalCorruption,
    EffectStatus,
    UnitVersion,
    apply_amendment,
    effect_status,
    governing_candidates,
    reconstruct_as_of,
    repeal,
)

D = date
EID = "nd99__dieu_3__khoan_2"


def _seed():
    """NĐ Điều 3 Khoản 2: 'A' hiệu lực 2021-01-01 (bản gốc)."""
    return [
        UnitVersion(
            unit_eid=EID, lang="vi",
            valid_from=D(2021, 1, 1), valid_to=None, text="Mức vốn 20 tỷ.",
        )
    ]


# ── ACCEPTANCE: văn bản tại ngày T qua một chuỗi sửa đổi ─────────────────────────
def test_van_ban_tai_ngay_T():
    vs = _seed()
    apply_amendment(vs, EID, "Mức vốn 50 tỷ.", D(2023, 6, 1), source_relation_id="r1")

    assert reconstruct_as_of(vs, EID, D(2020, 12, 31)) is None       # chưa hiệu lực
    assert reconstruct_as_of(vs, EID, D(2022, 1, 1)) == "Mức vốn 20 tỷ."
    assert reconstruct_as_of(vs, EID, D(2023, 5, 31)) == "Mức vốn 20 tỷ."
    assert reconstruct_as_of(vs, EID, D(2023, 6, 1)) == "Mức vốn 50 tỷ."  # biên: bản mới
    assert reconstruct_as_of(vs, EID, D(2025, 1, 1)) == "Mức vốn 50 tỷ."


def test_half_open_khong_off_by_one():
    """Tại as_of == effective_date: đúng MỘT dòng (bản mới), bản cũ đã đóng."""
    vs = _seed()
    apply_amendment(vs, EID, "B", D(2023, 6, 1))
    # không raise (không chồng nhau) + trả bản mới
    assert reconstruct_as_of(vs, EID, D(2023, 6, 1)) == "B"


# ── effect_status enum (không bool) ─────────────────────────────────────────────
def test_effect_status():
    vs = _seed()
    assert effect_status(vs, EID, D(2020, 1, 1)) is EffectStatus.NOT_YET
    assert effect_status(vs, EID, D(2022, 1, 1)) is EffectStatus.IN_FORCE
    assert effect_status(vs, "khong_ton_tai", D(2022, 1, 1)) is EffectStatus.ABSENT


# ── bãi bỏ (R4): hết hiệu lực vẫn cite được ──────────────────────────────────────
def test_repeal():
    vs = _seed()
    repeal(vs, EID, D(2024, 1, 1), source_relation_id="r_repeal")
    assert reconstruct_as_of(vs, EID, D(2023, 1, 1)) == "Mức vốn 20 tỷ."
    assert reconstruct_as_of(vs, EID, D(2024, 1, 1)) is None            # đã bãi bỏ
    assert effect_status(vs, EID, D(2024, 6, 1)) is EffectStatus.EXPIRED_CITABLE


# ── same-date fold theo order_key (G4-fix) ──────────────────────────────────────
def test_same_date_order_key():
    vs = _seed()
    apply_amendment(vs, EID, "C", D(2025, 1, 1), order_key=1, source_relation_id="rc")
    apply_amendment(vs, EID, "D", D(2025, 1, 1), order_key=2, source_relation_id="rd")
    # fold: order_key cao hơn (áp sau) thắng, KHÔNG tạo [d,d) zero-width
    assert reconstruct_as_of(vs, EID, D(2025, 1, 1)) == "D"
    open_at = [v for v in vs if v.valid_from == D(2025, 1, 1) and v.tx_to is None]
    assert len(open_at) == 1


# ── out-of-order / interval-split (slice-3): sửa đổi lọt GIỮA khoảng đã đóng ──────
def test_out_of_order_split():
    vs = _seed()                                   # [2021, ∞) = "A"
    apply_amendment(vs, EID, "C", D(2025, 1, 1), source_relation_id="r2025")  # → [2021,2025)A + [2025,∞)C
    # sửa đổi ĐẾN SAU nhưng hiệu lực 2023 (lệch thứ tự) → cắt khoảng [2021,2025)
    apply_amendment(vs, EID, "B", D(2023, 1, 1), source_relation_id="r2023")
    assert reconstruct_as_of(vs, EID, D(2022, 1, 1)) == "Mức vốn 20 tỷ."   # [2021,2023) giữ A
    assert reconstruct_as_of(vs, EID, D(2024, 1, 1)) == "B"                 # [2023,2025) mới
    assert reconstruct_as_of(vs, EID, D(2026, 1, 1)) == "C"                 # [2025,∞) giữ C
    # không chồng nhau (nếu chồng _assert_no_overlap đã raise)
    open_or_closed = [v for v in vs if v.tx_to is None]
    assert len(open_or_closed) == 3


# ── idempotent (chaos C1): replay cùng relation không nhân đôi ───────────────────
def test_idempotent_apply():
    vs = _seed()
    apply_amendment(vs, EID, "B", D(2023, 6, 1), source_relation_id="r1")
    n = len(vs)
    apply_amendment(vs, EID, "B", D(2023, 6, 1), source_relation_id="r1")  # replay
    assert len(vs) == n


# ── overlap fail-loud (chaos C2 / §11): KHÔNG corrupt im lặng ────────────────────
def test_overlap_raises():
    vs = _seed()
    # chèn tay một bản chồng nhau (mô phỏng 2 writer concurrent)
    vs.append(UnitVersion(EID, "vi", D(2022, 1, 1), None, "X"))
    with pytest.raises(BitemporalCorruption):
        reconstruct_as_of(vs, EID, D(2022, 6, 1))


# ── chuyển tiếp: hết hiệu lực nhưng điều khoản chuyển tiếp còn áp ─────────────────
def test_transitional():
    vs = [
        UnitVersion(EID, "vi", D(2019, 1, 1), D(2023, 1, 1), "cũ", transitional=True),
    ]
    assert effect_status(vs, EID, D(2024, 1, 1)) is EffectStatus.TRANSITIONAL_APPLIES


# ── hồi tố (A-fix): luật nhẹ hơn áp NGƯỢC qua applies_from ───────────────────────
def test_retroactive_applies_from():
    # Luật hình sự: hành vi 2019; luật 2023 (applies_from=2019) nhẹ hơn.
    eid = "blhs__dieu_X"
    vs = [
        UnitVersion(eid, "vi", D(2015, 1, 1), D(2023, 1, 1), "phạt nặng"),
        UnitVersion(eid, "vi", D(2023, 1, 1), None, "phạt nhẹ", applies_from=D(2010, 1, 1)),
    ]
    # reconstruct (valid-time): tại 2019 vẫn là luật đang-in-force lúc đó
    assert reconstruct_as_of(vs, eid, D(2019, 1, 1)) == "phạt nặng"
    # governing_candidates: PHẢI gồm CẢ 2 — luật@2019 + luật hồi tố 2023.
    # (lex-mitior chọn 'phạt nhẹ' là việc của tầng trên, KHÔNG phải hàm này.)
    cands = governing_candidates(vs, eid, D(2019, 1, 1))
    texts = {c.text for c in cands}
    assert texts == {"phạt nặng", "phạt nhẹ"}
    # bản hồi tố (nhẹ) có mặt để tầng lex-mitior so favorability
    assert any(c.applies_from == D(2010, 1, 1) and c.text == "phạt nhẹ" for c in cands)
