"""W1 stage-3 — parse cấu trúc + eId (pure, không cần DB)."""

from traluat.w1 import parse_structure

SAMPLE = """\
Chương I
NHỮNG QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
Nghị định này quy định về điều kiện kinh doanh.

Điều 3. Điều kiện
1. Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc.
2. Mức vốn pháp định tối thiểu là 20 tỷ đồng, gồm:
a) vốn góp bằng tiền;
b) tài sản khác.

Chương II
TỔ CHỨC THỰC HIỆN

Điều 5. Thẩm quyền
Cơ quan đăng ký kinh doanh có thẩm quyền.
"""


def test_parse_structure_eids_and_tree():
    us = parse_structure(SAMPLE, "nd99")
    by = {u.eid: u for u in us}

    # eId đúng + lồng theo cha
    assert "nd99__chuong_1" in by
    assert "nd99__dieu_3" in by
    assert "nd99__dieu_3__khoan_1" in by
    assert "nd99__dieu_3__khoan_2" in by
    assert "nd99__dieu_3__khoan_2__diem_a" in by
    assert "nd99__dieu_3__khoan_2__diem_b" in by

    # cây: Điều dưới Chương (số Điều toàn văn bản, nhưng parent cây = Chương)
    assert by["nd99__dieu_3"].parent_eid == "nd99__chuong_1"
    assert by["nd99__dieu_5"].parent_eid == "nd99__chuong_2"
    assert by["nd99__dieu_3__khoan_2"].parent_eid == "nd99__dieu_3"
    assert by["nd99__dieu_3__khoan_2__diem_a"].parent_eid == "nd99__dieu_3__khoan_2"

    # nội dung
    assert "15 ngày" in by["nd99__dieu_3__khoan_1"].text
    assert "20 tỷ" in by["nd99__dieu_3__khoan_2"].text
    assert by["nd99__dieu_3__khoan_2__diem_a"].text == "vốn góp bằng tiền;"
    # kết cấu không có nội dung riêng
    assert by["nd99__chuong_1"].text is None
    # dòng nối tiếp gắn vào Điều 1
    assert "Nghị định này quy định" in by["nd99__dieu_1"].text
