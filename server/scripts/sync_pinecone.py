"""Finish the Pinecone side of the phase-2 decontamination after an interrupted run.

Postgres already reached its final state (4,879 documents / 54,530 chunks), but
the interrupted run died during the index upsert at 6,100/11,686, so the index
is out of sync: part of the cleaned text is missing and ids that Postgres no
longer has were never deleted.

Rather than reading the whole index back (Pinecone fetch costs ~200 ms per id,
which is 95 minutes for 27k ids), the plan is derived from two local sources:

    * ``corpus/chunks.jsonl`` -- the exact payloads the index was built from,
      so the pre-cleaning text of every chunk is known offline;
    * the decontaminate backup -- the pre-cleaning document text and the old
      per-document chunk counts.

Steps:

    1. rebuild each cleaned document's chunks from its stored content
       (cleaning is idempotent, so this reproduces exactly what was written)
    2. verify the rebuilt chunks equal the stored rows -- abort on any mismatch
    3. diff new chunk text against the original chunk text to split the corpus
       into "vector already correct" and "needs a new vector"
    4. everything at or after ``--resume-from`` in that list is re-embedded and
       upserted (upsert is idempotent by id, so rewriting finished work is
       harmless); a sample read back from the index confirms the cut point
    5. delete ids Postgres no longer has (surplus from re-chunking, plus the
       dropped documents)
    6. check the index count against Postgres and sample both sides

Dry-run by default. ``--apply`` writes.

Usage:
    python server/scripts/sync_pinecone.py
    python server/scripts/sync_pinecone.py --apply
    python server/scripts/sync_pinecone.py --apply --resume-from 0
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "server"))

from sqlalchemy import select  # noqa: E402

from app.db.models import Document, DocumentChunk  # noqa: E402
from app.db.sessions import async_session  # noqa: E402

# Load the chunker by path so this tool stays readable offline (see the note in
# decontaminate_corpus.py).
_CHUNKER_PATH = REPO / "server" / "app" / "ingestion" / "shape_chunker.py"
_spec = importlib.util.spec_from_file_location("shape_chunker", _CHUNKER_PATH)
mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)

ShapeChunker = mod.ShapeChunker
cleaned_content = mod.cleaned_content
detect_kind = mod.detect_kind

BACKUPS = REPO / "backups"
MANIFEST = REPO / "corpus" / "manifest.jsonl"
CHUNKS_CACHE = REPO / "corpus" / "chunks.jsonl"

PINECONE_BATCH = 100
FETCH_BATCH = 200

# Pinecone metadata carries only the first META_TEXT_CHARS of a chunk -- the
# contract ingest_corpus.py documents (its META_TEXT_CHARS = 4000, and the
# original index was written that way). Every writer has to cap identically,
# otherwise a read-back comparison of chunks longer than the cap reports a
# mismatch against vectors that are in fact correct.
META_TEXT_CHARS = 4000

# Last batch the interrupted run confirmed before it died (its progress lines
# print after the upsert: 100, 2,100, 4,100, 6,100).
DEFAULT_RESUME_FROM = 6100

# Read-back samples: small enough to cost ~2 minutes at ~200 ms per id.
SAMPLE_CHECK = 400
SAMPLE_FINAL = 300


def pinecone_id(doc_id: str, index: int) -> str:
    return f"{doc_id}#chunk_{index:03d}"


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
    return "markdown"


def latest_backup() -> Path:
    found = sorted(BACKUPS.glob("decontaminate-*.jsonl"))
    if not found:
        raise SystemExit(f"no decontaminate backup found in {BACKUPS}")
    return found[-1]


def table(title: str, headers: list[str], rows: list[list]) -> None:
    print(f"\n  {title}")
    print("    " + " | ".join(headers))
    print("    " + "-+-".join("-" * len(h) for h in headers))
    for r in rows:
        print("    " + " | ".join("" if c is None else str(c) for c in r))


def load_original_chunks(doc_ids: set[str]) -> dict[str, dict[int, tuple[str, str]]]:
    """{doc_id: {0-based index: (text, citation)}} exactly as the index was built."""
    if not CHUNKS_CACHE.exists():
        raise SystemExit(f"ABORT: {CHUNKS_CACHE} missing -- cannot tell old from new text")
    out: dict[str, dict[int, tuple[str, str]]] = defaultdict(dict)
    with CHUNKS_CACHE.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            md = rec.get("metadata") or {}
            doc_id = md.get("doc_id")
            if doc_id not in doc_ids:
                continue
            tail = str(rec.get("id", "")).rsplit("#chunk_", 1)
            if len(tail) != 2:
                continue
            try:
                idx = int(tail[1]) - 1
            except ValueError:
                continue
            out[doc_id][idx] = (md.get("text") or "", md.get("citation") or "")
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


async def build_targets(plans: list[dict], manifest: dict[str, dict]):
    """Rebuild every cleaned document's chunks and check them against Postgres."""
    chunker = ShapeChunker()
    ids = [r["id"] for r in plans]

    async with async_session() as db:
        docs = (await db.execute(select(Document).where(Document.id.in_(ids)))).scalars().all()
        rows_by_id = {str(d.id): d for d in docs}
        res = await db.execute(
            select(
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
                DocumentChunk.citation,
            ).where(DocumentChunk.document_id.in_(ids))
        )
        stored: dict[str, dict[int, tuple[str, str]]] = defaultdict(dict)
        for did, idx, content, citation in res.all():
            stored[str(did)][int(idx)] = (content, citation or "")

    missing = [i for i in ids if i not in rows_by_id]
    if missing:
        raise SystemExit(
            f"ABORT: {len(missing)} backup document ids are not in Postgres (first: {missing[0]})"
        )

    # (doc_key, pinecone id, chunk, document row) in backup order -- the same
    # order the interrupted run upserted in, so its progress line is a usable
    # resume point.
    targets: list[tuple[str, str, object, Document]] = []
    bad: list[str] = []
    n_old = 0

    for rec in plans:
        did = rec["id"]
        row = rows_by_id[did]
        source_file = row.source_file or ""
        kind = kind_for(source_file, manifest)
        after = cleaned_content(row.content, kind)
        chunks, _report = chunker.chunk(
            after,
            source_file or row.source or row.doc_id,
            kind,
            source_title=row.title,
        )
        prev = stored.get(did, {})
        n_old += rec.get("n_chunks", 0)
        if len(chunks) != len(prev):
            bad.append(f"{did}: rebuilt {len(chunks)} chunks, stored {len(prev)}")
            continue
        for i, ch in enumerate(chunks):
            got = prev.get(i)
            if got is None or got[0] != ch.text or got[1] != (ch.citation or ""):
                bad.append(f"{did}: chunk {i} text/citation differs from Postgres")
                break
            targets.append((str(row.doc_id), pinecone_id(row.doc_id, i + 1), ch, row))

    if bad:
        print("\n  ABORT: rebuilt chunks do not match the stored rows")
        for line in bad[:10]:
            print(f"    {line}")
        raise SystemExit(1)

    return targets, n_old


