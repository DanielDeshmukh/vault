"""Block-level structures shared by all v2 parsers (no DB/network imports)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """One structural unit of a parsed document.

    kind: heading | prose | table | code | list
    md:    display markdown for this block (text_md fragment)
    plain: plain-text form for embedding (tables linearized, markup stripped)
    level: heading level (1-6) for kind == "heading"
    """

    kind: str
    md: str
    plain: str = ""
    level: int | None = None


@dataclass
class ParsedDoc:
    source_type: str  # md | cuad_txt | sec_htm | pdf
    doc_title: str
    frontmatter: dict
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
