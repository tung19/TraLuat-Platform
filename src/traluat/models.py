"""
⛔ SKETCH MINH HOẠ — SUPERSEDED. KHÔNG CODE/COPY. Thiếu review_status/applies_from/
constraint. Nguồn chân lý = docs/specs/w2-knowledge-graph.md §2. Viết lại từ SPEC.

Schema canonical L3 (rút gọn) — bitemporal, trung lập pháp hệ.

Hai trục thời gian:
- valid-time  (valid_from / valid_to): khoảng điều khoản CÓ HIỆU LỰC pháp lý.
- transaction-time (tx_from / tx_to): khoảng hệ thống TIN rằng điều đó đúng.

Bitemporal cho phép trả lời hai câu khác nhau:
  (a) "Văn bản tại ngày T"        -> lọc theo valid-time.
  (b) "Tại ngày ta BIẾT là K, hệ thống tin văn bản tại T là gì" -> lọc cả hai trục.
Trục (b) là thứ Indigo KHÔNG có (chỉ valid-time) — cần cho audit/phòng vệ pháp lý.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Mốc "vô cực" cho transaction-time (bản ghi còn hiệu lực hệ thống).
TX_INF = dt.datetime(9999, 12, 31, tzinfo=dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    """Văn bản (FRBR Work). Vd: một Nghị định."""
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    frbr_uri: Mapped[str] = mapped_column(String(255), unique=True)  # canonical ID
    doc_number: Mapped[str] = mapped_column(String(100))
    doc_type: Mapped[str] = mapped_column(String(50))  # luat/nghi_dinh/thong_tu...
    title_vi: Mapped[str] = mapped_column(String(500))
    date_issued: Mapped[dt.date] = mapped_column(Date)
    date_effective: Mapped[dt.date] = mapped_column(Date)

    units: Mapped[list["Unit"]] = relationship(back_populates="document")


class Unit(Base):
    """Đơn vị cấu trúc (Điều/Khoản/Điểm...), cây đệ quy. Bản thân Unit KHÔNG mang text —
    text nằm ở UnitVersion để version theo thời gian."""
    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))
    unit_type: Mapped[str] = mapped_column(String(20))  # dieu/khoan/diem
    ordinal: Mapped[int] = mapped_column(Integer)        # thứ tự để sắp xếp
    label: Mapped[str] = mapped_column(String(50))       # "Điều 3", "2", "a"
    eid: Mapped[str] = mapped_column(String(255), unique=True)  # ID ổn định kiểu Bluebell

    document: Mapped["Document"] = relationship(back_populates="units")
    versions: Mapped[list["UnitVersion"]] = relationship(back_populates="unit")


class UnitVersion(Base):
    """Phiên bản văn bản của một Unit — BITEMPORAL. text=None => tombstone (bị bãi bỏ)."""
    __tablename__ = "unit_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"))
    lang: Mapped[str] = mapped_column(String(5), default="vi")

    valid_from: Mapped[dt.date] = mapped_column(Date)                 # hiệu lực từ
    valid_to: Mapped[Optional[dt.date]] = mapped_column(Date)         # None = còn hiệu lực
    tx_from: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    tx_to: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=TX_INF)

    text: Mapped[Optional[str]] = mapped_column(Text)                 # None = tombstone
    status: Mapped[str] = mapped_column(String(20), default="in_force")  # in_force/repealed
    source_note: Mapped[Optional[str]] = mapped_column(String(255))   # sửa đổi nào tạo ra

    unit: Mapped["Unit"] = relationship(back_populates="versions")


class NormRelation(Base):
    """Đồ thị quan hệ quy phạm. amends/repeals/replaces/cites/guides/conflicts."""
    __tablename__ = "norm_relation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    src_unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"))   # văn bản sửa đổi
    dst_unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"))   # bị sửa đổi
    relation_type: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    confidence: Mapped[float] = mapped_column(default=1.0)
