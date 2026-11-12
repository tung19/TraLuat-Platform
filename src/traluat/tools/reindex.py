"""Rebuild the public search index after ingestion or reviewed law changes.

Usage: DATABASE_URL=<KB writer URL> python -m traluat.tools.reindex --all
No ingestion, synthetic seeds or schema migrations are performed here.
"""
from __future__ import annotations

import argparse
import os

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..w2.db import make_engine
from ..w2.models import Document
from ..w3.indexer import reindex_document
from ..w5.ai_runtime import load_embedder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true")
    scope.add_argument("--frbr", action="append")
    parser.add_argument("--lang", default="vi", choices=["vi", "en"])
    parser.add_argument("--lexical-only", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL must explicitly identify a KB writer connection")
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            uris = args.frbr or list(session.scalars(sa.select(Document.frbr_uri).order_by(Document.id)))
        if not uris:
            print("No documents to index. Load reviewed data first.")
            return
        embedder = None if args.lexical_only else load_embedder()
        count = 0
        for uri in uris:
            with Session(engine) as session, session.begin():
                count += reindex_document(session, uri, embedder=embedder, lang=args.lang)
        print(f"Indexed {count} chunks from {len(uris)} documents ({args.lang}).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
