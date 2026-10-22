"""CUAD contract .txt -> Block list.

Structure is inferred from the text layout (legal-document line patterns):
first line = title, a BETWEEN line = parties pseudo-heading, ALLCAPS lines =
level-1 headings, ``ARTICLE``/``SECTION``/``N. Title`` lines = headings.
Blank-line separated paragraphs become prose blocks.
"""
from __future__ import annotations

import re

from .blocks import Block, ParsedDoc

_SOURCE_TYPE = "cuad_txt"

_ARTICLE_RE = re.compile(r"^(ARTICLE|Article|SECTION|Section|ART\.?|EXHIBIT|SCHEDULE)\b.{0,80}$")
_NUMBERED_RE = re.compile(r"^\d{1,2}\.\s+[A-Z(\[].{2,90}$")
_BETWEEN_RE = re.compile(r"\bbetween\b|\bby and between\b", re.I)


def _is_allcaps_heading(line: str) -> bool:
    stripped = line.strip()
    if not (4 <= len(stripped) <= 100):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) < 4:
        return False
    upper = sum(1 for c in letters if c.isupper())
    if upper / len(letters) < 0.6:
        return False
    if stripped.endswith(".") and len(stripped) > 60:
        return False
    return True


def _heading_level(line: str) -> int | None:
    stripped = line.strip()
    if _ARTICLE_RE.match(stripped):
        return 1
    if _is_allcaps_heading(stripped):
        return 1
    if _NUMBERED_RE.match(stripped) and not stripped.endswith("."):
        return 2
    if _NUMBERED_RE.match(stripped) and stripped.count(" ") <= 12:
        return 2
    return None


def parse_cuad_txt(text: str) -> ParsedDoc:
    warnings: list[str] = []
    lines = text.splitlines()

    nonempty = [(idx, line.strip()) for idx, line in enumerate(lines) if line.strip()]
    title = ""
    for _, line in nonempty[:5]:
        candidate = line.strip(" *#")
        if len(candidate) <= 120:
            title = candidate
            break
    if not title and nonempty:
        title = nonempty[0][1][:120]

    parties = ""
    for _, line in nonempty[:15]:
        if _BETWEEN_RE.search(line) and 10 <= len(line.strip()) <= 600:
            parties = line.strip()
            break

    blocks: list[Block] = []
    if title:
        blocks.append(Block("heading", f"# {title}", title, 1))
    if parties:
        blocks.append(Block("heading", f"## {parties}", parties, 2))

    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            body = "\n".join(paragraph).strip()
            if body:
                blocks.append(Block("prose", body, body))
            paragraph.clear()

    for _, raw in [(i, lines[i]) for i in range(len(lines))]:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        level = _heading_level(stripped) if len(stripped) < 110 else None
        if level is not None and len(stripped.split()) <= 14:
            flush_paragraph()
            marker = "#" * level
            blocks.append(Block("heading", f"{marker} {stripped}", stripped, level))
            continue
        paragraph.append(line.strip())
    flush_paragraph()

    return ParsedDoc(_SOURCE_TYPE, title, {}, blocks, warnings)
