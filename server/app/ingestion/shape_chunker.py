"""Document-shape-aware chunker.

Replaces the old fixed-size window in ``chunker.py``. Instead of cutting text at
an arbitrary character count, this walks the document's own structure and keeps
each section intact:

* Markdown (GitLab handbook)  -> YAML frontmatter title + ATX heading sections,
  with headings inside fenced code blocks ignored.
* SEC 10-K filings            -> tag-stripped prose sectioned on the SEC-mandated
  "Item N. Title" markers, which all five filings in the corpus expose.
* Contracts (CUAD exhibits)   -> numbered clauses, "12. Heading", on a short line.
* Statutes (labour codes)     -> numbered sections, "12. (1) ...", which is how an
  Act of Parliament lays its provisions out.

A section is only split further when it breaches ``max_chunk_chars``. Splitting
then happens at paragraph boundaries, then sentence boundaries, never mid-word.

Offsets (``start_char`` / ``end_char``) are relative to the cleaned text that
this module extracts, not to the raw source bytes -- raw HTML offsets would be
meaningless once tags are removed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# Deliberately generous: the caller's record cap is ~40 KB, so stay under it.
DEFAULT_MAX_CHUNK_CHARS = 38_000

# Markdown ATX heading: 1-6 hashes, then non-empty text.
_MD_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)

# YAML frontmatter is only frontmatter when it opens the file.
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_FRONT_TITLE = re.compile(r"^title:[ \t]*(.+?)[ \t]*$", re.MULTILINE)

# A fenced code block opener/closer. Tracks state so '#' inside code is ignored.
_FENCE = re.compile(r"^[ \t]{0,3}(```|~~~)")

# SEC 10-K item heading, e.g. "Item 1A. Risk Factors" or "Item 7. Management's".
# Runs on already tag-stripped prose. In the filings we have, the marker and
# its title sit on the SAME line ("Item 1. Business") while the table of
# contents puts them on separate lines, so anchoring the title to the rest of
# the line naturally skips the TOC.
_SEC_ITEM = re.compile(
    r"\bItem[ \t]+([0-9]{1,2}[A-Z]?)[ \t]*\.[ \t]+([^\n]{2,90})",
    re.IGNORECASE,
)

# Trailing page number that can ride along with a TOC-style title.
_TITLE_TRAILING = re.compile(r"[ \t]+\d{1,4}[ \t]*$")

# Block-level closers -> newline, so paragraph structure survives tag stripping.
_BLOCK_TAGS = re.compile(
    r"(?i)</?(?:p|div|tr|td|th|li|ul|ol|table|section|article|h[1-6]|br"
    r"|blockquote|pre|hr)\b[^>]*>"
)
_TAG = re.compile(r"(?s)<[^>]+>")
_ENTITY = re.compile(r"&#x[0-9a-fA-F]+;|&#\d+;|&[a-zA-Z][a-zA-Z0-9]{1,8};")

_SENTENCE_END = re.compile(r"(?<=[.!?])[ \t]+(?=[A-Z0-9\"'(\[])")

# --- markdown artefact stripping ---------------------------------------------
#
# The stripper used to work off a bare ``<[^>]+>``, which also matched markdown
# autolinks (``<https://...>``), email autolinks and documentation placeholders
# such as ``<username>`` -- measured at 128 documents that the stripper
# triggered on and would have damaged. Those are content, not markup.
#
# The pipeline therefore masks every region that must survive byte-identical
# (fenced code, inline code, autolinks, non-HTML ``<...>``) into private-use
# sentinels, runs the HTML/Hugo pass over what is left, then restores them.
# Masking first also means the pass cannot mint a new fence out of its own
# output, which is how ``&#96;&#96;&#96;`` entities previously corrupted a page.

# Sentinel brackets live in the Unicode private-use area, so they cannot appear
# in corpus text and survive whitespace normalisation. There are two kinds:
#
#   * a FENCE sentinel is a hard barrier -- an HTML comment or ``<script>`` block
#     may never span one, or it would swallow a documented code sample;
#   * a content sentinel (inline code, autolink, placeholder) is soft -- a
#     comment is free to swallow it, because a comment is authoring metadata and
#     the whole point is to delete it. Without that distinction a comment that
#     mentions ``_index.md`` could never close.
_FENCE_SENT_L = "\ue000"
_SENT_L = "\ue002"
_SENT_R = "\ue001"
_SENT_RE = re.compile("[\ue000\ue002](\\d+)\ue001")

# Multi-line elements (comments, script/style, iframe) may legitimately span
# lines, but must stop dead at a fenced code block -- otherwise an early
# ``<!--`` swallows the next code block, or tens of thousands of characters of
# prose on its way to the next ``-->``. That defect alone cost one template 98%
# of its content and removed 42k characters from a delivery methodology page.
_NO_CROSS = r"(?:.(?!" + _FENCE_SENT_L + r"))"

# Authoring artefacts that ride along in GitLab handbook markdown.
_HUGO_BLOCK = re.compile(rf"(?s)<!--{_NO_CROSS}*?-->")

# Real HTML elements. Anything not on this list is treated as content.
_HTML_INLINE = {
    "a", "abbr", "b", "bdi", "bdo", "big", "cite", "code", "data", "del", "dfn",
    "em", "font", "i", "img", "ins", "kbd", "mark", "q", "rp", "rt", "ruby", "s",
    "samp", "small", "span", "strike", "strong", "sub", "sup", "time", "tt", "u",
    "var", "wbr",
}
# Elements whose removal should leave a line break behind.
_HTML_BLOCK = {
    "address", "article", "aside", "blockquote", "caption", "center", "col",
    "colgroup", "dd", "details", "dialog", "div", "dl", "dt", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hgroup", "hr", "html", "legend", "li", "main", "menu",
    "nav", "ol", "optgroup", "output", "p", "picture", "pre", "script",
    "section", "style", "summary", "table", "tbody", "tfoot", "thead", "tr",
    "ul",
}
# Head/document machinery: void elements with no readable content, dropped whole.
_HTML_VOID = {"base", "link", "meta"}
_HTML_NAMES = sorted(
    _HTML_INLINE | _HTML_BLOCK | _HTML_VOID | {"td", "th", "br", "iframe"}
)
_HTML_NAME_SET = frozenset(_HTML_NAMES)

# Open/close tag. Group 1 is "/" for a closing tag, group 2 the element name.
_HTML_TAG = re.compile(r"(?i)<(/?)(" + "|".join(_HTML_NAMES) + r")\b[^>]*>")

# Whole-element removal: these tags are pure machinery, their content is code.
_SCRIPT_STYLE = re.compile(rf"(?is)<(script|style)\b[^>]*>{_NO_CROSS}*?</\1\s*>")
# ``[^<]*?`` keeps the element from swallowing the rest of the document when a
# page ships an unclosed tag.
_IFRAME = re.compile(
    rf"(?is)<iframe\b[^>]*>{_NO_CROSS}*?</iframe\s*>|<iframe\b[^>]*/?>"
)
_VOID_ELEMENT = re.compile(rf"(?i)<(?:{'|'.join(sorted(_HTML_VOID))})\b[^>]*/?>")
_IMG = re.compile(r"(?i)<img\b([^>]*)/?>")
_SRC = re.compile(r"""src\s*=\s*["']([^"']+)["']""", re.I)
_ALT = re.compile(r"""alt\s*=\s*["']([^"']+)["']""", re.I)

# Inline code spans. Runs after fence masking, so only spans outside fences.
_INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)

# Markdown autolinks and bare email autolinks -- these are content.
_AUTO_LINK = re.compile(
    r"<(?:(?:https?|ftp)://|mailto:)[^<>\s]+>"
    r"|<[^<>\s@]+@[^<>\s@]+\.[^<>\s@]+>",
    re.I,
)
_ANY_ANGLE = re.compile(r"<[^>\n]*>")

# Hugo shortcodes. Group 1 is the delimiter (``<`` or ``%``), group 2 the body.
# ``[^{}]*`` is safe because a shortcode cannot nest a brace.
_HUGO_SHORTCODE = re.compile(r"\{\{([<%])\s*([^{}]*?)\s*[>%]\}\}")
# Attributes whose value is itself prose worth keeping.
_HUGO_KEEP_ATTRS = ("header", "title", "summary", "name")
# Shortcodes whose only argument is a human-readable label, so substituting it
# preserves meaning. Slugs, IDs and video IDs are deliberately absent -- they
# would inject meaningless tokens into an embedding.
_HUGO_KEEP_ARG = frozenset(
    {"member-by-name", "member-by-gitlab", "team-by-name", "label", "notice"}
)
_HUGO_VIDEO = frozenset({"youtube", "vimeo"})

# Cheap pre-check. Autolinks and placeholders alone are left alone, so they do
# not need to trigger a pass at all.
_ARTEFACT_GATE = re.compile(
    r"\{\{[<%]|<!--|</?(?:" + "|".join(_HTML_NAMES) + r")\b"
    r"|\[\s*insert\b",
    re.I,
)

# Authoring placeholders such as "[insert issue number here]". They are removed
# because a retriever would otherwise be able to answer a factual question with
# the instruction itself. Bracketed text that does not begin with "insert" --
# footnote references, [Add-On], [added to the website repository] -- is left
# untouched, so this cannot eat real prose. Runs inside fences because the pass
# masks fenced code first.
_INSERT_PLACEHOLDER = re.compile(r"\[\s*insert\b[^\]\n]{0,70}\]", re.I)

# Indented (4-space) code is deliberately NOT detected: nested list content is
# also indented four spaces, so a detector would mask real prose.

# A numbered clause heading: "12. DEFINITIONS." on a line of its own. The line
# length cap is the filter -- prose wrapped into a clause starts mid-sentence and
# runs far past it, while a real heading stays short. Measured over all 510 CUAD
# contracts: 426 files have at least one, median 11 per file.
_CONTRACT_CLAUSE = re.compile(r"^[ \t]*\d{1,3}[ \t]*\.[ \t]+\S[^\n]{0,110}", re.MULTILINE)

# A numbered provision of an Act: "12. (1) Where..." or "12. The Board shall...".
# Anchored to line start and to an upper-case or opening paren after the number
# so gazette page furniture ("2 THE GAZETTE OF INDIA") cannot open a section.
_STATUTE_SECTION = re.compile(r"^[ \t]*\d{1,3}[ \t]*\.[ \t]+(?=[A-Z(])[^\n]{0,110}", re.MULTILINE)

# Boundaries closer together than this are merged away. Without a floor the
# clause regex produces micro-sections (a heading, then one sentence) and the
# index fills with near-duplicate one-paragraph vectors.
MIN_SECTION_CHARS = 1_200

PARAGRAPH_BREAK = "\n\n"


@dataclass(frozen=True)
class Section:
    """One structural section of a document."""

    title: str | None
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class ShapedChunk:
    """One embeddable unit. ``citation`` is ``path#heading``.

    ``part``/``parts`` describe splitting *within* a section: a section kept
    whole is 1/1, a section split over ``max_chunk_chars`` reports N pieces.
    ``section_index`` is the section's 0-based ordinal in the document and
    ``section_char_start``/``section_char_end`` its span in the cleaned text,
    so any fragment maps back to its parent without re-parsing the source.
    """

    text: str
    citation: str
    section_title: str | None
    start_char: int
    end_char: int
    part: int = 1
    parts: int = 1
    section_index: int = 0
    section_char_start: int = 0
    section_char_end: int = 0


@dataclass
class ChunkingReport:
    """What happened to one document -- useful for spotting silent failures."""

    source_path: str
    kind: str
    sections: int = 0
    chunks: int = 0
    dropped_empty_sections: int = 0
    overflow_splits: int = 0
    warnings: list[str] = field(default_factory=list)


def _exact_bounds(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Strip ``text[start:end]`` and return its exact post-strip bounds.

    Section text is stripped, so recording the raw span would leave the
    parent's ``end_char`` past the end of the text it actually describes.
    """
    raw = text[start:end]
    stripped = raw.strip()
    if not stripped:
        return "", start, start
    lead = len(raw) - len(raw.lstrip())
    exact_start = start + lead
    return stripped, exact_start, exact_start + len(stripped)


