"""Build shape-aware chunk records from the fetched corpus.

Reads ``corpus/manifest.jsonl``, chunks every document with
``ShapeChunker``, and writes:

  corpus/chunks.jsonl      one canonical vector record per line
  corpus/chunk_stats.json  per-department counts + every defaulted field

Nothing is embedded and nothing is written to Pinecone or Postgres. This pass
exists so the chunks can be reviewed on disk first.

Usage:
    python server/scripts/build_chunks.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Load the chunker directly rather than via ``app.ingestion``. The package
# __init__ imports the pipeline, which imports the DB engine, which would
# require DATABASE_URL -- and this tool is deliberately offline.
_CHUNKER_PATH = REPO / "server" / "app" / "ingestion" / "shape_chunker.py"
_spec = importlib.util.spec_from_file_location("shape_chunker", _CHUNKER_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# dataclasses on 3.13 resolves cls.__module__ out of sys.modules.
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

ShapeChunker = _mod.ShapeChunker
_FRONTMATTER = _mod._FRONTMATTER
_FRONT_TITLE = _mod._FRONT_TITLE

CORPUS = REPO / "corpus"
TENANT_ID = "acme"

# Fields the manifest cannot supply. Defaulted here, then reported.
DEFAULTED_FIELDS = ("owner", "version", "page", "updated_at", "allowed_groups")

# Binary formats we have no parser for. Failing loudly beats chunking PDF
# bytes as markdown and silently filling the index with replacement chars.
UNSUPPORTED_EXTS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}


def _detect_kind(rel_path: str) -> str:
    p = rel_path.lower()
    if p.endswith((".htm", ".html")):
        return "sec_filing"
    if p.endswith(".md"):
        return "markdown"
    ext = Path(rel_path).suffix.lower()
    if ext in UNSUPPORTED_EXTS:
        raise ValueError(f"unsupported file type {ext!r} -- no parser (add one or skip)")
    return "markdown"


def _source_title(rel_path: str, text: str, kind: str) -> str:
    stem = Path(rel_path).stem.replace("_", " ").strip()
    if kind == "markdown":
        m = _FRONTMATTER.match(text)
        if m:
            t = _FRONT_TITLE.search(m.group(1))
            if t:
                val = t.group(1).strip().strip("\"'")
                if val:
                    return val
        return stem
    # SEC filing: <title> is just a ticker/date slug, so derive from filename.
    # e.g. apple_10k_2025-09-27 -> Apple 10-K (2025-09-27)
    parts = Path(rel_path).stem.split("_")
    if len(parts) >= 3 and parts[1] == "10k":
        return f"{parts[0].title()} 10-K ({parts[2]})"
    return stem


def build(limit: int | None = None, dry_run: bool = False) -> dict:
    manifest_path = CORPUS / "manifest.jsonl"
    if not manifest_path.exists():
        raise SystemExit(f"missing manifest: {manifest_path}")

    chunker = ShapeChunker()
    records: list[dict] = []
    stats = {
        "generated_at": int(time.time()),
        "tenant_id": TENANT_ID,
        "max_chunk_chars": chunker.max_chunk_chars,
        "defaulted_fields": list(DEFAULTED_FIELDS),
        "total_documents": 0,
        "total_chunks": 0,
        "by_department": defaultdict(lambda: {"documents": 0, "chunks": 0, "chars": 0}),
        "by_kind": Counter(),
        "untitled_chunks": 0,
        "untitled_chars": 0,
        "warnings": [],
        "failed": [],
    }

    # doc_id is allocated per department, matching doc_{dept}_{NNNN}.
    counters: dict[str, int] = defaultdict(int)

    with manifest_path.open(encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]

    if limit:
        entries = entries[:limit]

    for entry in entries:
        rel_path = entry["path"]
        dept = entry["department"]
        try:
            kind = _detect_kind(rel_path)
        except ValueError as exc:
            stats["failed"].append({"path": rel_path, "error": str(exc)})
            continue
        abs_path = CORPUS / rel_path

        if not abs_path.exists():
            stats["failed"].append({"path": rel_path, "error": "file missing"})
            continue

        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - report, don't abort the run
            stats["failed"].append({"path": rel_path, "error": repr(exc)})
            continue

        counters[dept] += 1
        doc_id = f"doc_{dept}_{counters[dept]:04d}"
        title = _source_title(rel_path, text, kind)
        updated_at = int(abs_path.stat().st_mtime)

        chunks, report = chunker.chunk(text, rel_path, kind, source_title=title)
        stats["total_documents"] += 1
        stats["by_department"][dept]["documents"] += 1
        stats["by_department"][dept]["chunks"] += len(chunks)
        stats["by_department"][dept]["chars"] += sum(len(c.text) for c in chunks)
        stats["by_kind"][kind] += 1

        for w in report.warnings:
            stats["warnings"].append({"path": rel_path, "warning": w})

        # Chunk numbering is per document: doc_hr_0042#chunk_007 is the 7th
        # chunk of that document, not the 7th in the department.
        doc_chunk_no = 0
        for chunk in chunks:
            doc_chunk_no += 1
            untitled = "#" not in chunk.citation
            if untitled:
                stats["untitled_chunks"] += 1
                stats["untitled_chars"] += len(chunk.text)
            record = {
                "id": f"{doc_id}#chunk_{doc_chunk_no:03d}",
                "values": [],
                "metadata": {
                    "tenant_id": TENANT_ID,
                    "doc_id": doc_id,
                    "source_title": title,
                    "department": dept,
                    "classification": entry["classification"],
                    "allowed_roles": list(entry["allowed_roles"]),
                    "allowed_groups": [dept],
                    "owner": "",
                    "version": 1,
                    "page": 0,
                    "updated_at": updated_at,
                    "text": chunk.text,
                    "citation": chunk.citation,
                    "source_file": rel_path,
                    "section_title": chunk.section_title or "",
                    "section_index": chunk.section_index,
                    "section_parts": chunk.parts,
                    "section_span_start": chunk.section_char_start,
                    "section_span_end": chunk.section_char_end,
                },
            }
            records.append(record)
            stats["total_chunks"] += 1

    if dry_run:
        return stats

    out_jsonl = CORPUS / "chunks.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stats["output"] = str(out_jsonl)
    stats["output_bytes"] = out_jsonl.stat().st_size
    stats["by_department"] = dict(stats["by_department"])
    stats["by_kind"] = dict(stats["by_kind"])

    out_stats = CORPUS / "chunk_stats.json"
    out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    stats["stats_path"] = str(out_stats)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="only first N manifest entries")
    ap.add_argument("--dry-run", action="store_true", help="compute stats, write nothing")
    args = ap.parse_args()

    t0 = time.time()
    stats = build(limit=args.limit, dry_run=args.dry_run)
    elapsed = time.time() - t0

    mode = "DRY RUN" if args.dry_run else "WROTE"
    print(
        f"\n[{mode}] {stats['total_documents']:,} documents -> "
        f"{stats['total_chunks']:,} chunks in {elapsed:.1f}s"
    )
    if not args.dry_run:
        print(f"  records: {stats['output']}  ({stats['output_bytes']:,} bytes)")
        print(f"  stats:   {stats['stats_path']}")
    print(f"\n  by kind: {dict(stats['by_kind'])}")
    print(f"\n  {'department':<14} {'docs':>7} {'chunks':>8} {'chars':>12}")
    print(f"  {'-' * 14} {'-' * 7} {'-' * 8} {'-' * 12}")
    for dept, s in sorted(stats["by_department"].items(), key=lambda kv: -kv[1]["chunks"]):
        print(f"  {dept:<14} {s['documents']:>7,} {s['chunks']:>8,} {s['chars']:>12,}")
    print(f"\n  defaulted fields: {', '.join(stats['defaulted_fields'])}")
    print(
        f"  untitled chunks: {stats['untitled_chunks']:,} "
        f"({stats['untitled_chars']:,} chars, no #heading in citation)"
    )
    if stats["warnings"]:
        print(f"\n  {len(stats['warnings'])} warnings:")
        for w in stats["warnings"][:10]:
            print(f"    {w['path']}: {w['warning']}")
        if len(stats["warnings"]) > 10:
            print(f"    ... +{len(stats['warnings']) - 10} more")
    if stats["failed"]:
        print(f"\n  {len(stats['failed'])} failed:")
        for f in stats["failed"][:10]:
            print(f"    {f['path']}: {f['error']}")
    print()


if __name__ == "__main__":
    main()
