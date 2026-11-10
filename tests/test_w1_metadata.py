"""W1 stage-4 — trích metadata header (pure, không cần DB)."""

import datetime as dt

from traluat.w1 import derive_frbr_uri, extract_metadata

D = dt.date

FULL_ND = """\
CHÍNH PHỦ

Số: 99/2020/NĐ-CP

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Hà Nội, ngày 15 tháng 6 năm 2020

NGHỊ ĐỊNH
Quy định về điều kiện kinh doanh

Điều 1. Phạm vi điều chỉnh
Nghị định này quy định về điều kiện kinh doanh.

Điều 5. Hiệu lực thi hành
Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 01 năm 2021.
"""


def test_extract_metadata_full_header():
    m = extract_metadata(FULL_ND)
    assert m.doc_number == "99/2020/NĐ-CP"
    assert m.doc_type == "nghi_dinh"          # suy từ hậu tố NĐ-CP
    assert m.authority_name == "CHÍNH PHỦ"
    assert m.date_issued == D(2020, 6, 15)
    assert m.date_effective == D(2021, 1, 1)
    assert derive_frbr_uri(m) == "trl:vn/nd/99/2020"


def test_hieu_luc_tu_ngay_ky():
    # 'kể từ ngày ký' → date_effective = date_issued
    t = "Số: 10/2022/QĐ-TTg\nngày 03 tháng 02 năm 2022\nQuyết định này có hiệu lực kể từ ngày ký."
    m = extract_metadata(t)
    assert m.doc_type == "quyet_dinh"
    assert m.date_effective == m.date_issued == D(2022, 2, 3)


def test_unknown_suffix_no_guess():
    # hậu tố lạ → doc_type=None (không gán bừa — ảnh hưởng authority_rank)
    m = extract_metadata("Số: 7/2021/XYZ-ABC")
    assert m.doc_number == "7/2021/XYZ-ABC" and m.doc_type is None
    assert derive_frbr_uri(m) is None