def _strip_markdown_frontmatter(text: str) -> tuple[str, str | None, int]:
    """Return (body, title, offset_of_body_in_original)."""
    m = _FRONTMATTER.match(text)
    if not m:
        return text, None, 0
    title_m = _FRONT_TITLE.search(m.group(1))
    title = None
    if title_m:
        title = title_m.group(1).strip().strip("\"'")
    return text[m.end() :], title, m.end()


def _iter_markdown_sections(body: str) -> Iterable[Section]:
    """Split markdown on ATX headings, ignoring headings inside code fences.

    Every line is scanned -- fences must be tracked on all lines, not just
    heading-looking ones, or a ``# comment`` inside a bash block would open a
    section. Each heading opens a section that runs until the next heading of
    any level. A heading immediately followed by another heading yields an
    empty section, which the caller drops.
    """
    in_fence = False
    boundaries: list[tuple[int, int, str | None]] = []  # (start, level, title)

    pos = 0
    for line in body.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            m = _MD_HEADING.match(line)
            if m:
                boundaries.append((pos, len(m.group(1)), m.group(2).strip()))
        pos += len(line) + 1

    if not boundaries:
        text, s, e = _exact_bounds(body, 0, len(body))
        if text:
            yield Section(None, text, s, e)
        return

    prologue, p_start, p_end = _exact_bounds(body, 0, boundaries[0][0])
    if prologue:
        yield Section(None, prologue, p_start, p_end)

    for i, (start, _level, title) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(body)
        text, x_start, x_end = _exact_bounds(body, start, end)
        if not text:
            continue
        # Drop the heading line itself. If nothing is left, this is a bare
        # parent heading ("## Title" immediately followed by "### Sub"), which
        # carries no retrievable content -- its title is already the child's.
        rest = text.split("\n", 1)
        if len(rest) < 2 or not rest[1].strip():
            continue
        yield Section(title, text, x_start, x_end)


