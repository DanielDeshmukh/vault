"""Embed corpus/v2_dryrun records into the Pinecone ``v2`` namespace (Phase 5).

Modes
-----
  --pilot   ~1000 records, stratified evenly across departments
  (default) every record in records.jsonl (61,807)

Guarantees
----------
- ``input_type="passage"`` on every embed call (NVIDIA requirement; the old
  pipeline omitted it and the endpoint silently used query mode).
- Resume-safe: each confirmed batch appends ``{"ids": [...]}`` to a state
  file; re-runs skip those ids. Upserts are keyed by ``chunk_id``, so a
  crash mid-batch only repeats that batch (upsert overwrites idempotently).
- Backoff on 429/5xx for both the embed API (app.embeddings) and Pinecone
  upserts (this script).
- Metadata is the CP3-approved small payload only: department,
  classification, allowed_roles, heading_path, content_hash, doc_id,
  doc_title, source_type, block_type, chunk_version and a ~300-char
  ``text`` snippet for rerank. Full ``text_md`` stays in Postgres.

``--target local|neon`` is REQUIRED (scripts/db_target.py): the associated
Postgres must be chosen explicitly, its masked host is printed before any
write, and the run aborts if that host does not match the target -- the
resume state of a run must never be paired with an ambiguous environment.

Usage (cwd = server/):
  python scripts/embed_v2.py --target local --pilot
  python scripts/embed_v2.py --target local            # full run, concurrency 3
  python scripts/embed_v2.py --target local --concurrency 4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent
RECORDS_PATH = REPO_ROOT / "corpus" / "v2_dryrun" / "records.jsonl"
STATE_DIR = REPO_ROOT / "corpus" / "v2_dryrun"
sys.path.insert(0, str(SERVER_DIR))

from scripts.db_target import add_target_arg, resolve_target  # noqa: E402

BATCH = 128
SNIPPET = 300
UPSERT_CHUNK = 64
UPSERT_RETRIES = 6
META_FIELDS = (
    "doc_id",
    "doc_title",
    "department",
    "classification",
    "allowed_roles",
    "heading_path",
    "source_type",
    "block_type",
    "chunk_version",
    "content_hash",
)

_print_lock = threading.Lock()
_state_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_env() -> None:
    for line in (SERVER_DIR / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def load_records() -> list[dict]:
    recs: list[dict] = []
    with RECORDS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            recs.append(json.loads(line))
    return recs


def stratified_pilot(recs: list[dict], limit: int) -> list[dict]:
    """Evenly spaced sample across departments, deterministic file order."""
    by_dept: dict[str, list[dict]] = {}
    for r in recs:
        by_dept.setdefault(r["metadata"].get("department") or "unknown", []).append(r)
    depts = sorted(by_dept)
    quota, rem = divmod(limit, len(depts))
    picked: list[dict] = []
    counts: dict[str, int] = {}
    for i, dept in enumerate(depts):
        pool = by_dept[dept]
        take = quota + (1 if i < rem else 0)
        take = min(take, len(pool))
        stride = max(1, len(pool) // take)
        part = pool[::stride][:take]
        counts[dept] = len(part)
        picked.extend(part)
    dist = ", ".join(f"{d}:{counts[d]}" for d in depts)
    log(f"pilot: {len(picked)} records across {len(depts)} departments ({dist})")
    return picked


def load_state(paths: list[Path]) -> set[str]:
    done: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.update(json.loads(line).get("ids") or [])
            except json.JSONDecodeError:
                continue
    return done


def meta_payload(md: dict) -> dict:
    payload = {k: md.get(k) for k in META_FIELDS}
    text = md.get("text_md") or md.get("text_embed") or ""
    payload["text"] = text[:SNIPPET]
    return payload


def upsert_with_retry(index, vectors: list[dict]) -> None:
    last: Exception | None = None
    for attempt in range(UPSERT_RETRIES):
        try:
            for start in range(0, len(vectors), UPSERT_CHUNK):
                index.upsert(vectors=vectors[start : start + UPSERT_CHUNK], namespace="v2")
            return
        except Exception as exc:  # noqa: BLE001 - backoff on 429/5xx, raise fatal
            last = exc
            msg = str(exc).lower()
            retryable = any(s in msg for s in ("429", "500", "502", "503", "504",
                                               "rate", "timeout", "temporar", "unavailable"))
            if not retryable or attempt == UPSERT_RETRIES - 1:
                raise
            delay = 2.0 * (2**attempt)
            log(f"    [upsert] {type(exc).__name__}: {str(exc)[:120]}; retry in {delay:.0f}s")
            time.sleep(delay)
    raise RuntimeError(f"upsert failed after {UPSERT_RETRIES} attempts: {last}")


def process_batch(batch: list[dict], index, state_path: Path) -> tuple[int, float]:
    from app.embeddings import embed_texts

    texts = [m["metadata"].get("text_embed") or "" for m in batch]
    t0 = time.perf_counter()
    vectors_batch = embed_texts(texts, input_type="passage")
    embed_secs = time.perf_counter() - t0
    vectors = [
        {
            "id": rec["id"],
            "values": vec,
            "metadata": meta_payload(rec["metadata"]),
        }
        for rec, vec in zip(batch, vectors_batch)
    ]
    upsert_with_retry(index, vectors)
    with _state_lock:
        with state_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ids": [v["id"] for v in vectors],
                                 "ts": time.time()}) + "\n")
    return len(vectors), embed_secs


def main() -> int:
    ap = argparse.ArgumentParser()
    add_target_arg(ap)
    ap.add_argument("--pilot", action="store_true", help="~1000 stratified records")
    ap.add_argument("--limit", type=int, default=1000, help="pilot size")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--namespace", default="v2")
    args = ap.parse_args()

    load_env()
    # Explicit target: validate + print masked DB host BEFORE any write.
    os.environ["DATABASE_URL"] = resolve_target(args.target, env_loaded=True)

    from pinecone import Pinecone

    from app.config import settings
    from app.embeddings import EMBED_DIM

    recs = load_records()
    picked = stratified_pilot(recs, args.limit) if args.pilot else recs
    state_path = STATE_DIR / ("embed_state_pilot.jsonl" if args.pilot else "embed_state_full.jsonl")
    done = load_state([STATE_DIR / "embed_state_full.jsonl", STATE_DIR / "embed_state_pilot.jsonl"])
    todo = [r for r in picked if r["id"] not in done]
    log(f"records: total={len(recs)} selected={len(picked)} done={len(picked) - len(todo)} todo={len(todo)}")
    log(f"[write] pinecone index={settings.PINECONE_INDEX_NAME} "
        f"namespace={args.namespace!r} host={settings.PINECONE_INDEX_HOST}")

    if args.namespace != "v2":
        log(f"WARNING: namespace {args.namespace!r} (upsert_with_retry hardcodes v2; "
            "pass matching --namespace only for stats)")

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX_NAME, host=settings.PINECONE_INDEX_HOST)

    batches = [todo[i : i + BATCH] for i in range(0, len(todo), BATCH)]
    log(f"batches: {len(batches)} x up to {BATCH}, concurrency {args.concurrency}, "
        f"dim {EMBED_DIM}, input_type=passage")

    started = time.monotonic()
    done_count = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = {pool.submit(process_batch, b, index, state_path): b for b in batches}
        for fut in as_completed(futs):
            batch = futs[fut]
            try:
                n, embed_secs = fut.result()
            except Exception as exc:  # noqa: BLE001 - report, keep going; resume fixes
                errors += 1
                log(f"  BATCH FAILED ({batch[0]['id']}..{batch[-1]['id']}): {type(exc).__name__}: {str(exc)[:200]}")
                continue
            done_count += n
            elapsed = time.monotonic() - started
            rate = done_count / elapsed if elapsed else 0
            eta = (len(todo) - done_count) / rate if rate else -1
            log(f"  upserted {done_count}/{len(todo)} "
                f"(batch {embed_secs:.1f}s embed, elapsed {elapsed:.0f}s, eta {eta:.0f}s, errors={errors})")

    elapsed = time.monotonic() - started
    log(f"done: upserted={done_count} errors={errors} elapsed={elapsed:.0f}s")
    try:
        stats = index.describe_index_stats()
        ns = (stats.get("namespaces") or {}).get("v2") or {}
        log(f"namespace v2 vector_count: {ns.get('vector_count')}")
    except Exception as exc:  # noqa: BLE001 - stats are informational
        log(f"describe_index_stats failed: {exc}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
