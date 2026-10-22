"""Offline pipeline: one corpus file -> ChunkRecords (schema D) + drop log.

No database, no Pinecone, no embedding calls — those belong to Phase 2+.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .blocks import ParsedDoc
from .chunker import Draft, chunk_doc
from .md_parser import parse_markdown
from .pdf_parser import parse_labour_pdf
from .records import ChunkRecord, DropRecord, build_chunk_id, content_hash
from .sec_parser import parse_sec_htm
from .text_parser import parse_cuad_txt
from .tokens import count_tokens

_SEC_FILE_RE = re.compile(r"^([a-z0-9_]+)_(10-?k|10-?q|8-?k)_(\d{4}-\d{2}-\d{2})\.htm$", re.I)


def detect_source_type(rel_path: str) -> str:
    lowered = rel_path.replace("\\", "/").lower()
    if "/cuad/" in f"/{lowered}" and lowered.endswith(".txt"):
        return "cuad_txt"
    if lowered.endswith(".htm") and ("/sec_10k/" in f"/{lowered}" or "10-k" in lowered or "10k" in lowered):
        return "sec_htm"
    if lowered.endswith(".htm"):
        return "sec_htm"
    if lowered.endswith(".pdf"):
        return "pdf"
    return "md"


def source_title(rel_path: str, parsed: ParsedDoc, raw_text: str = "") -> str:
    if parsed.frontmatter.get("title"):
        return str(parsed.frontmatter["title"]).strip()
    name = Path(rel_path).name
    sec = _SEC_FILE_RE.match(name)
    if sec:
        company = sec.group(1).replace("_", " ").title()
        return f"{company} {sec.group(2).upper().replace('-', '-')} ({sec.group(3)})"
    if parsed.doc_title:
        return parsed.doc_title.strip()
    for line in (raw_text or "").splitlines():
        line = line.strip(" *#")
        if line and len(line) <= 120:
            return line
    return name


def parse_file(abs_path: str | Path, rel_path: str = "") -> ParsedDoc:
    path = Path(abs_path)
    rel = rel_path or path.name
    source_type = detect_source_type(rel)
    if source_type == "cuad_txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        return parse_cuad_txt(text)
    if source_type == "sec_htm":
        html = path.read_text(encoding="utf-8", errors="replace")
        return parse_sec_htm(html)
    if source_type == "pdf":
        return parse_labour_pdf(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_markdown(text, source_path=rel)


def build_records(
    drafts: list[Draft],
    *,
    doc_id: str,
    source_path: str,
    source_type: str,
    doc_title: str,
    department: str,
    classification: str,
    allowed_roles: list[str],
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for index, draft in enumerate(drafts):
        records.append(
            ChunkRecord(
                chunk_id=build_chunk_id(doc_id, index),
                doc_id=doc_id,
                chunk_index=index,
                source_path=source_path,
                source_type=source_type,
                doc_title=doc_title,
                heading_path=draft.heading_path,
                block_type=draft.block_type,
                text_md=draft.text_md,
                text_embed=_build_text_embed(doc_title, draft),
                token_count=count_tokens(draft.text_md),
                char_count=len(draft.text_md),
                content_hash=content_hash(draft.text_md),
                department=department,
                classification=classification,
                allowed_roles=list(allowed_roles),
            )
        )
    return records


def _build_text_embed(doc_title: str, draft: Draft) -> str:
    path = " > ".join(p for p in draft.heading_path if p and p != doc_title)
    head = f"{doc_title} > {path}" if path else doc_title
    if draft.plain:
        return f"{head}\n\n{draft.plain}"
    return head


def process_file(
    abs_path: str | Path,
    entry: dict,
    doc_id: str,
) -> tuple[list[ChunkRecord], list[DropRecord], dict]:
    """Parse + chunk one corpus file using manifest metadata (plan B).

    Returns (records, drops, meta). meta carries Phase-2 gate data:
    oversize atom justifications and mojibake drop counts.
    """
    rel = str(entry["path"]).replace("\\", "/")
    parsed = parse_file(abs_path, rel)
    raw_text = ""
    if parsed.source_type != "pdf":
        try:
            raw_text = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw_text = ""
    title = source_title(rel, parsed, raw_text)

    drafts, drops = chunk_doc(parsed)
    records = build_records(
        drafts,
        doc_id=doc_id,
        source_path=rel,
        source_type=parsed.source_type,
        doc_title=title,
        department=str(entry.get("department", "")),
        classification=str(entry.get("classification", "")),
        allowed_roles=list(entry.get("allowed_roles", [])),
    )
    # Guard against verbatim duplicate chunks inside one document (parser or
    # source artifacts) — embedding the same text twice wastes budget and
    # pollutes retrieval with twin hits.
    seen_hashes: set[str] = set()
    deduped: list[ChunkRecord] = []
    for record in records:
        if record.content_hash in seen_hashes:
            drops.append(DropRecord("duplicate_chunk", record.text_md[:120], record.heading_path))
            continue
        seen_hashes.add(record.content_hash)
        deduped.append(record)
    records = deduped
    meta = {
        "doc_id": doc_id,
        "source_path": rel,
        "doc_title": title,
        "oversize_atoms": [
            {
                "tokens": d.token_count,
                "justification": d.oversize_justification,
                "heading_path": d.heading_path,
                "preview": d.text_md[:100],
            }
            for d in drafts
            if d.oversize_justification
        ],
        "drop_reasons": dict(Counter(d.reason for d in drops)),
    }
    return records, drops, meta