def _html_to_prose(html: str) -> str:
    """Strip an SEC inline-XBRL filing down to readable, paragraph-preserving prose."""
    import html as _html

    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    # Block boundaries become newlines *before* tags are removed.
    t = _BLOCK_TAGS.sub("\n", t)
    t = _TAG.sub(" ", t)
    t = _ENTITY.sub(lambda m: _html.unescape(m.group(0)), t)
    t = t.replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _looks_like_html(angle: str) -> bool:
    """True for ``<td>`` / ``</div>``; False for ``<username>`` and friends."""
    m = re.match(r"</?([a-zA-Z][a-zA-Z0-9]*)\b", angle)
    return m is not None and m.group(1).lower() in _HTML_NAME_SET


def _mask_regions(text: str) -> tuple[str, list[str]] | None:
    """Replace every must-survive region with a sentinel; ``None`` if unsafe.

    Regions are masked, never rewritten in place, so the substitution pass
    cannot see -- and therefore cannot damage -- fenced code, inline code,
    autolinks or placeholders.
    """
    if _SENT_L in text or _FENCE_SENT_L in text:
        return None

    n = len(text)
    lines = text.split("\n")

    # 1) fenced code blocks, tracked line by line.
    in_fence = [False] * n
    in_fence_state = False
    pos = 0
    for ln in lines:
        ends = pos + len(ln)
        if _FENCE.match(ln) or in_fence_state:
            for k in range(pos, min(ends, n)):
                in_fence[k] = True
        if _FENCE.match(ln):
            in_fence_state = not in_fence_state
        pos = ends + 1

    # 2) inline code spans, only outside fences.
    never = list(in_fence)
    for m in _INLINE_CODE.finditer(text):
        if in_fence[m.start()]:
            continue
        for k in range(m.start(), m.end()):
            never[k] = True

    # 3) Hugo shortcodes sit *outside* fences but contain a bare ``<...>`` that
    # must not be mistaken for a placeholder and protected.
    hugo_spans = [
        m.span()
        for m in _HUGO_SHORTCODE.finditer(text)
        if not never[m.start()]
    ]
    hi = 0

    def _inside_hugo(pos: int) -> bool:
        nonlocal hi
        while hi < len(hugo_spans) and hugo_spans[hi][1] <= pos:
            hi += 1
        return hi < len(hugo_spans) and hugo_spans[hi][0] <= pos < hugo_spans[hi][1]

    # 4) autolinks, emails and any ``<...>`` that is not a real HTML element.
    for m in _ANY_ANGLE.finditer(text):
        if never[m.start()]:
            continue
        angle = m.group(0)
        # Comments and shortcodes stay visible: they are content to *remove*,
        # not to protect.
        if angle.startswith("<!--") or _inside_hugo(m.start()):
            continue
        if _AUTO_LINK.match(angle) or not _looks_like_html(angle):
            for k in range(m.start(), m.end()):
                never[k] = True

    regions: list[str] = []
    out: list[str] = []
    k = 0
    while k < n:
        if never[k]:
            j = k
            while j < n and never[j]:
                j += 1
            regions.append(text[k:j])
            # A run that contains a fence gets the hard barrier; anything else
            # gets the soft one so comments can still be deleted wholesale.
            left = _FENCE_SENT_L if any(in_fence[i] for i in range(k, j)) else _SENT_L
            out.append(f"{left}{len(regions) - 1}{_SENT_R}")
            k = j
        else:
            out.append(text[k])
            k += 1
    return "".join(out), regions


