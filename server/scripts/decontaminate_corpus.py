"""Strip authoring artefacts from stored documents, then re-chunk and re-embed.

``shape_chunker.cleaned_content`` only removed YAML frontmatter from markdown,
so every GitLab handbook page carried its Hugo shortcodes, HTML tags and HTML
comments into ``documents.content``, into each chunk, and into the embedding.
This repairs the live corpus in place:

    1. re-clean each affected document with the corrected cleaner
    2. re-chunk it with the same ShapeChunker, so section offsets stay valid
    3. re-embed the new chunk texts
    4. swap the rows and the vectors

Dry-run by default. ``--apply`` writes a JSONL backup first.

Nothing about access control is reconstructed. ``allowed_roles`` is the Pinecone
permission filter, so every vector's metadata is fetched back from the index
and only the text-bearing keys are rewritten -- a role list cannot be lost by
a mistake in this script.

Order of writes: embeddings are computed *before* the database is touched, and
Pinecone is upserted *before* surplus old ids are deleted, so a document is
never retrievable with no vector and never lost.

Usage:
    python server/scripts/decontaminate_corpus.py
    python server/scripts/decontaminate_corpus.py --apply
    python server/scripts/decontaminate_corpus.py --apply --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "server"))

from sqlalchemy import delete, func, select, text, update  # noqa: E402

from app.db.models import Document, DocumentChunk  # noqa: E402
from app.db.sessions import async_session  # noqa: E402

# Load the chunker by path: app.ingestion imports the pipeline, which imports
# the DB engine, and this tool must be readable offline.
_CHUNKER_PATH = REPO / "server" / "app" / "ingestion" / "shape_chunker.py"
_spec = importlib.util.spec_from_file_location("shape_chunker", _CHUNKER_PATH)
mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)

ShapeChunker = mod.ShapeChunker
cleaned_content = mod.cleaned_content
detect_kind = mod.detect_kind

CORPUS = REPO / "corpus"
MANIFEST = CORPUS / "manifest.jsonl"

PINECONE_BATCH = 100
FETCH_BATCH = 200

# Any of these in stored content means the cleaner has work to do.
DIRTY_SQL = (
    "content like '%{{%' or content like '%<!--%' "
    "or content ~* '<[^>]+>'"
)

# Deliberately no per-document chunk count here: a correlated subquery runs a
# scan of the 55k-row chunk table once per document (4,901 times), which is
# what stalled the first dry-run. Counts are fetched in one grouped query
# below, and only for documents that actually change.
SCAN_SQL = f"""
select d.id, d.doc_id, d.title, d.source, coalesce(d.source_file,'') source_file,
       d.department, d.classification, d.allowed_roles, d.content
