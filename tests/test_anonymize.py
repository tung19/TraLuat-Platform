"""CN-05 · ẩn danh bản án (NQ 03/2017) — thuần, không DB."""

from __future__ import annotations

from traluat.w1.anonymize import anonymize, is_judgment_type


def test_redacts_id_phone_email():
    txt = "Bị cáo mang CMND 123456789, CCCD 123456789012, ĐT 0912345678, mail a.b@x.vn."
    out, rep = anonymize(txt)
    assert "123456789012" not in out and "[CCCD]" in out
    assert "[CMND]" in out and "[PHONE]" in out and "[EMAIL]" in out
    assert rep.counts["cccd"] == 1 and rep.counts["phone"] == 1


def test_name_after_honorific_to_initial():
    out, rep = anonymize("Theo lời khai của ông Nguyễn Văn An và bà Trần Thị Bình.")
    assert "Nguyễn Văn A." in out and "Trần Thị B." in out
    assert "Nguyễn Văn An" not in out
    assert rep.counts["ten_nguoi"] == 2


def test_so_nha_redacted():
    out, _ = anonymize("Địa chỉ: số 25/3 đường Lê Lợi.")
    assert "[SO_NHA]" in out and "25/3" not in out


def test_legal_term_not_over_redacted():
    # không có xưng hô → tên trần KHÔNG bị che (tránh che nhầm địa danh/thuật ngữ)
    txt = "Căn cứ Bộ luật Dân sự và Nghị định Chính phủ."
    out, rep = anonymize(txt)
    assert out == txt and rep.total == 0


def test_is_judgment_type():
    assert is_judgment_type("ban_an") and is_judgment_type("an_le")
    assert not is_judgment_type("nghi_dinh") and not is_judgment_type(None)