def _hugo_repl(m: re.Match) -> str:
    """Drop a shortcode, but keep any argument that is prose in its own right."""
    body = m.group(2).strip()
    if not body or body.startswith("/"):
        return "\n"

    name_m = re.match(r"([a-zA-Z0-9_:-]+)", body)
    if not name_m:
        return "\n"
    name = name_m.group(1).lower()
    if name == "include":
        # The payload lives in another file and Hugo is not running here, so
        # there is nothing to expand into.
        return "\n"

    for attr in _HUGO_KEEP_ATTRS:
        am = re.search(rf'{attr}\s*=\s*"([^"]*)"', body, re.I) or re.search(
            rf"{attr}\s*=\s*'([^']*)'", body, re.I
        )
        if am and am.group(1).strip():
            return am.group(1).strip()

    qm = re.search(r'"([^"]+)"', body[name_m.end() :])
    if qm and name in _HUGO_KEEP_ARG:
        return qm.group(1).strip()
    if qm and name in _HUGO_VIDEO:
        return "[video]"
    return "\n"


def _iframe_repl(m: re.Match) -> str:
    """Drop the element; keep the URL so an embedded talk stays findable."""
    sm = _SRC.search(m.group(0))
    return f" {sm.group(1).strip()} " if sm else " "


def _img_repl(m: re.Match) -> str:
    am = _ALT.search(m.group(0))
    return f" {am.group(1).strip()} " if am else " "