from documents d
where {DIRTY_SQL}
"""


def table(title: str, headers: list[str], rows: list[list]) -> None:
    print(f"\n  {title}")
    print("    " + " | ".join(headers))
    print("    " + "-+-".join("-" * len(h) for h in headers))
    for r in rows:
        print("    " + " | ".join("" if c is None else str(c) for c in r))


def load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        print("  WARNING: corpus/manifest.jsonl missing; kind inferred from extension")
        return {}
    out: dict[str, dict] = {}
    with MANIFEST.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                entry = json.loads(line)
                out[entry["path"]] = entry
    return out


def kind_for(source_file: str, manifest: dict[str, dict]) -> str:
    entry = manifest.get(source_file)
    if entry:
        try:
            return detect_kind(entry)
        except ValueError:
            pass
    p = source_file.lower()
    if p.endswith((".htm", ".html")):
        return "sec_filing"
    if p.endswith(".md") or not p:
        return "markdown"
    return "markdown"


async def scan(manifest: dict[str, dict]) -> list[dict]:
    chunker = ShapeChunker()
    async with async_session() as db:
        print("  loading candidate documents...", flush=True)
        rows = (await db.execute(text(SCAN_SQL))).mappings().all()
        print(
            f"  {len(rows):,} carry markup; checking which actually change...",
            flush=True,
        )

        candidates = []
        for r in rows:
            kind = kind_for(r["source_file"], manifest)
            after = cleaned_content(r["content"], kind)
            if after != r["content"]:
                candidates.append((r, kind, after))

        # One grouped query for every affected document at once. Doing this
        # per document is what hung the first dry-run.
        counts: dict[str, int] = {}
        if candidates:
            ids = [r["id"] for r, _, _ in candidates]
            res = await db.execute(
                select(DocumentChunk.document_id, func.count())
                .where(DocumentChunk.document_id.in_(ids))
                .group_by(DocumentChunk.document_id)
            )
            counts = {str(k): int(v) for k, v in res.all()}

        print(f"  {len(candidates):,} change; re-chunking...", flush=True)
        out = []
        for r, kind, after in candidates:
            chunks, report = chunker.chunk(
                after,
                r["source_file"] or r["source"] or r["doc_id"],
                kind,
                source_title=r["title"],
            )
            row = dict(r)
            row["n_chunks"] = counts.get(str(r["id"]), 0)
            out.append(
                {
                    "row": row,
                    "kind": kind,
                    "new_content": after,
                    "chunks": chunks,
                    "warnings": list(report.warnings),
                }
            )
    return out


def pinecone_id(doc_id: str, index: int) -> str:
    return f"{doc_id}#chunk_{index:03d}"


# Hash in the database, not in Python: pulling 4,901 documents' worth of text
# across the wire just to compute a fingerprint took 3-8 minutes. This returns
# a 32-byte digest instead of the whole corpus.
DUP_SQL = """
select d.id, d.doc_id, d.title, coalesce(d.source_file,'') source_file,
       d.department,
       md5(trim(regexp_replace(lower(d.content), '\\s+', ' ', 'g'))) as fingerprint
