"""FR-34 Template store (TES) — nạp + match mẫu đơn (theo loại / ngữ nghĩa)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2.models import Template


def add_template(session: Session, kind: str, title: str, body: str, *,
                 slots: list[str] | None = None, lang: str = "vi", embedder=None) -> Template:
    emb = embedder.embed([body])[0] if embedder is not None else None
    t = Template(kind=kind, title=title, body=body, slots=slots or [], lang=lang, embedding=emb)
    session.add(t)
    session.flush()
    return t


def match_templates(session: Session, *, kind: str | None = None, query: str | None = None,
                    embedder=None, top: int = 3, lang: str = "vi") -> list[Template]:
    """Theo loại (exact) → ưu tiên; else ngữ nghĩa (embedding) nếu có embedder+query."""
    if kind:
        return list(session.scalars(
            sa.select(Template).where(Template.kind == kind, Template.lang == lang).limit(top)))
    if query and embedder is not None:
        qv = embedder.embed([query])[0]
        return list(session.scalars(
            sa.select(Template).where(Template.lang == lang, Template.embedding.is_not(None))
            .order_by(Template.embedding.cosine_distance(qv)).limit(top)))
    return list(session.scalars(sa.select(Template).where(Template.lang == lang).limit(top)))


def fill_template(session: Session, kind: str, values: dict, *, lang: str = "vi"):
    """FR-38 — điền biểu mẫu `kind` DETERMINISTIC (validate slots + thế {name}), KHÔNG
    LLM. Trả (text, errors). Không có mẫu → (None, ['không có mẫu'])."""
    from .forms import fill_form
    tpls = match_templates(session, kind=kind, lang=lang)
    if not tpls:
        return None, ["không có mẫu cho loại: " + kind]
    t = tpls[0]
    return fill_form(t.body, t.slots, values)
