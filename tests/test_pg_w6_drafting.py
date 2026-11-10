"""WP2 — FR-34 PetitionDraftService: soạn đơn từ template, grounded."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from traluat.w1 import build_ingest, load_to_w2
from traluat.tools.templates import add_template, match_templates
from traluat.w2.db import make_engine
from traluat.w3 import EchoLLMGateway
from traluat.w6 import PetitionDraftService

D = dt.date
FRBR = "trl:vn/nd/99/2020"
from tests.test_w1_structure import SAMPLE  # noqa: E402


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.template')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("template chưa migrate")
    s = Session(bind=conn, future=True)
    load_to_w2(s, frbr_uri=FRBR, doc_type="nghi_dinh", date_effective=D(2021, 1, 1),
               units=build_ingest(SAMPLE, "nd99"), doc_number="99/2020/NĐ-CP")
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def test_draft_from_template_grounded(session: Session):
    add_template(session, "don_dang_ky", "Đơn đăng ký doanh nghiệp",
                 "CỘNG HÒA XÃ HỘI... Đơn đăng ký. Vốn pháp định: {von}. Căn cứ: {can_cu}.",
                 slots=["von", "can_cu"])
    assert match_templates(session, kind="don_dang_ky")      # TES có mẫu

    svc = PetitionDraftService(session, gateway=EchoLLMGateway())
    r = svc.draft("don_dang_ky", "vốn pháp định tối thiểu của doanh nghiệp", D(2022, 1, 1))
    assert not r.abstain and r.template_id is not None
    assert "nd99__dieu_3__khoan_2" in r.citations            # draft có trích dẫn điều luật
    assert r.ai_label is True


def test_draft_abstains_without_template(session: Session):
    svc = PetitionDraftService(session, gateway=EchoLLMGateway())
    r = svc.draft("khong_co_mau", "x", D(2022, 1, 1))
    assert r.abstain and r.reason == "no_template"


def test_fill_template_form_validates_and_fills(session: Session):
    # FR-38: biểu mẫu có cấu trúc + validation qua template store
    from traluat.tools.templates import fill_template
    add_template(session, "don_xin_phep",
                 "Đơn xin phép", "Tôi {ho_ten}, nộp ngày {ngay}.",
                 slots=[{"name": "ho_ten", "label": "Họ tên", "required": True},
                        {"name": "ngay", "label": "Ngày", "type": "date", "required": True}])
    # thiếu bắt buộc → lỗi, không điền
    text, errs = fill_template(session, "don_xin_phep", {"ho_ten": "Trần B"})
    assert errs and text == "Tôi {ho_ten}, nộp ngày {ngay}."
    # đủ + đúng kiểu → điền
    text, errs = fill_template(session, "don_xin_phep",
                               {"ho_ten": "Trần B", "ngay": "2022-03-01"})
    assert errs == [] and text == "Tôi Trần B, nộp ngày 2022-03-01."
    # không có mẫu
    _, errs = fill_template(session, "khong_co", {})
    assert errs
