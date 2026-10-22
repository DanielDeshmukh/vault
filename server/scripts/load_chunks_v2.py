"""Load the Phase 2 dry-run chunk records into ``document_chunks_v2``.

Source: ``corpus/v2_dryrun/records.jsonl`` -- Pinecone-shaped records with
empty ``values`` (no embeddings yet; Phase 5 does that) and the full chunk
payload in ``metadata``.

Idempotent: the table is created from the ORM metadata (single source of
truth, ``Base.metadata.create_all``) and rows are inserted with
``ON CONFLICT (chunk_id) DO NOTHING``, so re-runs insert 0 and never touch
existing rows. This writes chunk text only -- no vectors, no Pinecone.

    cd server && $env:PYTHONUTF8="1" && python -m scripts.load_chunks_v2

The ``app.*`` imports live inside ``main`` on purpose: ``app.config`` and
``app.db.sessions`` read ``DATABASE_URL`` at import time, so the environment
must be settled first.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

RECORDS_PATH = Path(__file__).resolve().parents[2] / "corpus" / "v2_dryrun" / "records.jsonl"
BATCH_SIZE = 2000

COLUMNS = (
    "chunk_id",
    "doc_id",
    "chunk_index",
    "source_path",
    "source_type",
    "doc_title",
    "heading_path",
    "block_type",
    "text_md",
    "text_embed",
    "token_count",
    "char_count",
    "content_hash",
    "department",
    "classification",
    "allowed_roles",
    "chunk_version",
)


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


def _row(meta: dict) -> dict:
    return {key: meta.get(key) for key in COLUMNS}


async def main() -> int:
    _load_env()
    if not os.environ.get("DATABASE_URL"):
        # Local convention: server/.env carries NEON_DATABASE_URL instead.
        neon = os.environ.get("NEON_DATABASE_URL", "")
        if not neon:
            print("ERROR: Set DATABASE_URL (or NEON_DATABASE_URL in server/.env)")
            return 1
        os.environ["DATABASE_URL"] = neon

    # Import after the environment is settled: app.config reads it at import.
    from app.db.models import DocumentChunkV2
    from app.db.sessions import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    if not RECORDS_PATH.exists():
        print(f"ERROR: {RECORDS_PATH} not found -- run the Phase 2 dry run first")
        return 1

    started = time.monotonic()
    lines = 0
    with RECORDS_PATH.open(encoding="utf-8") as fh:
        for _ in fh:
            lines += 1

    async with session_factory() as session:
        before = (
            await session.execute(select(func.count()).select_from(DocumentChunkV2))
        ).scalar_one()

        conflict_free = insert(DocumentChunkV2).on_conflict_do_nothing(
            index_elements=["chunk_id"]
        )

        batch: list[dict] = []
        with RECORDS_PATH.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                meta = json.loads(line)["metadata"]
                batch.append(_row(meta))
                if len(batch) >= BATCH_SIZE:
                    await session.execute(conflict_free, batch)
                    batch = []
                    if lineno % 10000 == 0:
                        print(f"  {lineno}/{lines} rows processed...")
            if batch:
                await session.execute(conflict_free, batch)
        await session.commit()

        after = (
            await session.execute(select(func.count()).select_from(DocumentChunkV2))
        ).scalar_one()

    await engine.dispose()
    elapsed = time.monotonic() - started
    print(f"records.jsonl lines : {lines}")
    print(f"rows in table before: {before}")
    print(f"rows in table after : {after}")
    print(f"inserted            : {after - before}")
    print(f"already present     : {lines - (after - before)}")
    print(f"elapsed             : {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
