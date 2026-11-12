"""Reference-data-plane adapter (L1) — nơi đội data ĐẨY văn bản vào hệ.

Đội data lo Lakehouse + chuẩn hoá; hệ nhận qua `DocumentSource` theo schema cố định
(RawDocument). Cắm nguồn thật = implement `DocumentSource.fetch()` gọi API/CDC của họ,
KHÔNG đụng W1/W2. Stub: InMemorySource + JsonlFileSource để chạy & test ngay.

`ingest_source` lặp RawDocument → `ingest_document` (metadata+structure→W2) → gom kết
quả; văn bản thiếu metadata bắt buộc → ghi vào `failed` (không chặn cả mẻ).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .ingest import ingest_document


@dataclass
class RawDocument:
    doc_slug: str                 # prefix eId ổn định (vd 'nd99')
    text: str = ""                # nguyên văn (đã OCR/chuẩn hoá phía data)
    frbr_uri: str | None = None   # override metadata nếu đội data đã chuẩn hoá
    doc_type: str | None = None
    date_effective: dt.date | None = None
    doc_number: str | None = None
    lang: str = "vi"
    image_ref: bytes | None = None  # ảnh thô → OCR khi text rỗng


@runtime_checkable
class DocumentSource(Protocol):
    def fetch(self, since: dt.date | None = None) -> Iterable[RawDocument]: ...


class InMemorySource:
    """Stub: danh sách RawDocument (test / seed thủ công)."""

    def __init__(self, docs: list[RawDocument]) -> None:
        self._docs = docs

    def fetch(self, since: dt.date | None = None) -> Iterable[RawDocument]:
        return list(self._docs)


class JsonlFileSource:
    """Stub: mỗi dòng JSONL = 1 văn bản {doc_slug, text, frbr_uri?, ...}."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def fetch(self, since: dt.date | None = None) -> Iterator[RawDocument]:
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                de = d.get("date_effective")
                yield RawDocument(
                    doc_slug=d["doc_slug"], text=d["text"],
                    frbr_uri=d.get("frbr_uri"), doc_type=d.get("doc_type"),
                    date_effective=dt.date.fromisoformat(de) if de else None,
                    doc_number=d.get("doc_number"), lang=d.get("lang", "vi"),
                )


@dataclass
class IngestOutcome:
    loaded: list[str] = field(default_factory=list)              # frbr_uri đã nạp
    failed: list[tuple[str, str]] = field(default_factory=list)  # (doc_slug, lý do)
    unresolved: list[dict] = field(default_factory=list)
    indexed_chunks: int = 0


def ingest_source(
    session, source: DocumentSource, *, since: dt.date | None = None, ocr=None,
    anonymize_judgments: bool = True, index: bool = False, embedder=None,
    relations: bool = False,
) -> IngestOutcome:
    """Nạp cả mẻ từ nguồn → W2. Lỗi 1 văn bản không chặn mẻ (ghi vào failed).

    ocr = OCREngine (w1.ocr): văn bản chỉ có `image_ref` (text rỗng) → OCR trước.
    Thiếu ocr mà rỗng text → văn bản đó vào `failed` (không nạp bừa).
    anonymize_judgments (CN-05/NQ 03/2017): doc-type bản-án/án-lệ → ẩn danh PII TRƯỚC
    khi lưu (tên→viết tắt, CMND/CCCD/SĐT/email che). KB QPPL (Luật/NĐ) không áp."""
    from .anonymize import anonymize, is_judgment_type
    out = IngestOutcome()
    loaded_sources = []
    for raw in source.fetch(since):
        try:
            text = raw.text
            if not text and raw.image_ref is not None:
                if ocr is None:
                    raise ValueError("văn bản chỉ có ảnh nhưng chưa cấu hình OCR")
                text = ocr.extract(raw.image_ref, raw.lang)
            if anonymize_judgments and is_judgment_type(raw.doc_type):
                text, _ = anonymize(text)              # CN-05: che PII bản án
            # A failed flush aborts a PostgreSQL transaction. A savepoint per
            # document preserves earlier successes and permits later documents.
            with session.begin_nested():
                doc, _ = ingest_document(
                    session, text, raw.doc_slug, frbr_uri=raw.frbr_uri,
                    doc_type=raw.doc_type, date_effective=raw.date_effective,
                    doc_number=raw.doc_number, lang=raw.lang,
                )
                count = 0
                if index:
                    from ..w3.indexer import reindex_document
                    count = reindex_document(session, doc.frbr_uri, lang=raw.lang, embedder=embedder)
            out.loaded.append(doc.frbr_uri)
            out.indexed_chunks += count
            loaded_sources.append((doc.frbr_uri, text, doc.date_effective))
        except Exception as e:  # noqa: BLE001 — cô lập lỗi từng văn bản
            out.failed.append((raw.doc_slug, str(e)))
    # Resolve after the whole batch: targets may occur after their referring source.
    if relations:
        from dataclasses import asdict

        from .ingest import extract_and_load_relations
        for uri, text, effective in loaded_sources:
            with session.begin_nested():
                _, unresolved = extract_and_load_relations(
                    session, src_frbr_uri=uri, text=text, default_effective_date=effective)
                out.unresolved.extend({"source": uri, **asdict(c)} for c in unresolved)
    return out
