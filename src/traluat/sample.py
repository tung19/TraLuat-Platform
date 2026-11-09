"""Dữ liệu MINH HOẠ (không phải văn bản pháp luật thật) để chứng minh moat #1.

Kịch bản:
- Nghị định 99/2020/NĐ-CP, Điều 3 gồm Khoản 1 và Khoản 2. Hiệu lực 2021-01-01.
- Nghị định 55/2023/NĐ-CP SỬA ĐỔI Khoản 2, hiệu lực 2023-07-01.
- Nghị định 80/2025/NĐ-CP BÃI BỎ Khoản 2, hiệu lực 2025-10-01.
Khoản 1 không đổi suốt.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base, Document, Unit, UnitVersion, TX_INF
from .temporal import apply_amendment, repeal

D = dt.date

K1_TEXT = "Doanh nghiệp phải nộp hồ sơ trong thời hạn 15 ngày làm việc."
K2_V1 = "Mức vốn pháp định tối thiểu là 20 tỷ đồng."
K2_V2 = "Mức vốn pháp định tối thiểu là 30 tỷ đồng."  # sửa 2023-07-01


def make_engine(url: str = "sqlite+pysqlite:///:memory:"):
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    return engine


def seed(session: Session) -> dict:
    """Nạp dữ liệu minh hoạ. Trả về id các thực thể để test tiện tham chiếu."""
    now = dt.datetime.now(tz=dt.timezone.utc)

    nd99 = Document(
        frbr_uri="trl:vn/nghi_dinh/99-2020-nd-cp",
        doc_number="99/2020/NĐ-CP", doc_type="nghi_dinh",
        title_vi="Nghị định 99/2020/NĐ-CP (minh hoạ)",
        date_issued=D(2020, 8, 20), date_effective=D(2021, 1, 1),
    )
    session.add(nd99)
    session.flush()

    dieu3 = Unit(document_id=nd99.id, parent_id=None, unit_type="dieu",
                 ordinal=3, label="Điều 3", eid="nd99__dieu_3")
    session.add(dieu3)
    session.flush()

    k1 = Unit(document_id=nd99.id, parent_id=dieu3.id, unit_type="khoan",
              ordinal=1, label="1", eid="nd99__dieu_3__khoan_1")
    k2 = Unit(document_id=nd99.id, parent_id=dieu3.id, unit_type="khoan",
              ordinal=2, label="2", eid="nd99__dieu_3__khoan_2")
    session.add_all([k1, k2])
    session.flush()

    # Phiên bản gốc, hiệu lực 2021-01-01
    session.add_all([
        UnitVersion(unit_id=k1.id, lang="vi", valid_from=D(2021, 1, 1), valid_to=None,
                    tx_from=now, tx_to=TX_INF, text=K1_TEXT, source_note="NĐ 99/2020"),
        UnitVersion(unit_id=k2.id, lang="vi", valid_from=D(2021, 1, 1), valid_to=None,
                    tx_from=now, tx_to=TX_INF, text=K2_V1, source_note="NĐ 99/2020"),
    ])
    session.flush()

    # Văn bản sửa đổi: NĐ 55/2023 sửa Khoản 2, hiệu lực 2023-07-01
    nd55 = Document(
        frbr_uri="trl:vn/nghi_dinh/55-2023-nd-cp",
        doc_number="55/2023/NĐ-CP", doc_type="nghi_dinh",
        title_vi="Nghị định 55/2023/NĐ-CP (minh hoạ, sửa đổi NĐ 99)",
        date_issued=D(2023, 5, 10), date_effective=D(2023, 7, 1),
    )
    session.add(nd55)
    session.flush()
    amend_v2 = apply_amendment(
        session, target_unit_id=k2.id, new_text=K2_V2,
        effective_date=D(2023, 7, 1), source_note="sửa bởi NĐ 55/2023",
    )

    # Văn bản bãi bỏ: NĐ 80/2025 bãi bỏ Khoản 2, hiệu lực 2025-10-01
    repeal(session, target_unit_id=k2.id, effective_date=D(2025, 10, 1),
           source_note="bãi bỏ bởi NĐ 80/2025")

    session.commit()
    return {
        "nd99_id": nd99.id, "dieu3_id": dieu3.id,
        "k1_id": k1.id, "k2_id": k2.id,
        "k2_v2_version_id": amend_v2.id,
    }
