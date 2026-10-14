"""Remove dead weight from the Vault corpus.

Dry-run by default: prints exactly what would be removed and touches nothing.
Pass --apply to execute, which first writes a JSONL backup of every document
about to be deleted.

    python scripts/cleanup_corpus.py                 # report only
    python scripts/cleanup_corpus.py --apply         # back up + delete
    python scripts/cleanup_corpus.py --cats json     # add the JSON stubs

Ordering matters. Pinecone is cleared before Postgres: content always stays
in Postgres until its vectors are gone, so an interrupted run can only ever
leave a document that is listed but not yet searchable (re-upsertable from
its own stored text) rather than a vector pointing at a document that no
longer exists (which nothing could repair).
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete, func, select, text  # noqa: E402

from app.db.models import Document, DocumentAccess, DocumentChunk  # noqa: E402
from app.db.sessions import async_session  # noqa: E402

# Pages ingested as if they were content: index stubs, Hugo notices, redirects.
PLACEHOLDER = (
    r"placeholder page|This page has moved|[Nn]ot Live Yet|"
    r"work-in-progress and represents a very early state"
)
JSON_LIKE = r"^\s*[\{\[]"
OFF_THEME = "https%"

CATS = ("dupes", "placeholders", "thin", "offtheme", "json")
DEFAULT_CATS = ("dupes", "placeholders", "thin", "offtheme")

SCAN = """
select
  id, title, source, coalesce(source_file,'') source_file,
  coalesce(department,'') department, coalesce(classification,'') classification,
  length(content) len, md5(content) hash,
  (content ~ :placeholder) placeholder,
  (content ~ :jsonlike) jsonlike,
  (source like :offtheme) offtheme