# Cell boundaries become pipe separators and row/list boundaries become line
# breaks, so a table stays readable to retrieval instead of collapsing into a
# single run-on paragraph.
_TD_TH = frozenset({"td", "th"})
_ROW_LI = frozenset({"tr", "li"})


def _html_tag_repl(m: re.Match) -> str:
    closing = m.group(1) == "/"
    name = m.group(2).lower()
    if name in _TD_TH:
        return " | " if closing else " "
    if name in _ROW_LI:
        return "\n" if closing else ""
    if name == "br":
        return "\n"
    if name in _HTML_BLOCK:
        return "\n"
    return " "


def _clean_masked(t: str) -> str:
    t = _HUGO_BLOCK.sub(" ", t)
    t = _SCRIPT_STYLE.sub(" ", t)
    t = _VOID_ELEMENT.sub(" ", t)
    t = _IFRAME.sub(_iframe_repl, t)
    t = _IMG.sub(_img_repl, t)
    t = _HUGO_SHORTCODE.sub(_hugo_repl, t)
    t = _HTML_TAG.sub(_html_tag_repl, t)
    t = _INSERT_PLACEHOLDER.sub("", t)
    t = t.replace("\xa0", " ")
    # Tidy only what the pass disturbed. Leading indentation is load-bearing in
    # markdown -- list nesting depends on it -- so it is left alone.
    t = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"(?m)^[ \t]+$", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip("\n")


def _strip_markdown_artifacts(text: str) -> str:
    """Strip Hugo shortcodes, HTML comments and HTML tags from markdown.

    Handbooks quote HTML and Hugo in code samples on purpose; fenced code,
    inline code, autolinks and placeholders are masked first and restored
    byte-identical afterwards.
    """
    if not _ARTEFACT_GATE.search(text):
        return text

    masked = _mask_regions(text)
    if masked is None:
        # A private-use sentinel already appears in the source; refuse to guess.
        return text
    body, regions = masked
    body = _clean_masked(body)
    return _SENT_RE.sub(lambda m: regions[int(m.group(1))], body)


