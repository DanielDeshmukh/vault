"""Labour-code PDF -> Block list.

pymupdf4llm first (keeps layout / tables), pdfplumber fallback. Numbered
statute section lines (``N. Title``) are promoted to headings so the chunker
can track heading paths; then the shared markdown block splitter runs.
"""
from __future__ import annotations

import re
from pathlib import Path

from .blocks import Block, ParsedDoc
from .md_parser import blocks_from_markdown

_SOURCE_TYPE = "pdf"

_SECTION_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z(\[].{3,90})$")


def _promote_sections(md: str) -> str:
    out: list[str] = []
    for line in md.splitlines():
        stripped = line.strip()
        if _SECTION_RE.match(stripped):
            out.append(f"## {stripped}")
        else:
            out.append(line)
    return "\n".join(out)


def _alphabetic_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for c in text if c.isalpha())
    return letters / len(text)


def parse_labour_pdf(path: str | Path, doc_title: str = "") -> ParsedDoc:
    warnings: list[str] = []
    md = ""
    try:
        import pymupdf4llm

        md = pymupdf4llm.to_markdown(str(path))
    except Exception as exc:
        warnings.append(f"pymupdf4llm_failed: {exc}")

    if len(md.strip()) < 500 or _alphabetic_ratio(md) < 0.3:
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                md = "\n\n".join((page.extract_text() or "") for page in pdf.pages)
        except Exception as exc:
            warnings.append(f"pdfplumber_failed: {exc}")

    md = _promote_sections(md.strip())
    blocks: list[Block] = blocks_from_markdown(md)

    if not doc_title:
        for block in blocks:
            if block.kind == "heading" and block.plain:
                doc_title = block.plain.strip()
                break
        if not doc_title:
            first = next((b.plain for b in blocks if b.plain), "")
            doc_title = first[:120]
    return ParsedDoc(_SOURCE_TYPE, doc_title, {}, blocks, warnings)
