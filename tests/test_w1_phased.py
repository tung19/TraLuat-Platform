"""W1 phased-commencement — hiệu lực lệch cấp Điều/Khoản (pure)."""

import datetime as dt

from traluat.w1 import extract_effective_overrides, extract_metadata

D = dt.date

PHASED = """\
Số: 20/2022/NĐ-CP
Hà Nội, ngày 10 tháng 1 năm 2022

Điều 1. Nội dung
Quy định chung.

Điều 2. Khoản đặc biệt
1. Quy định A.
2. Quy định B.

Điều 3. Chuyển tiếp
1. Quy định C.

Điều 5. Hiệu lực thi hành
1. Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 3 năm 2022.
2. Khoản 2 Điều 2 của Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 7 năm 2022.
3. Điều 1 của Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 6 năm 2022.
4. Điều 3 của Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 9 năm 2022.
"""


def test_doc_level_effective_still_works():
    # hiệu lực cấp VB (khoản 1, 'Nghị định này …') KHÔNG lẫn vào override
    assert extract_metadata(PHASED).date_effective == D(2022, 3, 1)


def test_phased_overrides():
    ov = extract_effective_overrides(PHASED, "nd20")
    assert ov == {
        "nd20__dieu_2__khoan_2": D(2022, 7, 1),
        "nd20__dieu_1": D(2022, 6, 1),
        "nd20__dieu_3": D(2022, 9, 1),
    }