from documents
"""

PINECONE_BATCH = 100


def table(headers, rows, title=None):
    if title:
        print(f"\n  {title}")
    print("    " + " | ".join(headers))
    print("    " + "-+-".join("-" * len(h) for h in headers))
    for r in rows:
        print("    " + " | ".join("" if c is None else str(c) for c in r))


def select_canonical(members):
    """Among identical documents keep the shallowest source path -- the index
    page a reader would actually land on -- falling back to the lowest id."""
    return sorted(members, key=lambda m: (len(m["source_file"]), str(m["id"])))[0]


async def plan(cats):
    async with async_session() as db:
        rows = (
            await db.execute(
                text(SCAN).params(placeholder=PLACEHOLDER, jsonlike=JSON_LIKE, offtheme=OFF_THEME)
            )
        ).mappings().all()

    by_cat = defaultdict(set)  # category -> {doc id}
    for r in rows:
        did = str(r["id"])
        if "placeholders" in cats and r["placeholder"] and r["len"] < 1000:
            by_cat["placeholders"].add(did)
        if "thin" in cats and r["len"] < 200:
            by_cat["thin"].add(did)
        if "offtheme" in cats and r["offtheme"]:
            by_cat["offtheme"].add(did)
        if "json" in cats and r["jsonlike"]:
            by_cat["json"].add(did)

    non_dupe = set().union(*by_cat.values()) if by_cat else set()

    # Exact-content duplicates. Anything already doomed by another category
    # is not worth preserving as the canonical copy, so only surviving
    # members compete for that role.
    groups = defaultdict(list)
    for r in rows:
        if r["len"] > 0:
            groups[r["hash"]].append(r)

    dupe_losers, kept = [], 0
    for members in groups.values():
        if len(members) < 2:
            continue
        alive = [m for m in members if str(m["id"]) not in non_dupe]
        if not alive:
            continue  # every copy is being removed anyway
        keeper = select_canonical(alive)
        kept += 1
        for m in members:
            if str(m["id"]) != str(keeper["id"]):
                dupe_losers.append(str(m["id"]))
    if "dupes" in cats:
        by_cat["dupes"] = set(dupe_losers)

    removal = set().union(*by_cat.values()) if by_cat else set()
    return rows, by_cat, removal


async def chunk_stats(ids):
    if not ids:
        return 0, 0
    async with async_session() as db:
        n = (
            await db.execute(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id.in_([i for i in ids]))
            )
        ).scalar_one()
    return n


async def apply(removal, backup_path):
    from app.db.pinecone import pinecone_client

    async with async_session() as db:
        ids = [i for i in removal]
        pc_ids = (
            await db.execute(
                select(DocumentChunk.pinecone_id).where(
                    DocumentChunk.document_id.in_(ids),
                    DocumentChunk.pinecone_id.isnot(None),
                )
            )
        ).scalars().all()

        # 1. Backup everything first -- nothing is destroyed unrecoverably.
        docs = (
            await db.execute(
                select(
                    Document.id,
                    Document.title,
                    Document.source,
                    Document.source_file,
                    Document.department,
                    Document.classification,
                    Document.content,
                ).where(Document.id.in_(ids))
            )
        ).all()
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, "w", encoding="utf-8") as fh:
            for d in docs:
                fh.write(
                    json.dumps(
                        {
                            "id": str(d[0]),
                            "title": d[1],
                            "source": d[2],
                            "source_file": d[3],
                            "department": d[4],
                            "classification": d[5],
                            "content": d[6],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(f"  backup  : {backup_path}  ({len(docs):,} documents)")

        # 2. Vectors before rows -- see module docstring.
        pc_ids = [p for p in pc_ids if p]
        for i in range(0, len(pc_ids), PINECONE_BATCH):
            batch = pc_ids[i : i + PINECONE_BATCH]
            await pinecone_client.delete_vectors(batch)
            if (i // PINECONE_BATCH) % 20 == 0:
                done = min(i + len(batch), len(pc_ids))
                print(f"    vectors {done:,}/{len(pc_ids):,}", flush=True)
        print(f"  vectors : {len(pc_ids):,} deleted")

        # 3. Rows.
        await db.execute(delete(DocumentAccess).where(DocumentAccess.document_id.in_(ids)))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(ids)))
        res = await db.execute(delete(Document).where(Document.id.in_(ids)))
        await db.commit()
        print(f"  rows    : {res.rowcount:,} documents removed")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default is dry-run)")
    ap.add_argument("--cats", default=",".join(DEFAULT_CATS),
                    help=f"comma list from: {','.join(CATS)}")
    ap.add_argument("--backup", default=None, help="backup path (apply only)")
    args = ap.parse_args()

    cats = tuple(c.strip() for c in args.cats.split(",") if c.strip())
    unknown = [c for c in cats if c not in CATS]
    if unknown:
        ap.error(f"unknown category: {unknown}; valid: {CATS}")

    print("=" * 74)
    print("CORPUS CLEANUP  " + ("APPLY" if args.apply else "DRY-RUN (no changes)"))
    print(f"categories: {', '.join(cats)}")
    print("=" * 74)

    t0 = time.time()
    rows, by_cat, removal = await plan(cats)

    existing_chunks = None
    if removal:
        existing_chunks = await chunk_stats(removal)

    n_docs = len(rows)
    pct = len(removal) / n_docs * 100 if n_docs else 0

    table(
        ["category", "documents"],
        [[k, f"{len(v):,}"] for k, v in sorted(by_cat.items(), key=lambda x: -len(x[1]))],
        "Removals by category (a document can match several)",
    )
    table(
        ["summary", "value"],
        [
            ["documents before", f"{n_docs:,}"],
            ["documents to remove", f"{len(removal):,}  ({pct:.1f}%)"],
            ["chunks to remove", f"{existing_chunks:,}" if existing_chunks is not None else "-"],
            ["documents after", f"{n_docs - len(removal):,}"],
        ],
        "Plan",
    )

    if removal:
        sample = [r for r in rows if str(r["id"]) in removal][:8]
        table(
            ["chars", "title"],
            [[f"{r['len']:,}", r["title"][:64]] for r in sample],
            "Sample of what would go",
        )

    print(f"\n  scanned in {time.time() - t0:.1f}s")

    if not removal:
        print("\n  Nothing to remove.")
        return

    if not args.apply:
        print("\n  DRY-RUN: nothing was deleted. Re-run with --apply to execute.")
        return

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup or os.path.join(
        os.path.dirname(__file__), "..", "..", "backups", f"corpus-cleanup-{stamp}.jsonl"
    )
    print("\n  applying...")
    await apply(removal, os.path.abspath(backup))
    print("  done.")


if __name__ == "__main__":
    asyncio.run(main())