async def fetch_metadata(ids: list[str]) -> dict[str, dict]:
    from app.db.pinecone import pinecone_client

    index = pinecone_client.index
    out: dict[str, dict] = {}
    for start in range(0, len(ids), FETCH_BATCH):
        batch = ids[start : start + FETCH_BATCH]
        got = getattr(index.fetch(ids=batch), "vectors", None) or {}
        for vid, vec in got.items():
            out[vid] = dict(getattr(vec, "metadata", None) or {})
        print(f"    read {min(start + len(batch), len(ids)):,}/{len(ids):,}", flush=True)
    return out


def spread(ids: list[str], limit: int) -> list[str]:
    """Evenly spaced sample of at most `limit` ids, preserving order."""
    if limit <= 0 or len(ids) <= limit:
        return list(ids)
    step = len(ids) / limit
    return [ids[int(i * step)] for i in range(limit)]


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually write (default is dry-run)")
    ap.add_argument("--backup", default=None, help="decontaminate backup jsonl to use")
    ap.add_argument(
        "--resume-from",
        type=int,
        default=DEFAULT_RESUME_FROM,
        help="re-embed todo entries from this offset; 0 rewrites every changed chunk",
    )
    ap.add_argument("--no-verify", action="store_true", help="skip the read-back samples")
    args = ap.parse_args()

    backup_path = Path(args.backup) if args.backup else latest_backup()
    print("=" * 74)
    print("PINECONE / POSTGRES RECONCILIATION", " APPLY " if args.apply else " DRY-RUN ")
    print("=" * 74)
    print(f"  backup  : {backup_path}")
    print(f"  resume  : from todo offset {args.resume_from:,}")

    with backup_path.open(encoding="utf-8") as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    plans = [r for r in recs if r.get("kind") != "dropped"]
    drops = [r for r in recs if r.get("kind") == "dropped"]
    print(f"  plan    : {len(plans):,} cleaned documents")
    print(f"  drops   : {len(drops):,} deleted documents")
    if not plans:
        raise SystemExit("ABORT: backup contains no cleaned documents")

    manifest = load_manifest()
    print("  rebuilding chunks from stored content...", flush=True)
    targets, n_old = await build_targets(plans, manifest)
    print(f"  rebuilt : {len(targets):,} chunks, all match the stored rows")

    # The original chunk texts, straight from the payloads the index was built
    # from -- chunking alone cannot reproduce them, because ShapeChunker cleans
    # its input, so re-chunking pre-cleaning text would yield the new counts.
    print("  reading original chunk payloads...", flush=True)
    original = load_original_chunks({r["doc_id"] for r in plans})
    drift = [
        r["doc_id"]
        for r in plans
        if len(original.get(r["doc_id"], {})) != r.get("n_chunks", 0)
    ]
    if drift:
        print(
            f"  WARNING: {len(drift)} documents whose cache chunk count differs "
            "from the backup's old count (first: "
            f"{drift[0]}, cache {len(original.get(drift[0], {}))}, "
            f"backup {dict((r['doc_id'], r.get('n_chunks')) for r in plans)[drift[0]]})",
            flush=True,
        )

    # Split into "vector already correct" and "needs a new vector" using the
    # original chunk texts, exactly the rule decontaminate_corpus applied.
    keep: list[tuple[str, str, object, Document]] = []
    todo: list[tuple[str, str, object, Document]] = []
    seen: dict[str, int] = defaultdict(int)
    for doc_key, vid, ch, row in targets:
        i = seen[doc_key]
        seen[doc_key] += 1
        prev = original.get(doc_key, {}).get(i)
        if prev and prev[0] == ch.text and prev[1] == ch.citation:
            keep.append((doc_key, vid, ch, row))
        else:
            todo.append((doc_key, vid, ch, row))

    target_set = {t[1] for t in targets}

    # Ids Postgres no longer has: the pre-cleaning numbering of every cleaned
    # document, plus everything belonging to a dropped document.
    surplus: list[str] = []
    for rec in plans:
        for i in range(1, rec.get("n_chunks", 0) + 1):
            vid = pinecone_id(rec["doc_id"], i)
            if vid not in target_set:
                surplus.append(vid)
    drop_ids: list[str] = []
    for rec in drops:
        for i in range(1, rec.get("n_chunks", 0) + 1):
            drop_ids.append(pinecone_id(rec["doc_id"], i))

    boundary = max(0, min(args.resume_from, len(todo)))
    stale = todo[boundary:]

    table(
        "Plan",
        ["item", "count"],
        [
            ["cleaned documents", f"{len(plans):,}"],
            ["new chunks in Postgres", f"{len(targets):,}"],
            ["vector already correct", f"{len(keep):,}"],
            ["changed chunks (todo)", f"{len(todo):,}"],
            ["  ... already upserted", f"{len(todo) - len(stale):,}"],
            ["  ... to embed + upsert", f"{len(stale):,}"],
            ["surplus ids to delete", f"{len(surplus):,}"],
            ["dropped-doc ids to delete", f"{len(drop_ids):,}"],
            ["old chunks before cleaning", f"{n_old:,}"],
        ],
    )
    print(
        f"\n  keep/todo = {len(keep):,}/{len(todo):,} "
        f"(interrupted run reported 15,578/11,686)",
        flush=True,
    )

    from app.db.pinecone import pinecone_client

    index = pinecone_client.index

    # Confirm the resume point against the index itself before trusting it.
    if not args.no_verify and boundary > 0:
        probe = spread([t[1] for t in todo[:boundary]], SAMPLE_CHECK)
        print(f"\n  checking {len(probe):,} already-upserted vectors...", flush=True)
        meta = await fetch_metadata(probe)
        want = {t[1]: t[2] for t in todo[:boundary]}
        bad = [
            vid
            for vid in probe
            if vid not in meta
            or meta[vid].get("text") != want[vid].text[:META_TEXT_CHARS]
            or (meta[vid].get("citation") or "") != (want[vid].citation or "")
        ]
        if bad:
            print(
                f"  {len(bad)} of {len(probe)} sampled vectors are stale -- "
                "the interrupted run got further than its last progress line; "
                "re-embedding every changed chunk instead.",
                flush=True,
            )
            boundary = 0
            stale = todo
        else:
            print(
                f"  all {len(probe):,} sampled vectors match -- resume point confirmed",
                flush=True,
            )

    if not args.apply:
        print("\n  DRY-RUN: no writes; counts and read-back samples follow.")

    if args.apply and stale:
        sample_by_doc: dict[str, str] = {}
        for doc_key, vid, _ch, _row in targets:
            sample_by_doc.setdefault(doc_key, vid)
        meta_cache: dict[str, dict] = {}

        def doc_meta(doc_key: str, row: Document) -> dict:
            """Document-level metadata: prefer what the index already stores for
            that document, else fall back to the row -- never drop allowed_roles."""
            vid = sample_by_doc.get(doc_key)
            got = meta_cache.get(vid) if vid else None
            if got:
                return dict(got)
            return {
                "doc_id": row.doc_id or "",
                "source_title": row.title or row.source_file or "",
                "department": row.department or "",
                "classification": row.classification or "",
                "allowed_roles": row.allowed_roles or [],
                "source_file": row.source_file or "",
            }

        # One vector per document carries the document-level fields.
        seen_ids: dict[str, None] = {}
        for doc_key, _vid, _ch, _row in stale:
            sid = sample_by_doc.get(doc_key)
            if sid:
                seen_ids.setdefault(sid, None)
        doc_samples = list(seen_ids)
        print(f"\n  reading document metadata for {len(doc_samples):,} documents...", flush=True)
        try:
            got = await fetch_metadata(doc_samples)
            meta_cache.update(got)
            print(f"  read {len(got):,} of {len(doc_samples):,}", flush=True)
        except Exception as exc:
            print(f"  WARNING: document metadata read failed ({exc}); using Postgres", flush=True)

        vectors = embed_all([ch.text for _k, _v, ch, _r in stale])
        print(f"  embedded {len(vectors):,} vectors", flush=True)

        recs_out = [
            (vid, vec, doc_key, ch, row)
            for vec, (doc_key, vid, ch, row) in zip(vectors, stale)
        ]
        t0 = time.time()
        for start in range(0, len(recs_out), PINECONE_BATCH):
            batch = recs_out[start : start + PINECONE_BATCH]
            vecs = []
            for vid, vec, doc_key, ch, row in batch:
                md = doc_meta(doc_key, row)
                md.update(
                    {
                        "text": ch.text[:META_TEXT_CHARS],
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
            if (start // PINECONE_BATCH) % 10 == 0:
                done = min(start + len(batch), len(recs_out))
                pct = 100.0 * done / len(recs_out)
                print(
                    f"    upsert {done:,}/{len(recs_out):,} ({pct:.0f}%)  {time.time() - t0:.0f}s",
                    flush=True,
                )
        print(f"  pinecone: {len(recs_out):,} vectors upserted", flush=True)

    if args.apply:
        for start in range(0, len(surplus), PINECONE_BATCH):
            index.delete(ids=surplus[start : start + PINECONE_BATCH])
            if (start // PINECONE_BATCH) % 10 == 0:
                done = min(start + PINECONE_BATCH, len(surplus))
                print(f"    surplus {done:,}/{len(surplus):,}", flush=True)
        print(f"  pinecone: {len(surplus):,} surplus ids deleted", flush=True)

        for start in range(0, len(drop_ids), PINECONE_BATCH):
            index.delete(ids=drop_ids[start : start + PINECONE_BATCH])
        print(f"  pinecone: {len(drop_ids):,} dropped-doc ids deleted", flush=True)

    from sqlalchemy import text as sql_text

    async with async_session() as db:
        n_chunks = (await db.execute(sql_text("select count(*) from document_chunks"))).scalar()
        n_docs = (await db.execute(sql_text("select count(*) from documents"))).scalar()

    stats = index.describe_index_stats().to_dict()
    n_vec = stats.get("total_vector_count", 0)
    table(
        "Result",
        ["store", "count"],
        [
            ["postgres documents", f"{n_docs:,}"],
            ["postgres chunks", f"{n_chunks:,}"],
            ["pinecone vectors", f"{n_vec:,}"],
        ],
    )
    ok = n_vec == n_chunks
    print(f"\n  index vs database: {'match' if ok else f'MISMATCH {n_vec - n_chunks:+,}'}")

    if args.no_verify:
        print("\n  (read-back samples skipped)")
    else:
        # Sample both sides: freshly written vectors, and the ones we assumed
        # were already correct.
        checks = [("rewritten", [t[1] for t in stale]), ("untouched", [t[1] for t in keep])]
        for label, pool in checks:
            if not pool:
                continue
            probe = spread(pool, SAMPLE_FINAL)
            want = {t[1]: t[2] for t in targets}
            print(f"\n  verifying {len(probe):,} {label} vectors...", flush=True)
            meta = await fetch_metadata(probe)
            bad = [
                vid
                for vid in probe
                if vid not in meta
                or meta[vid].get("text") != want[vid].text[:META_TEXT_CHARS]
                or (meta[vid].get("citation") or "") != (want[vid].citation or "")
            ]
            if bad:
                ok = False
                print(
                    f"  FAIL: {len(bad)} of {len(probe):,} {label} vectors differ "
                    f"(e.g. {bad[0]})"
                )
            else:
                print(f"  OK: {len(probe):,} {label} vectors match Postgres")

    if ok:
        print("\n  OK: index and database agree.")
    else:
        print("\n  MISMATCH -- re-run this script.")
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
