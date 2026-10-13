"""Embed the shape-chunked corpus and load it into Postgres + Pinecone.

Runs in two phases so nothing is deleted until every embedding has landed:

  embed   read corpus/chunks.jsonl -> corpus/embeddings.npy
          reports batches / failures, touches neither database
  load    wipe + insert documents and document_chunks, upsert vectors
  all     embed, then load only if the embed phase had zero failures

Embedding input is truncated to 2000 chars because embed-english-v3.0 caps
input at 512 tokens. Full text still lands in documents.content and
document_chunks.content; Pinecone metadata carries the first 4000 chars of
``text`` so the record stays under the 40 KB metadata limit.

Usage:
    python server/scripts/ingest_corpus.py --phase embed
    python server/scripts/ingest_corpus.py --phase load
    python server/scripts/ingest_corpus.py --phase all [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import asyncpg

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"
CHUNKS = CORPUS / "chunks.jsonl"
EMBED_NPY = CORPUS / "embeddings.npy"
EMBED_IDS = CORPUS / "embedding_ids.json"

# Chars fed to the embedder. The provider also truncates internally, but
# keeping the corpus-side cap explicit documents what was actually embedded.
EMBED_CHARS = 2000
# Pinecone rejects a request whose decoded message exceeds 4 MB. The binding
# cost is 4 bytes per float (2048-dim -> 8 KB) plus ~6.8 KB of worst-case
# protobuf metadata, so a batch tops out near 280 records. 100 keeps us at
# ~1.5 MB worst case.
PINECONE_BATCH = 100
# Metadata cap is 40 KB and rerank/generation only read [:1500]/[:1000].
META_TEXT_CHARS = 4000

PG_BATCH = 1000

# Legacy tier value per classification, so the old tier UI keeps working
# alongside the role-based filter.
ACCESS_LEVEL_BY_CLASSIFICATION = {"internal": 1, "restricted": 3}

# Pinecone metadata keys, in a stable order.
META_KEYS = (
    "tenant_id",
    "doc_id",
    "source_title",
    "department",
    "classification",
    "allowed_roles",
    "allowed_groups",
    "owner",
    "version",
    "page",
    "updated_at",
    "text",
    "citation",
    "source_file",
    "section_title",
    "section_index",
    "section_parts",
    "part",
    "section_span_start",
    "section_span_end",
)


def _load_env() -> None:
    """Pull server/.env into the environment without adding a dependency."""
    env_path = REPO / "server" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise SystemExit(f"ERROR: {name} is not set (expected in server/.env)")
    return val


def _read_records(limit: int | None) -> list[dict]:
    if not CHUNKS.exists():
        raise SystemExit(f"missing {CHUNKS} -- run build_chunks.py first")
    records: list[dict] = []
    with CHUNKS.open(encoding="utf-8") as fh:
        for line in fh:
            records.append(json.loads(line))
            if limit and len(records) >= limit:
                break
    return records


# ---------------------------------------------------------------- embed ----

# Embedding is delegated to app.embeddings, which owns provider backoff.
# This script keeps only checkpointing and per-batch failure isolation.
# Checkpoint every N batches so a mid-run failure resumes rather than restarts.
CHECKPOINT_EVERY = 20
EMBED_CKPT = CORPUS / "embeddings.ckpt.npz"


def _embed(records: list[dict], resume: bool = True) -> int:
    """Embed every record via app.embeddings. Returns the number of failures."""
    import numpy as np

    from app.embeddings import EMBED_DIM, NIM_BATCH, embed_texts

    n = len(records)
    want_ids = [r["id"] for r in records]
    vectors = np.zeros((n, EMBED_DIM), dtype=np.float32)
    done = np.zeros(n, dtype=bool)

    # Resume from a checkpoint when it matches this exact record set.
    if resume and EMBED_CKPT.exists():
        try:
            with np.load(EMBED_CKPT) as ck:
                if list(ck["ids"]) == want_ids and ck["vectors"].shape == vectors.shape:
                    vectors = ck["vectors"]
                    done = ck["done"]
                    print(f"  resumed: {int(done.sum()):,}/{n:,} already embedded")
                else:
                    print("  checkpoint does not match current chunks.jsonl; restarting")
        except Exception as exc:  # noqa: BLE001 - a corrupt ckpt is just a restart
            print(f"  checkpoint unreadable ({type(exc).__name__}); restarting")

    failures = 0
    pending: list[int] = [i for i in range(n) if not done[i]]
    batches = (len(pending) + NIM_BATCH - 1) // NIM_BATCH
    t0 = time.time()

    def save_ckpt() -> None:
        tmp = EMBED_CKPT.with_name(EMBED_CKPT.name + ".tmp")
        # np.savez appends ".npz" to a filename, so pass a file object.
        with open(tmp, "wb") as fh:
            np.savez(fh, ids=np.array(want_ids, dtype=object), vectors=vectors, done=done)
        os.replace(tmp, EMBED_CKPT)

    b = 0
    idx = 0
    while idx < len(pending):
        b += 1
        starts = pending[idx : idx + NIM_BATCH]
        texts = [records[i]["metadata"]["text"][:EMBED_CHARS] for i in starts]
        try:
            emb = embed_texts(texts, dim=EMBED_DIM)
            for j, vec in enumerate(emb):
                vectors[starts[j]] = vec
            for i in starts:
                done[i] = True
            idx += len(starts)
            failures = 0
        except Exception as exc:  # noqa: BLE001 - isolate the failure, keep going
            failures += len(starts)
            print(f"  FAIL batch {b}/{batches}: {type(exc).__name__}: {str(exc)[:160]}")
            idx += len(starts)  # skip past; recorded as failed below

        if b % CHECKPOINT_EVERY == 0 or idx >= len(pending):
            save_ckpt()
            rate = b / max(time.time() - t0, 1e-9)
            eta = (batches - b) / max(rate, 1e-9)
            print(
                f"  batch {b}/{batches}  done={int(done.sum()):,}/{n:,}  "
                f"failures={failures}  eta {eta / 60:.1f} min",
                flush=True,
            )

    if not done.all():
        missing = int((~done).sum())
        print(f"\nEMBED FAILED: {missing}/{n} texts unembedded -- nothing will be written")
        print(f"  checkpoint kept at {EMBED_CKPT}; rerun --phase embed to resume")
        return missing

    save_ckpt()
    np.save(EMBED_NPY, vectors)
    EMBED_IDS.write_text(json.dumps(want_ids, indent=0), encoding="utf-8")
    elapsed = time.time() - t0
    print(f"\nembed ok: {n:,} vectors, {batches:,} API calls, {elapsed / 60:.1f} min")
    print(f"  {EMBED_NPY}  ({EMBED_NPY.stat().st_size:,} bytes)")
    print(f"  {EMBED_IDS}")
    return 0


# ----------------------------------------------------------------- load ----


def _meta_for(meta: dict) -> dict:
    out = {}
    for key in META_KEYS:
        if key not in meta:
            continue
        val = meta[key]
        if key == "text":
            val = val[:META_TEXT_CHARS]
        out[key] = val
    return out


async def _wipe(conn: asyncpg.Connection) -> None:
    # FK order: children first. document_access/document_chunks -> documents.
    for table in ("document_access", "document_chunks", "documents"):
        result = await conn.execute(f"DELETE FROM {table}")
        print(f"  cleared {table}: {result.split()[-1]} rows")


async def _load_pg(conn: asyncpg.Connection, records: list[dict]) -> dict:
    """Insert documents + document_chunks. Returns doc_id -> uuid map."""
    # Group chunk records by document, preserving first-seen order.
    doc_order: list[str] = []
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        did = rec["metadata"]["doc_id"]
        if did not in by_doc:
            doc_order.append(did)
        by_doc[did].append(rec)

    # Document content is the *cleaned* text the chunker offset against, so
    # section_span_start/end index directly into documents.content.
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location(
        "shape_chunker", REPO / "server" / "app" / "ingestion" / "shape_chunker.py"
    )
    mod = module_from_spec(spec)
    sys.modules["shape_chunker"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    manifest = {}
    with (CORPUS / "manifest.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            manifest[entry["path"]] = entry

    doc_rows = []
    doc_id_to_uuid: dict[str, str] = {}
    content_chars = 0

    for did in doc_order:
        first = by_doc[did][0]["metadata"]
        rel_path = first["source_file"]
        raw = (CORPUS / rel_path).read_text(encoding="utf-8", errors="replace")
        if rel_path.lower().endswith((".htm", ".html")):
            content = mod._html_to_prose(raw)
        else:
            content = mod._strip_markdown_frontmatter(raw)[0]
        content_chars += len(content)

        entry = manifest.get(rel_path, {})
        source = (entry.get("source") or first["department"])[:100]
        level = ACCESS_LEVEL_BY_CLASSIFICATION.get(first["classification"], 0)
        # Passed as raw objects: the connection's json codec already runs
        # json.dumps, so pre-serialising here double-encodes the value and the
        # column decodes back to str instead of list/dict.
        meta_obj = {
            "tenant_id": first["tenant_id"],
            "allowed_groups": first.get("allowed_groups", []),
            "allowed_roles": first.get("allowed_roles", []),
            "source_path": rel_path,
        }
        doc_rows.append(
            (
                did,
                first["source_title"][:500],
                content,
                source,
                rel_path,
                first["department"],
                level,
                first["classification"],
                first.get("allowed_roles", []),
                meta_obj,
            )
        )

    await conn.executemany(
        """
        INSERT INTO documents
            (id, doc_id, title, content, source, source_file, department,
             access_level, classification, allowed_roles, metadata,
             created_at, updated_at)
        VALUES
            (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9::json,
             $10::json, now(), now())
        """,
        doc_rows,
    )
    rows = await conn.fetch("SELECT id, doc_id FROM documents")
    doc_id_to_uuid = {r["doc_id"]: str(r["id"]) for r in rows}
    print(f"  documents: {len(doc_rows):,} rows, {content_chars:,} content chars")

    # --- chunks ---
    chunk_rows = []
    for rec in records:
        md = rec["metadata"]
        chunk_no = int(rec["id"].rsplit("_", 1)[-1]) - 1  # 0-based chunk_index
        chunk_rows.append(
            (
                doc_id_to_uuid[md["doc_id"]],
                md["text"],
                chunk_no,
                rec["id"],
                md.get("citation", ""),
                md.get("section_index", 0),
                md.get("section_span_start", 0),
                md.get("section_span_end", 0),
                md.get("part", 1),
                md.get("section_parts", 1),
            )
        )

    for start in range(0, len(chunk_rows), PG_BATCH):
        await conn.executemany(
            """
            INSERT INTO document_chunks
                (id, document_id, content, chunk_index, pinecone_id, citation,
                 section_index, section_span_start, section_span_end,
                 part, section_parts, created_at)
            VALUES
                (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
            """,
            chunk_rows[start : start + PG_BATCH],
        )
    print(f"  document_chunks: {len(chunk_rows):,} rows")

    return doc_id_to_uuid


def _upsert_with_retry(index, payload: list[dict], attempts: int = 5) -> None:
    """Upsert one batch, retrying transient failures with exponential backoff."""
    delay = 5.0
    for attempt in range(attempts):
        try:
            index.upsert(vectors=payload)
            return
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            # Oversize batches and other 4xx client errors will never succeed.
            status = getattr(exc, "status", None) or getattr(exc, "code", None)
            if status is not None and 400 <= int(status) < 500 and int(status) != 429:
                raise
            print(
                f"    [upsert] {type(exc).__name__} on attempt {attempt + 1}/"
                f"{attempts}; retrying in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 60.0)


def _resume_index(index, total: int, batch: int = PINECONE_BATCH) -> int:
    """Find how many leading records are already in Pinecone.

    Upstream writes are strictly sequential and upsert is idempotent by ID, so
    the index's vector count is the resume point. ``describe_index_stats`` can
    lag, so we confirm by fetching the ID at the boundary and walk back until
    we find one that actually exists -- an over-count would otherwise leave a
    silent gap of records that never get written.
    """
    from app.db.pinecone import pinecone_client

    ids = json.loads(EMBED_IDS.read_text(encoding="utf-8"))
    n = min(total, len(ids))
    if n <= 0:
        return 0

    # Round down to a batch boundary, then step back one extra batch: cheap
    # (re-upserting is a no-op overwrite) and absorbs any lag in the stats.
    probe = max(0, (n // batch) * batch - batch)

    while probe > 0:
        # FetchResponse exposes attribute access, not mapping access.
        got = pinecone_client.index.fetch(ids=[ids[probe - 1]])
        if getattr(got, "vectors", None):
            return probe
        print(f"  resume probe: {ids[probe - 1]} absent; stepping back", flush=True)
        probe = max(0, probe - batch)
    return 0


def _load_pinecone(records: list[dict], start: int = 0) -> int:
    import numpy as np

    from app.db.pinecone import pinecone_client

    vectors = np.load(EMBED_NPY)
    ids = json.loads(EMBED_IDS.read_text(encoding="utf-8"))
    if len(vectors) != len(records) or len(ids) != len(records):
        raise SystemExit(
            f"embed artefacts out of sync: npy={len(vectors)} ids={len(ids)} "
            f"records={len(records)} -- rerun --phase embed"
        )
    if ids != [r["id"] for r in records]:
        raise SystemExit(
            "embedding_ids.json does not match chunks.jsonl order -- "
            "chunks.jsonl changed since the embed pass; rerun --phase embed"
        )

    if start:
        print(f"  resuming upsert at record {start:,}/{len(records):,}", flush=True)

    index = pinecone_client.index
    remaining = records[start:]
    batches = (len(remaining) + PINECONE_BATCH - 1) // PINECONE_BATCH
    t0 = time.time()
    for b, rel in enumerate(range(0, len(remaining), PINECONE_BATCH), start=1):
        start_i = start + rel
        stop = min(start_i + PINECONE_BATCH, len(records))
        payload = [
            {
                "id": records[i]["id"],
                "values": vectors[i].tolist(),
                "metadata": _meta_for(records[i]["metadata"]),
            }
            for i in range(start_i, stop)
        ]
        # A transient failure at batch 400/491 would otherwise kill the run
        # after the Postgres wipe has already happened.
        _upsert_with_retry(index, payload)
        if b % 25 == 0 or b == batches:
            print(
                f"  upsert {b}/{batches}  ({stop:,}/{len(records):,} vectors)",
                flush=True,
            )
    print(
        f"  pinecone: {len(remaining):,} vectors upserted in {time.time() - t0:.1f}s "
        f"({batches:,} batches of {PINECONE_BATCH})"
    )
    return len(records)


async def _load(records: list[dict], resume: bool = False) -> int:
    import numpy as np

    if not EMBED_NPY.exists():
        raise SystemExit(f"missing {EMBED_NPY} -- run --phase embed first")
    vectors = np.load(EMBED_NPY, mmap_mode="r")
    if len(vectors) != len(records):
        raise SystemExit(
            f"embeddings cover {len(vectors):,} records but chunks.jsonl has "
            f"{len(records):,} -- rerun --phase embed"
        )
    del vectors  # _load_pinecone reopens it

    _require("DATABASE_URL")
    _require("PINECONE_API_KEY")
    _require("NVIDIA_API_KEY")

    from app.db.pinecone import pinecone_client

    stats = pinecone_client.index.describe_index_stats()
    already = int(stats.get("total_vector_count") or 0)

    # Postgres is written in a single transaction, so it is either fully
    # populated or untouched -- there is no partial state to repair.
    conn = await asyncpg.connect(_require("DATABASE_URL"))
    try:
        pg_docs = (
            await conn.fetchrow("SELECT count(*)::int AS n FROM documents")
        )["n"]
        pg_chunks = (
            await conn.fetchrow("SELECT count(*)::int AS n FROM document_chunks")
        )["n"]
    finally:
        await conn.close()
    pg_ok = pg_docs == len({r["metadata"]["doc_id"] for r in records}) and (
        pg_chunks == len(records)
    )

    if resume:
        print(f"\n[resume] pinecone has {already:,} vectors; postgres {'ok' if pg_ok else 'stale'}")
        if not pg_ok:
            raise SystemExit(
                "resume requested but Postgres does not match this corpus "
                f"({pg_docs:,} docs / {pg_chunks:,} chunks) -- rerun without --resume"
            )
        start = _resume_index(pinecone_client.index, already)
        print(f"[resume] continuing from record {start:,}/{len(records):,}", flush=True)
        print("[write] pinecone")
        _load_pinecone(records, start=start)
        return len(records)

    # Old vectors carry access_level/account_id metadata that no longer exists
    # in the schema, so the index is cleared rather than merged into.
    print("\n[wipe] pinecone")
    if already == 0:
        print("  index already empty; skipping wipe")
    else:
        try:
            pinecone_client.index.delete(delete_all=True, namespace="")
            print("  cleared pinecone index (delete_all)")
        except Exception as exc:  # noqa: BLE001 - fall back to a metadata filter
            print(f"  delete_all failed ({type(exc).__name__}); using tenant filter")
            pinecone_client.index.delete(filter={"tenant_id": {"$eq": "acme"}}, namespace="")
            print("  cleared pinecone index (tenant filter)")

    print("[wipe] postgres")
    conn = await asyncpg.connect(_require("DATABASE_URL"))
    try:
        await conn.set_type_codec(
            "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )
        async with conn.transaction():
            await _wipe(conn)
            print("[write] postgres")
            await _load_pg(conn, records)
    finally:
        await conn.close()

    print("[write] pinecone")
    _load_pinecone(records)
    return len(records)


# ----------------------------------------------------------------- main ----


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", choices=("embed", "load", "all"), default="all")
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="only the first N records (smoke test; leaves embeddings flagged as partial)",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="continue an interrupted load: keep Postgres and skip vectors already "
        "in Pinecone instead of wiping and starting over",
    )
    args = ap.parse_args()

    _load_env()
    records = _read_records(args.limit)
    print(
        f"chunks.jsonl: {len(records):,} records"
        + (f" (limited to {args.limit})" if args.limit else "")
    )

    if args.phase in ("embed", "all"):
        from app.embeddings import EMBED_DIM, NIM_BATCH, NIM_MAX_CHARS

        print(
            f"\n[embed] model=nvidia/nemotron-3-embed-1b dim={EMBED_DIM} "
            f"batch={NIM_BATCH} input<= {NIM_MAX_CHARS} chars"
        )
        failures = _embed(records)
        if failures and args.phase == "all":
            return 1
        if args.phase == "embed":
            return 1 if failures else 0

    n = asyncio.run(_load(records, resume=args.resume))
    print(f"\nDONE: {n:,} chunks loaded")
    if args.limit:
        print(f"NOTE: --limit {args.limit} was used -- this is a partial load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
