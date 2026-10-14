"""Add the columns the shape-chunked corpus needs.

Idempotent: safe to run repeatedly. There is no migration tooling in this
repo (no alembic/), so DDL is applied directly via ALTER TABLE.

    python server/scripts/migrate_corpus_schema.py
"""

import asyncio
import os
from pathlib import Path

import asyncpg

STATEMENTS = [
    # --- documents -------------------------------------------------------
    # Corpus-native identifier, e.g. doc_hr_0042. The legacy uuid primary
    # key stays as-is because document_chunks.document_id references it.
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_id varchar(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS classification varchar(32)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS allowed_roles json",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_file text",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_doc_id ON documents (doc_id)",
    "CREATE INDEX IF NOT EXISTS ix_documents_classification ON documents (classification)",
    # Full-text search over title + content. Title weighted A, body B, so
    # ts_rank prefers a document about the query over one that mentions it.
    # STORED generated column: Postgres backfills every existing row and keeps
    # it current, so scripts/ingest_corpus.py needs no change. The expression
    # must stay byte-identical to Document.search_vector in app/db/models.py,
    # or create_all on a fresh database would build a different column.
    (
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector "
        "GENERATED ALWAYS AS ("
        "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('english', coalesce(content, '')), 'B')"
        ") STORED"
    ),
    "CREATE INDEX IF NOT EXISTS ix_documents_search_vector ON documents USING gin (search_vector)",
    # --- document_chunks -------------------------------------------------
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS citation text",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_index integer",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_span_start integer",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_span_end integer",
    # Parent mapping for chunks split out of an oversized section.
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS part integer",
    "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_parts integer",
    "CREATE INDEX IF NOT EXISTS ix_document_chunks_pinecone_id ON document_chunks (pinecone_id)",
]


def _load_env() -> None:
    """Pull server/.env into the environment without adding a dependency."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


async def main() -> int:
    _load_env()
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: Set DATABASE_URL")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        for stmt in STATEMENTS:
            await conn.execute(stmt)
            print(f"  ok  {stmt}")
    finally:
        await conn.close()

    print(f"\nApplied {len(STATEMENTS)} statements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