def _iter_sec_sections(prose: str) -> Iterable[Section]:
    """Split tag-stripped 10-K prose on the SEC-mandated Item markers."""
    raw = list(_SEC_ITEM.finditer(prose))
    if not raw:
        text, s, e = _exact_bounds(prose, 0, len(prose))
        if text:
            yield Section(None, text, s, e)
        return

    # Some filings echo every Item in a same-line table of contents. The body
    # always follows the TOC, so keep the last match per item number.
    last_by_item: dict[str, re.Match] = {}
    for m in raw:
        last_by_item[m.group(1).upper()] = m
    matches = sorted(last_by_item.values(), key=lambda m: m.start())

    prologue, p_start, p_end = _exact_bounds(prose, 0, matches[0].start())
    if prologue:
        yield Section(None, prologue, p_start, p_end)

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prose)
        title = _clean_sec_title(m.group(1), m.group(2))
        text, x_start, x_end = _exact_bounds(prose, m.start(), end)
        if not text:
            continue
        yield Section(title, text, x_start, x_end)


def _clean_sec_title(num: str, raw_title: str) -> str:
    """Normalise an Item title: collapse whitespace, drop page numbers."""
    t = re.sub(r"[ \t]+", " ", raw_title).strip()
    t = _TITLE_TRAILING.sub("", t)
    t = t.strip(" .,:;")
    return f"Item {num.upper()}. {t}" if t else f"Item {num.upper()}"


def _clip_title(raw: str, limit: int = 90) -> str:
    """Shorten a matched heading line to something citable."""
    t = re.sub(r"[ \t]+", " ", raw).strip()
    t = t.strip(" .,:;")
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "\u2026"


def _iter_structured_sections(
    body: str,
    heading_re: re.Pattern[str],
    min_chars: int = MIN_SECTION_CHARS,
) -> Iterable[Section]:
    """Split ``body`` on ``heading_re``, keeping every section at least ``min_chars``.

    Shared by the contract and statute shapes, which differ only in which
    marker opens a section. Boundaries are dropped when they fall closer than
    ``min_chars`` to the previous *kept* boundary, so a false positive (a wrapped
    prose line that happens to start with ``12.``) cannot dice a clause into
    one-paragraph fragments. Offsets stay exact: sections tile ``body`` and each
    one is passed through :func:`_exact_bounds`.
    """
    bounds: list[tuple[int, str | None]] = [
        (m.start(), _clip_title(m.group(0))) for m in heading_re.finditer(body)
    ]
    if not bounds:
        text, s, e = _exact_bounds(body, 0, len(body))
        if text:
            yield Section(None, text, s, e)
        return

    kept = [bounds[0]]
    for b in bounds[1:]:
        if b[0] - kept[-1][0] >= min_chars:
            kept.append(b)

    prologue, p_start, p_end = _exact_bounds(body, 0, kept[0][0])
    if prologue:
        yield Section(None, prologue, p_start, p_end)

    for i, (start, title) in enumerate(kept):
        end = kept[i + 1][0] if i + 1 < len(kept) else len(body)
        text, x_start, x_end = _exact_bounds(body, start, end)
        if text:
            yield Section(title, text, x_start, x_end)


