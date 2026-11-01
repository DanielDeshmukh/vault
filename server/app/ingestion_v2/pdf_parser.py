"""Labour-code PDF -> Block list.

pymupdf4llm first (keeps layout / tables), pdfplumber fallback. Repeating
gazette page furniture (running heads, act footers, bare page numbers) is
stripped BEFORE heading detection so it can never open a section, statute
section starts (``N. Title``) are promoted to headings with their marginal
title attached; then the shared markdown block splitter runs.
"""
from __future__ import annotations

import re
from pathlib import Path

from .blocks import Block, ParsedDoc
from .md_parser import blocks_from_markdown

_SOURCE_TYPE = "pdf"

# --- page furniture (stripped before any heading detection) ------------------
_GAZETTE_HEAD = re.compile(r"GAZETTE OF INDIA", re.I)
_PART_HEAD = re.compile(r"^\[?\s*PART\s+[IVXLC]+[\]\u2014-]")
_ACT_SEC_MARK = re.compile(r"^SEC\.\s*\d+\]\s*$")
_PAGE_NUMBER = re.compile(r"^[\s\u2013\u2014-]*\d{1,3}[\s\u2013\u2014-]*$")
_ACT_FOOTER = re.compile(r"^\d+\s+OF\s+\d{4}$", re.I)

_FURNITURE = (_GAZETTE_HEAD, _PART_HEAD, _ACT_SEC_MARK, _PAGE_NUMBER, _ACT_FOOTER)

# --- statute section starts --------------------------------------------------
# Paragraph form from pymupdf4llm: "**5.** No employer shall ..." or "5. Title".
_SECTION_P = re.compile(r"^(?:\*\*)?(\d{1,2})\.(?:\*\*)?\s+(\S.*)$")
# Marginal title lines: short noun phrases ending in a full stop. Clause
# openers ("Provided that ...", "( 2 ) ...") are NOT titles.
_TITLE_LINE = re.compile(r"^[A-Z][^.]{4,89}\.$")
_NOT_TITLE = re.compile(
    r"^(Provided|Notwithstanding|Whereas|Where|If|The|Every|No|Any|For|When|An|In|"
    r"Subject|Save|Except|Nothing|While|Unless|Under|During|Upon|After|Before|Not|"
    r"Such|Each|Both|Hence|According|Complying)"
)
_MAX_TITLE_WORDS = 16
_TITLE_SCAN = 4  # non-empty lines to scan around a section start


def _is_title(s: str) -> bool:
    s = s.strip()
    if not _TITLE_LINE.match(s):
        return False
    if _NOT_TITLE.match(s):
        return False
    if len(s.split()) > _MAX_TITLE_WORDS:
        return False
    return bool(re.search(r"[A-Za-z]{3}", s))


def _strip_furniture(md: str) -> str:
    """Drop repeating page headers/footers BEFORE heading detection.

    Page furniture must never become a heading or land in chunk bodies:
    running gazette heads, ``SEC. N]``/``[PART II`` header fragments, bare
    page-number lines (``- 7 -``, ``12``), act footers (``4 OF 2019``).
    """
    out: list[str] = []
    for line in md.splitlines():
        stripped = re.sub(r"\s+", " ", line).strip()
        if stripped and any(rx.search(stripped) for rx in _FURNITURE):
            continue
        out.append(line)
    return "\n".join(out)


def _promote_sections(md: str) -> str:
    """Promote ``N.`` section-start paragraphs to headings, attaching the
    marginal title line that sits just before or after the start. Lines whose
    title cannot be found are left as prose (an untitled ``## 5.`` would be a
    letterless heading, which the chunker drops anyway)."""
    lines = md.splitlines()
    used: set[int] = set()

    def non_empty_from(i: int, step: int) -> list[int]:
        found: list[int] = []
        idx = i + step
        while 0 <= idx < len(lines) and len(found) < _TITLE_SCAN:
            if lines[idx].strip():
                found.append(idx)
            idx += step
        return found

    out: list[str] = []
    for i, line in enumerate(lines):
        if i in used:
            continue
        stripped = line.strip()
        m = _SECTION_P.match(stripped)
        if not m or stripped.startswith("#"):
            out.append(line)
            continue
        num, body = m.group(1), m.group(2)
        title_idx = None
        for j in non_empty_from(i, -1):  # nearest non-empty lines before
            if lines[j].strip().startswith("#"):
                break  # chapter heading: the title is not above it
            if j in used:
                continue
            if _is_title(lines[j]):
                title_idx = j
                break
        if title_idx is None:
            for j in non_empty_from(i, 1):  # then scan forward
                nxt = lines[j].strip()
                if _SECTION_P.match(nxt) or nxt.startswith("#"):
                    break  # next section/chapter starts: title is not there
                if j in used:
                    continue
                if _is_title(lines[j]):
                    title_idx = j
                    break
        if title_idx is None:
            out.append(line)  # no marginal title: keep as prose
            continue
        used.add(title_idx)
        title = lines[title_idx].strip().rstrip(".").strip()
        if out and out[-1].strip():
            out.append("")
        out.append(f"## {num}. {title}")
        out.append("")
        out.append(body)
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

    md = _strip_furniture(md.strip())
    md = _promote_sections(md)
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
