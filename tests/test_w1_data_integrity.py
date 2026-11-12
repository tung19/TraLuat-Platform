import datetime as dt

import pytest

from traluat.w1 import (
    derive_frbr_uri,
    extract_effective_overrides,
    extract_metadata,
    parse_structure,
)
from traluat.w1.metadata import DocMeta


def test_issuer_is_part_of_circular_identity():
    uris = {derive_frbr_uri(DocMeta(doc_number=f"01/2024/TT-{issuer}", doc_type="thong_tu"))
            for issuer in ("BTC", "BXD")}
    assert len(uris) == 2


def test_phased_exception_before_general_commencement_does_not_shift_whole_document():
    text = """Số: 99/2020/NĐ-CP
Hà Nội, ngày 15 tháng 6 năm 2020
Điều 1. Nội dung
Khoản 1 Điều 2 có hiệu lực kể từ ngày 01 tháng 01 năm 2022.
Nghị định này có hiệu lực kể từ ngày 01 tháng 01 năm 2021.
"""
    metadata = extract_metadata(text)
    assert metadata.date_issued == dt.date(2020, 6, 15)
    assert metadata.date_effective == dt.date(2021, 1, 1)
    assert extract_effective_overrides(text, "x") == {"x__dieu_2__khoan_1": dt.date(2022, 1, 1)}


def test_body_dates_cannot_become_issue_date_and_ambiguous_commencement_needs_review():
    text = """Số: 99/2020/NĐ-CP
Điều 1. Nội dung
Nghị định này có hiệu lực kể từ ngày 01 tháng 01 năm 2021.
Nghị định này có hiệu lực kể từ ngày 01 tháng 01 năm 2022.
"""
    metadata = extract_metadata(text)
    assert metadata.date_issued is None
    assert metadata.date_effective is None


def test_section_siblings_and_repeated_number_in_next_chapter_have_distinct_identity():
    units = parse_structure("Chương I\nMục 1\nĐiều 1. A\nMục 2\nĐiều 2. B\nChương II\nMục 1\nĐiều 3. C", "x")
    by_eid = {u.eid: u for u in units}
    assert len(by_eid) == len(units)
    assert by_eid["x__chuong_1__muc_1"].parent_eid == "x__chuong_1"
    assert by_eid["x__chuong_1__muc_2"].parent_eid == "x__chuong_1"
    assert by_eid["x__chuong_2__muc_1"].parent_eid == "x__chuong_2"


def test_point_continuation_is_not_assigned_to_parent_or_next_sibling():
    by_eid = {u.eid: u for u in parse_structure(
        "Điều 1. Nghĩa vụ\n1. Các việc:\na) Có giấy phép và\nđủ vốn.\nb) Báo cáo.\n2. Nghĩa vụ khác.", "x")}
    assert by_eid["x__dieu_1__khoan_1__diem_a"].text == "Có giấy phép và đủ vốn."
    assert by_eid["x__dieu_1__khoan_1"].text == "Các việc:"
    assert by_eid["x__dieu_1__khoan_1__diem_b"].text == "Báo cáo."
    assert by_eid["x__dieu_1__khoan_2"].text == "Nghĩa vụ khác."


def test_duplicate_article_is_rejected_for_human_structure_review():
    with pytest.raises(ValueError, match="trùng eId"):
        parse_structure("Điều 1. A\nĐiều 1. B", "x")