def _split_oversized(text: str, limit: int, overlap: int) -> list[tuple[str, int, int]]:
    """Split ``text`` over ``limit`` chars at paragraph, then sentence, boundaries.

    Returns (piece, rel_start, rel_end) triples. Never splits mid-word unless a
    single word alone exceeds ``limit`` (pathological case).
    """
    if len(text) <= limit:
        return [(text, 0, len(text))]

    # Pack whole paragraphs greedily. Ranges are tracked separately from the
    # scan cursor so they tile the parent span exactly: the cursor skips
    # inter-piece whitespace (which is not worth keeping in ``text``), but each
    # piece's range runs from the previous boundary to this one. That keeps
    # text[parent_start:parent_end] an exact reconstruction of the section.
    pieces: list[tuple[str, int, int]] = []
    cursor = 0
    boundary = 0
    while cursor < len(text):
        if len(text) - cursor <= limit:
            piece = text[cursor:].strip()
            if piece:
                pieces.append((piece, boundary, len(text)))
            break
        window_end = cursor + limit
        # Prefer a paragraph break inside the window.
        brk = text.rfind(PARAGRAPH_BREAK, cursor + limit // 2, window_end)
        if brk == -1 or brk <= cursor:
            # No paragraph break -- fall back to a sentence boundary.
            brk = -1
            for sm in _SENTENCE_END.finditer(text, cursor + limit // 2, window_end):
                brk = sm.start()
            if brk == -1 or brk <= cursor:
                # Last resort: split on any whitespace, else hard cut.
                brk = text.rfind(" ", cursor + limit // 2, window_end)
                if brk == -1 or brk <= cursor:
                    brk = window_end
        piece = text[cursor:brk].strip()
        if piece:
            pieces.append((piece, boundary, brk))
            boundary = brk
        cursor = brk
        while cursor < len(text) and text[cursor] in " \n":
            cursor += 1

    # Whitespace-only tail: extend the last piece so the span reaches the end.
    if pieces and pieces[-1][2] < len(text) and not text[pieces[-1][2] :].strip():
        piece, start, _ = pieces[-1]
        pieces[-1] = (piece, start, len(text))

    # Optional character overlap between consecutive pieces.
    if overlap > 0 and len(pieces) > 1:
        with_ov: list[tuple[str, int, int]] = []
        for i, (piece, s, e) in enumerate(pieces):
            if i > 0:
                head_start = max(0, s - overlap)
                piece = text[head_start:e].strip()
                s = head_start
            with_ov.append((piece, s, e))
        pieces = with_ov

    return pieces


class ShapeChunker:
    """Chunk a document by walking its own structure."""

    def __init__(
        self,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        overlap_chars: int = 0,
    ):
        if max_chunk_chars <= 0:
            raise ValueError("max_chunk_chars must be positive")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must be non-negative")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    # -- public API ---------------------------------------------------------

    def chunk_markdown(
        self, text: str, source_path: str, source_title: str | None = None
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        body, fm_title, _offset = _strip_markdown_frontmatter(text)
        # Offsets must be measured against the same string ``cleaned_content``
        # stores, so artefact stripping happens here as well as there.
        body = _strip_markdown_artifacts(body)
        title = source_title or fm_title
        report = ChunkingReport(source_path=source_path, kind="markdown")
        sections = list(_iter_markdown_sections(body))
        return self._emit(sections, source_path, title, report)

    def chunk_sec_filing(
        self, html: str, source_path: str, source_title: str | None = None
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        prose = _html_to_prose(html)
        report = ChunkingReport(source_path=source_path, kind="sec_filing")
        if len(prose) < 200:
            report.warnings.append(
                f"only {len(prose)} chars of prose after stripping; filing may be data-only"
            )
        sections = list(_iter_sec_sections(prose))
        return self._emit(sections, source_path, source_title, report)

    def chunk_contract(
        self, text: str, source_path: str, source_title: str | None = None
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        """Chunk a CUAD contract exhibit on its numbered clauses."""
        report = ChunkingReport(source_path=source_path, kind="contract")
        if len(text.strip()) < 200:
            report.warnings.append(
                f"only {len(text.strip())} chars of text; document may be a stub"
            )
        sections = list(_iter_structured_sections(text, _CONTRACT_CLAUSE))
        return self._emit(sections, source_path, source_title, report)

    def chunk_statute(
        self, text: str, source_path: str, source_title: str | None = None
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        """Chunk an Act on its numbered provisions."""
        report = ChunkingReport(source_path=source_path, kind="statute")
        if len(text.strip()) < 200:
            report.warnings.append(
                f"only {len(text.strip())} chars of text; extraction may have failed"
            )
        sections = list(_iter_structured_sections(text, _STATUTE_SECTION))
        return self._emit(sections, source_path, source_title, report)

    def chunk(
        self, text: str, source_path: str, kind: str, source_title: str | None = None
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        if kind == "markdown":
            return self.chunk_markdown(text, source_path, source_title)
        if kind == "sec_filing":
            return self.chunk_sec_filing(text, source_path, source_title)
        if kind == "contract":
            return self.chunk_contract(text, source_path, source_title)
        if kind == "statute":
            return self.chunk_statute(text, source_path, source_title)
        raise ValueError(f"unknown document kind: {kind!r}")

    # -- internals ----------------------------------------------------------

    def _emit(
        self,
        sections: list[Section],
        source_path: str,
        doc_title: str | None,
        report: ChunkingReport,
    ) -> tuple[list[ShapedChunk], ChunkingReport]:
        chunks: list[ShapedChunk] = []
        report.sections = len(sections)

        for section_index, sec in enumerate(sections):
            pieces = _split_oversized(sec.text, self.max_chunk_chars, self.overlap_chars)
            n_pieces = len(pieces)
            if n_pieces > 1:
                report.overflow_splits += n_pieces - 1
            if sec.title is None and len(sec.text) > 10_000:
                # Untitled prologue of real size -- in a 10-K this is the XBRL
                # header + table of contents. Flagged, not dropped.
                report.warnings.append(
                    f"untitled prologue of {len(sec.text):,} chars (likely cover page/TOC)"
                )
            citation = f"{source_path}#{sec.title}" if sec.title else source_path
            for part, (piece, rel_s, rel_e) in enumerate(pieces, start=1):
                chunks.append(
                    ShapedChunk(
                        text=piece,
                        citation=citation,
                        section_title=sec.title or doc_title,
                        start_char=sec.start_char + rel_s,
                        end_char=sec.start_char + rel_e,
                        part=part,
                        parts=n_pieces,
                        section_index=section_index,
                        section_char_start=sec.start_char,
                        section_char_end=sec.end_char,
                    )
                )

        report.chunks = len(chunks)
        if not chunks:
            report.warnings.append("no chunks produced")
        return chunks, report


# ------------------------------------------------------------ source layer --
# The two offline scripts that consume this module (``build_chunks.py`` and
# ``ingest_corpus.py``) both load it by path to avoid importing the DB engine.
# Kind detection and source loading live here so they cannot drift: the text a
# chunk is offset against must be the same text ``documents.content`` stores, or
# every ``section_span_*`` points at the wrong character.

# Formats neither script can turn into text. Failing loudly beats chunking
# binary bytes as markdown and silently filling the index with replacement chars.
# ``.pdf`` is not listed: :func:`read_source_text` extracts it with pypdf.
UNSUPPORTED_EXTS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}


def detect_kind(entry: dict) -> str:
    """Pick the chunking shape from a manifest entry.

    The manifest carries no ``kind`` column, but its ``source`` is unique per
    fetch stage: ``cuad:`` for contract exhibits, a bare ``http(s)://`` URL for
    the four labour codes fetched directly, and the two original stages
    otherwise. Keying on that keeps the file extension out of the decision --
    CUAD ships the same agreement as both ``.txt`` and ``.pdf`` and both must
    land in the contract shape.
    """
    source = entry.get("source", "")
    if source.startswith("cuad:"):
        return "contract"
    if source.startswith(("http://", "https://")):
        return "statute"
    p = entry["path"].lower()
    if p.endswith((".htm", ".html")):
        return "sec_filing"
    if p.endswith(".md"):
        return "markdown"
    ext = Path(entry["path"]).suffix.lower()
    if ext in UNSUPPORTED_EXTS:
        raise ValueError(f"unsupported file type {ext!r} -- no parser (add one or skip)")
    return "markdown"


def read_source_text(path: Path, kind: str) -> str:
    """Load a source document as text, extracting PDFs page by page.

    ``kind`` is accepted so callers pass the same value they chunked with; only
    the extension decides how bytes become text.
    """
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ValueError("pypdf is required to extract PDF text; pip install pypdf") from exc
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - report, don't abort the run
        raise ValueError(f"PDF extraction failed: {type(exc).__name__}: {exc}") from exc


def cleaned_content(text: str, kind: str) -> str:
    """Return exactly the text the chunker offset against.

    ``ShapedChunk.start_char``/``end_char`` are relative to the cleaned text,
    not the raw file, so ``documents.content`` must hold the same string or the
    stored spans will not line up with it.
    """
    if kind == "sec_filing":
        return _html_to_prose(text)
    if kind == "markdown":
        return _strip_markdown_artifacts(_strip_markdown_frontmatter(text)[0])
    return text
