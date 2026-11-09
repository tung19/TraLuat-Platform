"""W2 canonical schema (SQLAlchemy 2.0) — slice-2 Postgres layer.

Bất biến bitemporal được ENFORCE ở DB (engineering-principles #2):
  EXCLUDE USING gist (unit_id =, lang =, daterange(valid_from, valid_to) &&)
  WHERE tx_to IS NULL    → không thể có 2 dòng in-force chồng nhau cho cùng đơn vị.
(cần extension btree_gist cho toán tử = trên cột scalar.)

Spec: docs/specs/w2-knowledge-graph.md §2 + spec-audit-fixes. Tối giản ở slice-2:
các bảng lõi cần để enforce + reconstruct; mở rộng (chunk/precedent/concept…) sau.
"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Authority(Base):
    __tablename__ = "authority"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    rank_level: Mapped[int | None]  # lex superior (authority_rank versioned ở legal-rule-base)


class Document(Base):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(primary_key=True)
    frbr_uri: Mapped[str] = mapped_column(unique=True)
    doc_number: Mapped[str | None]
    doc_type: Mapped[str]
    authority_id: Mapped[int | None] = mapped_column(sa.ForeignKey("authority.id"))
    date_issued: Mapped[dt.date | None]
    date_effective: Mapped[dt.date | None]
    status: Mapped[str | None]
    units: Mapped[list[Unit]] = relationship(back_populates="document")


class Unit(Base):
    __tablename__ = "unit"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(sa.ForeignKey("document.id"))
    parent_id: Mapped[int | None] = mapped_column(sa.ForeignKey("unit.id"))
    unit_type: Mapped[str]
    ordinal: Mapped[int]
    label: Mapped[str]
    eid: Mapped[str] = mapped_column(unique=True)  # ★ prefix theo doc (nd99__dieu_3)
    document: Mapped[Document] = relationship(back_populates="units")
    versions: Mapped[list[UnitVersion]] = relationship(back_populates="unit")


class UnitVersion(Base):
    __tablename__ = "unit_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(sa.ForeignKey("unit.id"), index=True)
    lang: Mapped[str] = mapped_column(default="vi")
    valid_from: Mapped[dt.date]
    valid_to: Mapped[dt.date | None]                 # None = mở (+∞); half-open [from, to)
    applies_from: Mapped[dt.date | None]             # ★ A-fix: hồi tố
    tx_from: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    tx_to: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))  # None = đang tin
    text: Mapped[str | None]                         # None = tombstone (bãi bỏ)
    status: Mapped[str] = mapped_column(default="con_hieu_luc")
    transitional: Mapped[bool] = mapped_column(default=False)
    source_relation_id: Mapped[str | None] = mapped_column(index=True)
    order_key: Mapped[int] = mapped_column(default=0)  # ★ G4-fix: fold same-date

    unit: Mapped[Unit] = relationship(back_populates="versions")

    __table_args__ = (
        # ★ Bất biến DB-enforced: 0/1 dòng in-force (tx_to NULL) mỗi (unit, lang) tại mọi ngày.
        ExcludeConstraint(
            ("unit_id", "="),
            ("lang", "="),
            (sa.text("daterange(valid_from, valid_to)"), "&&"),
            using="gist",
            where=sa.text("tx_to IS NULL"),
            name="uv_no_overlap",
        ),
    )


# DDL phụ thuộc: btree_gist phải có TRƯỚC khi tạo uv_no_overlap.
BTREE_GIST = sa.DDL("CREATE EXTENSION IF NOT EXISTS btree_gist")
sa.event.listen(Base.metadata, "before_create", BTREE_GIST.execute_if(dialect="postgresql"))
