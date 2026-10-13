"""Add the columns the shape-chunked corpus needs.

Idempotent: safe to run repeatedly. There is no migration tooling in this
repo (no alembic/), so DDL is applied directly via ALTER TABLE.

    python server/scripts/migrate_corpus_schema.py
"""

import asyncio
import os

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


async def main() -> int:
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
