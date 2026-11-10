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
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ExcludeConstraint, TSVECTOR
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
    source_hash: Mapped[str | None] = mapped_column(index=True)  # D6: sha256 văn bản gốc (idempotent)
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


class NormRelation(Base):
    """Quan hệ quy phạm (amends/repeals/…) — G3-fix: endpoint cấp DOCUMENT hoặc UNIT."""

    __tablename__ = "norm_relation"
    id: Mapped[int] = mapped_column(primary_key=True)
    relation_type: Mapped[str]  # cites|amends|repeals|replaces|guides|conflicts|hierarchy
    effective_date: Mapped[dt.date | None]
    src_doc_id: Mapped[int] = mapped_column(sa.ForeignKey("document.id"))
    src_unit_id: Mapped[int | None] = mapped_column(sa.ForeignKey("unit.id"))
    dst_doc_id: Mapped[int] = mapped_column(sa.ForeignKey("document.id"))
    dst_unit_id: Mapped[int | None] = mapped_column(sa.ForeignKey("unit.id"))
    order_key: Mapped[int] = mapped_column(default=0)           # ★ G4
    confidence: Mapped[float | None]
    confidence_basis: Mapped[str | None]                        # ★ C2: không bịa confidence
    review_status: Mapped[str] = mapped_column(default="needs_review")  # ★ C1 gate
    evidence_span: Mapped[str | None]

    __table_args__ = (
        # ★ C3-fix: dedupe — replay/CDC không nhân đôi edge
        sa.UniqueConstraint(
            "src_doc_id", "src_unit_id", "dst_doc_id", "dst_unit_id",
            "relation_type", "effective_date", name="nr_dedupe",
        ),
    )


class Chunk(Base):
    """L4 — index phái sinh (rebuild được từ L3), PERSISTED. Không phải nguồn sự thật.

    span_text = nguyên văn neo (== citable_text@as_of); embedding = bge-m3 (null tới
    khi reindex có model). valid_from/to denormalized từ L3 để PUSH-DOWN as_of trong
    SQL. namespace = 'kb' (luật công) | 'tenant:<id>' (dữ liệu khách) → cô lập + filter.
    tsv = FTS 'simple' (BM25-ish qua ts_rank). source_version → idempotent upsert + cache.
    """

    __tablename__ = "chunk"
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(sa.ForeignKey("unit.id"), index=True)
    eid: Mapped[str] = mapped_column(index=True)
    lang: Mapped[str] = mapped_column(default="vi")
    namespace: Mapped[str] = mapped_column(default="kb")
    struct_header: Mapped[str]
    span_text: Mapped[str]
    char_from: Mapped[int] = mapped_column(default=0)
    char_to: Mapped[int] = mapped_column(default=0)
    valid_from: Mapped[dt.date]
    valid_to: Mapped[dt.date | None]
    source_version: Mapped[str] = mapped_column(default="v1")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, sa.Computed("to_tsvector('simple', span_text)", persisted=True))

    __table_args__ = (
        sa.UniqueConstraint("eid", "lang", "source_version", "namespace", name="uq_chunk_ver"),
        sa.Index("ix_chunk_scope", "namespace", "valid_from", "valid_to"),
        sa.Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        sa.Index("ix_chunk_hnsw", "embedding", postgresql_using="hnsw",
                 postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


# DDL phụ thuộc: extension phải có TRƯỚC khi tạo index/constraint dùng chúng.
for _ext in ("btree_gist", "vector", "pg_trgm"):
    sa.event.listen(
        Base.metadata, "before_create",
        sa.DDL(f"CREATE EXTENSION IF NOT EXISTS {_ext}").execute_if(dialect="postgresql"))
