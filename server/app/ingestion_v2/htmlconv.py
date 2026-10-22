"""HTML fragment -> markdown conversion (BeautifulSoup + markdownify).

Plan: mask autolinks / emails / inline code / unknown ``<PLACEHOLDER>`` tags
with sentinels BEFORE BeautifulSoup parsing (so they survive untouched), drop
``script``/``style``/``iframe`` blocks, unwrap ``ix:*`` SEC tags, turn
``details``/``summary`` into heading+body, ``<br>`` into newlines, and
``<table>`` into canonical GFM. No regex is used to strip document structure
— sentinels are plain token substitution on delimited runs.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from bs4._typing import _StrainableAttributes
from markdownify import markdownify

_SENT_PREFIX = "\x02ing:"
_SENT_SUFFIX = "\x02"

_BLOCKED = {"script", "style", "iframe", "object", "embed", "noscript"}

# Tags whose *names* are known HTML — anything else capitalized-ish is a
# placeholder like <EBA name> or <FOIA@gitlab.com> and must be protected.
_KNOWN_TAGS = {
    "a", "abbr", "address", "article", "aside", "audio", "b", "bdi", "bdo",
    "blockquote", "br", "button", "caption", "center", "cite", "code", "col",
    "colgroup", "data", "datalist", "dd", "del", "details", "dfn", "div",
    "dl", "dt", "em", "figcaption", "figure", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "i", "img", "input",
    "ins", "kbd", "label", "legend", "li", "main", "mark", "meter", "nav",
    "ol", "optgroup", "option", "output", "p", "picture", "pre", "progress",
    "q", "rp", "rt", "ruby", "s", "samp", "section", "select", "small",
    "source", "span", "strong", "sub", "summary", "sup", "svg", "table",
    "tbody", "td", "template", "textarea", "tfoot", "th", "thead", "time",
    "title", "tr", "track", "u", "ul", "var", "video", "wbr",
}

# Inline-code runs, autolinks, emails, and capitalized placeholder tags.
_MASK_PATTERNS = [
    re.compile(r"`[^`\n]+`"),
    re.compile(r"<https?://[^>\s]+>"),
    re.compile(r"<[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}>"),
    re.compile(r"</?[A-Z][A-Z0-9_]*(?:[ -][A-Za-z0-9_]+)+>"),  # <EBA name>
    re.compile(r"</?[A-Z][A-Z0-9_]{2,}>"),  # <FOIA>, <XYZ123>
]

_TAG_NAME_RE = re.compile(r"</?\s*([A-Za-z][\w:-]*)")


def _mask(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def stash(match: re.Match) -> str:
        saved.append(match.group(0))
        return f"{_SENT_PREFIX}{len(saved) - 1}{_SENT_SUFFIX}"

    out = text
    for pattern in _MASK_PATTERNS:
        out = pattern.sub(stash, out)
    return out, saved


def _restore(text: str, saved: list[str]) -> str:
    def restore(match: re.Match) -> str:
        idx = int(match.group(1))
        return saved[idx] if 0 <= idx < len(saved) else match.group(0)

    return re.sub(r"\x02ing:(\d+)\x02", restore, text)


def _cleanup_soup(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(lambda t: isinstance(t, Tag) and t.name in _BLOCKED):
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in soup.find_all(
        lambda t: bool(isinstance(t, Tag) and t.name and t.name.split(":")[0] == "ix")
    ):
        tag.unwrap()
    style_attrs: _StrainableAttributes = {
        "style": re.compile(r"display\s*:\s*none", re.I),
    }
    for tag in soup.find_all(name=None, attrs=style_attrs):
        tag.decompose()
    aria_attrs: _StrainableAttributes = {"aria-hidden": "true"}
    for tag in soup.find_all(name=None, attrs=aria_attrs):
        if tag.name not in _KNOWN_TAGS or tag.name in ("span", "div", "i"):
            tag.decompose()


def _details_to_md(soup: BeautifulSoup) -> None:
    for details in soup.find_all("details"):
        summary = details.find("summary")
        head = summary.get_text(" ", strip=True) if summary else ""
        if summary:
            summary.decompose()
        body_md = markdownify(
            str(details.decode_contents()), heading_style="ATX"
        ).strip()
        pieces = [f"**{head}**"] if head else []
        if body_md:
            pieces.append(body_md)
        details.replace_with(NavigableString("\n\n" + "\n\n".join(pieces) + "\n\n"))


def _tables_to_gfm(soup: BeautifulSoup) -> None:
    for table in soup.find_all("table"):
        gfm = markdownify(str(table), heading_style="ATX").strip()
        table.replace_with(NavigableString("\n\n" + gfm + "\n\n"))


def convert_fragment(html: str) -> str:
    """Convert an HTML fragment (paragraph content, html_block, etc.) to markdown."""
    if not html or not html.strip():
        return ""
    if "<" not in html:
        return html

    masked, saved = _mask(html)
    soup = BeautifulSoup(masked, "html.parser")
    _cleanup_soup(soup)
    _details_to_md(soup)
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))
    _tables_to_gfm(soup)

    md = markdownify(str(soup), heading_style="ATX")
    md = _restore(md, saved)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()
