"""SEC 10-K .htm -> Block list via DOM cleanup, then markdown normalization.

- Drops script/style/iframe, unwraps ``ix:*`` inline-XBRL tags, removes
  display:none / aria-hidden noise.
- Promotes short ``Item N.`` body paragraphs to real ``<h2>`` headings in the
  DOM (parser-level edit, not text regex). Table-internal markers (the
  table-of-contents rows) are ignored; only the leaf-most match per header is
  promoted so div+span pairs yield a single heading.
- Then markdownifies and reuses the shared markdown block splitter.
"""
from __future__ import annotations

import re
import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
from markdownify import markdownify

from .blocks import Block, ParsedDoc
from .htmlconv import _cleanup_soup
from .md_parser import blocks_from_markdown

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_SOURCE_TYPE = "sec_htm"

_ITEM_RE = re.compile(r"^Item\s+\d{1,2}[A-B]?\.?(?:\s+\S.*)?$", re.I)


def _is_item_header(tag: Tag) -> bool:
    text = " ".join(tag.get_text(" ", strip=True).split())
    return bool(5 <= len(text) <= 120 and _ITEM_RE.match(text))


def _promote_items(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["p", "div", "span", "b", "strong", "em", "font"])):
        if not isinstance(tag, Tag) or tag.name == "html" or tag.name == "body":
            continue
        if not _is_item_header(tag):
            continue
        if tag.find_parent("table") is not None:
            continue  # table-of-contents rows, not body headers
        if any(_is_item_header(d) for d in tag.find_all(True)):
            continue  # promote only the leaf-most header element
        heading = soup.new_tag("h2")
        heading.string = " ".join(tag.get_text(" ", strip=True).split())
        tag.replace_with(heading)


def parse_sec_htm(html: str, doc_title: str = "") -> ParsedDoc:
    warnings: list[str] = []
    soup = BeautifulSoup(html, "lxml")
    _cleanup_soup(soup)
    _promote_items(soup)

    body = soup.body or soup
    md = markdownify(str(body), heading_style="ATX").strip()
    md = re.sub(r"\n{3,}", "\n\n", md)
    blocks: list[Block] = blocks_from_markdown(md)

    if not doc_title:
        for block in blocks:
            if block.kind == "heading" and block.plain:
                doc_title = block.plain.strip()
                break
    return ParsedDoc(_SOURCE_TYPE, doc_title, {}, blocks, warnings)