from documents d
"""

# Lower rank wins when a duplicate group has to pick one survivor.
_EXT_RANK = {".txt": 0, ".md": 1, ".markdown": 1}


def _keep_rank(m: dict) -> tuple:
    name = m["source_file"].lower()
    return (_EXT_RANK.get(Path(name).suffix, 2), name)


async def find_drops() -> tuple[list[dict], dict]:
    """Documents to delete outright.

    Two reasons, both approved before this run:
      * exact duplicates -- identical content stored twice (``.txt`` and its
        ``.PDF`` twin); keep one, drop the rest;
      * documents with zero chunks -- nothing retrievable points at them.
    """
    async with async_session() as db:
        rows = [dict(r) for r in (await db.execute(text(DUP_SQL))).mappings()]
        res = await db.execute(
            select(DocumentChunk.document_id, func.count())
            .group_by(DocumentChunk.document_id)
        )
        counts = {str(k): int(v) for k, v in res.all()}

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r.pop("fingerprint")].append(r)

    drops: list[dict] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=_keep_rank)
        for m in members[1:]:
            m["n_chunks"] = counts.get(str(m["id"]), 0)
            m["drop_reason"] = f"duplicate of {members[0]['source_file']}"
            drops.append(m)

    seen = {d["id"] for d in drops}
    for r in rows:
        if r["id"] in seen or counts.get(str(r["id"]), 0):
            continue
        r["n_chunks"] = 0
        r["drop_reason"] = "zero chunks (nothing retrievable)"
        drops.append(r)

    stats = {
        "duplicate": sum(1 for d in drops if d["drop_reason"].startswith("duplicate")),
        "zero_chunk": sum(1 for d in drops if d["drop_reason"].startswith("zero")),
        "chunks": sum(d["n_chunks"] for d in drops),
    }

    # The backup keeps full text, but only for documents we are deleting --
    # 20 rows, not the whole corpus.
    if drops:
        async with async_session() as db:
            res = await db.execute(
                select(Document.id, Document.content).where(
                    Document.id.in_([d["id"] for d in drops])
                )
            )
            contents = {str(k): v for k, v in res.all()}
        for d in drops:
            d["content"] = contents.get(str(d["id"]), "")

    return drops, stats


async def fetch_old_chunks(plans: list[dict]) -> dict[str, dict[int, tuple[str, str]]]:
    """For each affected document: {chunk_index: (content, citation)}."""
    async with async_session() as db:
        ids = [p["row"]["id"] for p in plans]
        res = await db.execute(
            select(
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
                DocumentChunk.citation,
            ).where(DocumentChunk.document_id.in_(ids))
        )
        out: dict[str, dict[int, tuple[str, str]]] = defaultdict(dict)
        for did, idx, content, citation in res.all():
            out[str(did)][int(idx)] = (content, citation or "")
    return out


def reusable_chunks(
    plans: list[dict], old: dict[str, dict[int, tuple[str, str]]]
) -> set[tuple[str, int]]:
    """(document key, new chunk index) whose existing vector can be left alone.

    Text *and* citation must both match: those are the only two keys the API
    reads out of a chunk's Pinecone metadata (``doc_id``/``department``/
    ``source_title`` are document-level and ``allowed_roles`` is untouched), so
    if both are unchanged the stored vector is already correct and needs no
    fetch, no re-embed and no upsert. Section spans are refreshed in Postgres
    but not in the index -- nothing reads them from Pinecone.
    """
    keep: set[tuple[str, int]] = set()
    for p in plans:
        doc_key = str(p["row"]["id"])
        existing = old.get(doc_key, {})
        for j, ch in enumerate(p["chunks"]):
            prev = existing.get(j)
            if prev and prev[0] == ch.text and prev[1] == ch.citation:
                keep.add((doc_key, j))
    return keep


async def measure_reuse(plans: list[dict]) -> tuple[int, int]:
    """(new chunks, chunks that can keep their existing vector)."""
    old = await fetch_old_chunks(plans)
    return sum(len(p["chunks"]) for p in plans), len(reusable_chunks(plans, old))


async def fetch_metadata(ids: list[str]) -> dict[str, dict]:
    from app.db.pinecone import pinecone_client

    index = pinecone_client.index
    out: dict[str, dict] = {}
    for start in range(0, len(ids), FETCH_BATCH):
        batch = ids[start : start + FETCH_BATCH]
        got = getattr(index.fetch(ids=batch), "vectors", None) or {}
        for vid, vec in got.items():
            out[vid] = dict(getattr(vec, "metadata", None) or {})
        if (start // FETCH_BATCH) % 10 == 0:
            print(f"    metadata {min(start + len(batch), len(ids)):,}/{len(ids):,}", flush=True)
    return out


def embed_all(texts: list[str]) -> list[list[float]]:
    from app.embeddings import EMBED_DIM, NIM_BATCH, embed_texts

    batches = (len(texts) + NIM_BATCH - 1) // NIM_BATCH
    print(f"  embedding {len(texts):,} texts in {batches:,} batches of {NIM_BATCH}", flush=True)
    t0 = time.time()
    out: list[list[float]] = []
    for i in range(0, len(texts), NIM_BATCH):
        out.extend(embed_texts(texts[i : i + NIM_BATCH], dim=EMBED_DIM))
        done = min(i + NIM_BATCH, len(texts))
        elapsed = time.time() - t0
        rate = done / max(elapsed, 1e-9)
        eta = (len(texts) - done) / max(rate, 1e-9)
        print(f"    {done:,}/{len(texts):,}  {elapsed:5.1f}s  eta {eta:5.1f}s", flush=True)
    return out


async def apply(
    plans: list[dict], backup_path: str, drops: list[dict] | None = None
) -> None:
    from app.db.pinecone import pinecone_client

    drops = drops or []

    # ---- 1. everything that can fail, fails before any write ----------------
    old = await fetch_old_chunks(plans)
    keep = reusable_chunks(plans, old)

    all_old_ids: list[str] = []
    all_new_ids: list[str] = []
    # (doc key, chunk index, video id, ShapedChunk) for the chunks that need work
    todo: list[tuple[str, int, str, object]] = []
    n_new = 0

    for p in plans:
        row = p["row"]
        doc_key = str(row["id"])
        all_old_ids.extend(
            pinecone_id(row["doc_id"], i) for i in range(1, row["n_chunks"] + 1)
        )
        for j, ch in enumerate(p["chunks"]):
            vid = pinecone_id(row["doc_id"], j + 1)
            all_new_ids.append(vid)
            n_new += 1
            if (doc_key, j) not in keep:
                todo.append((doc_key, j, vid, ch))

    n_reuse = n_new - len(todo)
    print(f"\n  chunks: {n_new:,} total, {n_reuse:,} reused, {len(todo):,} to embed", flush=True)

    # Document-level metadata (doc_id, source_title, department,
    # allowed_roles, ...) is identical for every chunk of one document, so
    # fetching it once per chunk -- 11,686 ids -- is 8x the network traffic
    # for nothing. Fetch one chunk per document instead (1,580 ids) and share
    # the result. Chunk-level keys are written explicitly further down.
    sample_for_doc: dict[str, str] = {}
    for doc_key, _j, vid, _ch in todo:
        sample_for_doc.setdefault(doc_key, vid)
    print(
        f"  fetching document metadata for {len(sample_for_doc):,} documents",
        flush=True,
    )
    try:
        fetched = await fetch_metadata(list(sample_for_doc.values()))
    except Exception as exc:  # never let this block the embedding run
        print(f"  WARNING: metadata fetch failed ({exc}); using fallback", flush=True)
        fetched = {}
    meta_by_doc = {k: fetched.get(v) for k, v in sample_for_doc.items()}
    n_meta = sum(1 for v in meta_by_doc.values() if v)
    print(f"  metadata ready for {n_meta:,}/{len(meta_by_doc):,} documents", flush=True)

    vectors = embed_all([t[3].text for t in todo])
    print(f"  embedded {len(vectors):,} vectors", flush=True)

    # ---- 2. backup -----------------------------------------------------------
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    n_backup = 0
    with open(backup_path, "w", encoding="utf-8") as fh:
        for p in plans:
            row = p["row"]
            fh.write(
                json.dumps(
                    {
                        "id": str(row["id"]),
                        "doc_id": row["doc_id"],
                        "title": row["title"],
                        "source_file": row["source_file"],
                        "kind": p["kind"],
                        "content": row["content"],
                        "n_chunks": row["n_chunks"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            n_backup += 1
        for d in drops:
            fh.write(
                json.dumps(
                    {
                        "id": str(d["id"]),
                        "doc_id": d["doc_id"],
                        "title": d["title"],
                        "source_file": d["source_file"],
                        "kind": "dropped",
                        "drop_reason": d["drop_reason"],
                        "content": d["content"],
                        "n_chunks": d.get("n_chunks", 0),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            n_backup += 1
    print(f"  backup: {backup_path}  ({n_backup:,} records)", flush=True)

    # ---- 3. postgres ---------------------------------------------------------
    async with async_session() as db:
        for p in plans:
            row = p["row"]
            await db.execute(
                update(Document)
                .where(Document.id == row["id"])
                .values(content=p["new_content"])
            )
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == row["id"])
            )
            for i, ch in enumerate(p["chunks"]):
                db.add(
                    DocumentChunk(
                        document_id=row["id"],
                        content=ch.text,
                        chunk_index=i,
                        pinecone_id=pinecone_id(row["doc_id"], i + 1),
                        citation=ch.citation,
                        section_index=ch.section_index,
                        section_span_start=ch.section_char_start,
                        section_span_end=ch.section_char_end,
                        part=ch.part,
                        section_parts=ch.parts,
                    )
                )
        if drops:
            drop_ids = [d["id"] for d in drops]
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id.in_(drop_ids))
            )
            await db.execute(delete(Document).where(Document.id.in_(drop_ids)))
        await db.commit()
    print(
        f"  postgres: {len(plans):,} documents + {n_new:,} chunks written"
        f" ({n_reuse:,} of them unchanged in the index)"
        + (f"; {len(drops):,} documents deleted" if drops else ""),
        flush=True,
    )

    # ---- 4. pinecone: upsert only the chunks that needed a new vector --------
    # Reused chunks keep the vector they already have -- same text, same
    # citation, so the stored entry is already correct. Their ids stay in
    # all_new_ids, which is why they are not treated as surplus below.
    index = pinecone_client.index
    row_by_key = {str(p["row"]["id"]): p["row"] for p in plans}

    def _doc_meta(doc_key: str) -> dict:
        """Document-level metadata for one chunk.

        Prefers what Pinecone already stores; falls back to the same fields
        taken from the document row, so a failed fetch can never strip
        ``allowed_roles``/``department`` off a vector (that would silently
        break ACL filtering).
        """
        got = meta_by_doc.get(doc_key)
        if got:
            return dict(got)
        r = row_by_key.get(doc_key, {})
        return {
            "doc_id": r.get("doc_id", ""),
            "source_title": r.get("title") or r.get("source_file", ""),
            "department": r.get("department", ""),
            "classification": r.get("classification", ""),
            "allowed_roles": r.get("allowed_roles") or [],
            "source_file": r.get("source_file", ""),
        }

    records: list[tuple[str, list[float], str, object]] = [
        (vid, vec, doc_key, ch)
        for vec, (doc_key, _j, vid, ch) in zip(vectors, todo)
    ]

    for start in range(0, len(records), PINECONE_BATCH):
        batch = records[start : start + PINECONE_BATCH]
        vecs = []
        for vid, vec, doc_key, ch in batch:
            md = _doc_meta(doc_key)
            md.update(
                {
                    "text": ch.text,
                    "citation": ch.citation,
                    "section_title": ch.section_title or "",
                    "section_index": ch.section_index,
                    "section_parts": ch.parts,
                    "part": ch.part,
                    "section_span_start": ch.section_char_start,
                    "section_span_end": ch.section_char_end,
                }
            )
            vecs.append({"id": vid, "values": vec, "metadata": md})
        index.upsert(vectors=vecs)
        if (start // PINECONE_BATCH) % 20 == 0:
            done = min(start + len(batch), len(records))
            print(f"    upsert {done:,}/{len(records):,}", flush=True)
    print(f"  pinecone: {len(records):,} vectors upserted", flush=True)

    surplus = sorted(set(all_old_ids) - set(all_new_ids))
    for start in range(0, len(surplus), PINECONE_BATCH):
        index.delete(ids=surplus[start : start + PINECONE_BATCH])
    print(f"  pinecone: {len(surplus):,} surplus ids deleted", flush=True)

    drop_ids = [
        pinecone_id(d["doc_id"], i)
        for d in drops
        for i in range(1, d.get("n_chunks", 0) + 1)
    ]
    for start in range(0, len(drop_ids), PINECONE_BATCH):
        index.delete(ids=drop_ids[start : start + PINECONE_BATCH])
    print(f"  pinecone: {len(drop_ids):,} vectors deleted for dropped docs", flush=True)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="only first N affected docs")
    ap.add_argument("--backup", default=None)
    args = ap.parse_args()

    print("=" * 74)
    print("CORPUS DECONTAMINATION  " + ("APPLY" if args.apply else "DRY-RUN (no changes)"))
    print("=" * 74)

    t0 = time.time()
    manifest = load_manifest()
    plans = await scan(manifest)

    print("  looking for exact duplicates and empty documents...", flush=True)
    drops, drop_stats = await find_drops()
    drop_ids = {d["id"] for d in drops}
    if drop_ids:
        before = len(plans)
        plans = [p for p in plans if p["row"]["id"] not in drop_ids]
        if before != len(plans):
            print(
                f"  {before - len(plans):,} cleaned doc(s) are also being dropped "
                f"-- removed from the cleaning list",
                flush=True,
            )
    if args.limit:
        plans = plans[: args.limit]

    # A document whose body is nothing but authoring notes (comments, disabled
    # shortcodes) cleans down to zero chunks. It would be invisible to search
    # but still counted as a document -- delete it instead.
    empty = [p for p in plans if not p["chunks"]]
    if empty:
        for p in empty:
            row = p["row"]
            row["n_chunks"] = row.get("n_chunks", 0)
            row["drop_reason"] = "cleaning leaves no retrievable content"
            drops.append(row)
        plans = [p for p in plans if p["chunks"]]
        print(
            f"  {len(empty):,} document(s) become empty after cleaning -- "
            f"moved to the delete list",
            flush=True,
        )

    by_kind = Counter(p["kind"] for p in plans)
    old_chunks = sum(p["row"]["n_chunks"] for p in plans)
    new_chunks = sum(len(p["chunks"]) for p in plans)
    chars_before = sum(len(p["row"]["content"]) for p in plans)
    chars_after = sum(len(p["new_content"]) for p in plans)
    warn_docs = sum(1 for p in plans if p["warnings"])

    # Purely a dry-run forecast: it fetches metadata for every candidate vector
    # from Pinecone, which can take minutes. --apply recomputes reuse itself,
    # inside apply(), so it is skipped here rather than blocking the real run.
    if not args.apply:
        print(
            "  measuring how many chunks can reuse their existing vector...",
            flush=True,
        )
        _, reusable = await measure_reuse(plans)
        to_embed = new_chunks - reusable
        est_min = to_embed * 0.22 / 60  # observed rate from the original ingest

    table(
        "Affected documents by kind",
        ["kind", "documents"],
        [[k, f"{v:,}"] for k, v in by_kind.most_common()],
    )
    table(
        "Plan",
        ["metric", "before", "after"],
        [
            ["documents cleaned", f"{len(plans):,}", f"{len(plans):,}"],
            ["chunks rewritten", f"{old_chunks:,}", f"{new_chunks:,}"],
            ["content chars", f"{chars_before:,}", f"{chars_after:,}"],
            ["chars removed", "", f"{chars_before - chars_after:,}"],
        ],
    )
    if drops:
        async with async_session() as db:
            n_docs_total = (
                await db.execute(select(func.count()).select_from(Document))
            ).scalar()
        by_reason = Counter(
            d["drop_reason"].split(" (")[0].split(" of ")[0] for d in drops
        )
        table(
            "Documents deleted outright",
            ["reason", "documents", "chunks removed"],
            [
                [reason, f"{n:,}", ""]
                for reason, n in by_reason.most_common()
            ]
            + [
                ["total", f"{len(drops):,}", f"{sum(d['n_chunks'] for d in drops):,}"],
                [
                    "corpus documents",
                    f"{n_docs_total:,}",
                    f"{n_docs_total - len(drops):,}",
                ],
            ],
        )
    if warn_docs:
        print(f"\n  {warn_docs} documents produced chunker warnings")

    print(f"\n  scanned in {time.time() - t0:.1f}s")
    if not plans and not drops:
        print("\n  Nothing to do.")
        return
    if not plans and not args.apply:
        print("\n  No cleaning needed; only deletions would run.")
        return
    if not args.apply:
        table(
            "Embedding cost on --apply",
            ["item", "count"],
            [
                ["new chunks", f"{new_chunks:,}"],
                ["reuse existing vector", f"{reusable:,}"],
                ["must be embedded", f"{to_embed:,}"],
                ["estimated time", f"~{est_min:.0f} min"],
            ],
        )
        print("\n  DRY-RUN: nothing was written. Re-run with --apply to execute.")
        return

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup or str(REPO / "backups" / f"decontaminate-{stamp}.jsonl")
    await apply(plans, os.path.abspath(backup), drops)
    print("\n  done.")


if __name__ == "__main__":
    asyncio.run(main())
