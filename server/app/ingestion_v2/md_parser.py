"""Markdown -> Block list via markdown-it (GFM tables) + frontmatter.

Used directly for ``*.md`` files and reused (without frontmatter) by the
SEC/PDF parsers after they normalize their source to markdown.
"""
from __future__ import annotations

import re
from functools import lru_cache

import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from .blocks import Block, ParsedDoc
from .htmlconv import _KNOWN_TAGS, convert_fragment
from .shortcodes import preprocess

_SOURCE_TYPE = "md"
_TICKS_RE = re.compile(r"`+")


def _fence_block(info: str, code: str) -> str:
    """Emit a fence whose delimiter nothing inside ``code`` can close.

    Sources legitimately nest ``` lines inside ````…```` fences; markdown-it
    hands us the inner lines verbatim as content. Re-emitting as ``` makes
    the inner line a real closer, and our appended closer then re-opens —
    records end up with unclosed fences. Longest backtick-run in the code
    + 1 (min 3) keeps the fence atomic.
    """
    longest = max((len(m) for m in _TICKS_RE.findall(code)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{info}\n{code}\n{ticks}"

# A standalone <br> token (markdown-it hands each inline tag separately).
# convert_fragment() strips its newline result to "", so a lone <br> would
# silently vanish and jam words together (e.g. "**Jeanne Rotenberry**<br>Staff").
_BR_RE = re.compile(r"(?i)^\s*<br\s*/?>\s*$")

# Author fill-in markers ("<Contact Name>", "<username and email address>"):
# html_inline tokens shaped like a tag-with-attribute, NOT real HTML. Parsing
# them as HTML would delete them silently (source-check token loss) — keep
# them literal: backticked in text_md (a renderer can't eat them), raw in
# plain. Mirrors the gate's placeholder definition (PLACEHOLDER_RE, no "=",
# first word not a known tag).
_PLACEHOLDER_RE = re.compile(r"<[A-Za-z][^<>\n]* [^<>\n]*>")

# Inline <a href="..."> / </a> tokens: markdown-it emits them as separate
# html_inline children around the link text, so convert_fragment() on the
# bare opening tag would drop the href. Groups: 1=double-quoted, 2=single-
# quoted, 3=unquoted href value.
_A_OPEN_RE = re.compile(
    r'''(?is)^\s*<a\s[^>]*?href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>\s*$'''
)
_A_CLOSE_RE = re.compile(r"(?is)^\s*</a\s*>\s*$")


def _is_placeholder(html_text: str) -> bool:
    s = html_text.strip()
    if not _PLACEHOLDER_RE.fullmatch(s) or "=" in s:
        return False
    return s[1:].split()[0].lower() not in _KNOWN_TAGS


@lru_cache(maxsize=1)
def _md() -> MarkdownIt:
    return MarkdownIt("commonmark").enable("table")


def _inline_plain(inline: Token) -> str:
    parts: list[str] = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type == "html_inline":
            if _BR_RE.match(child.content):
                parts.append(" ")  # plain text: match softbreak handling
            elif _is_placeholder(child.content):
                parts.append(child.content)  # literal <Marker Text> for embed/rerank
            else:
                stripped = re.sub(r"<[^>]+>", "", convert_fragment(child.content))
                parts.append(stripped)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def _inline_to_md(inline: Token) -> str:
    """Serialize an inline token back to markdown, converting html_inline runs."""
    out: list[str] = []
    link_hrefs: list[str] = []
    link_starts: list[int] = []
    html_hrefs: list[str] = []
    html_starts: list[int] = []
    for child in inline.children or []:
        if child.type == "text":
            out.append(child.content)
        elif child.type == "code_inline":
            out.append(f"`{child.content}`")
        elif child.type == "softbreak":
            out.append("\n")
        elif child.type == "hardbreak":
            out.append("  \n")
        elif child.type in ("em_open", "em_close"):
            out.append("*")
        elif child.type in ("strong_open", "strong_close"):
            out.append("**")
        elif child.type == "link_open":
            link_hrefs.append(str(child.attrGet("href") or ""))
            link_starts.append(len(out))
            out.append("[")
        elif child.type == "link_close":
            href = link_hrefs.pop() if link_hrefs else ""
            start = link_starts.pop() if link_starts else max(len(out) - 1, 0)
            text = "".join(out[start + 1 :])
            del out[start:]
            if href and (text == href or href == f"mailto:{text}"):
                out.append(f"<{text}>")  # preserve original autolink form
            elif href:
                out.append(f"[{text}]({href})")
            else:
                out.append(text)
        elif child.type == "html_inline":
            if _BR_RE.match(child.content):
                # Plan: <br> becomes a newline. In table cells _escape_cell
                # turns it into a space (GFM cells are single-line); in prose
                # the newline survives as a soft break.
                out.append("\n")
            elif _is_placeholder(child.content):
                # fill-in marker: keep literal, backticked so renderers keep it
                out.append(f"`{child.content}`")
            elif _A_OPEN_RE.match(child.content):
                # markdown-it splits <a href>text</a> into 3 tokens; converting
                # the lone opening tag drops the href (source-check URL loss).
                # Mirror link_open/close: carry the href across the text run.
                m = _A_OPEN_RE.match(child.content)
                assert m is not None
                html_hrefs.append(m.group(1) or m.group(2) or m.group(3) or "")
                html_starts.append(len(out))
                out.append("[")
            elif _A_CLOSE_RE.match(child.content):
                href = html_hrefs.pop() if html_hrefs else ""
                start = html_starts.pop() if html_starts else max(len(out) - 1, 0)
                text = "".join(out[start + 1 :])
                del out[start:]
                if href and (text == href or href == f"mailto:{text}"):
                    out.append(f"<{text}>")
                elif href:
                    out.append(f"[{text}]({href})")
                else:
                    out.append(text)
            else:
                out.append(convert_fragment(child.content))
        elif child.type == "image":
            out.append(child.content or "")
    # malformed anchor with no closing tag: still preserve the href
    while html_hrefs:
        href = html_hrefs.pop()
        start = html_starts.pop()
        text = "".join(out[start + 1 :])
        del out[start:]
        out.append(f"[{text}]({href})" if href else text)
    return "".join(out)


def _escape_cell(text: str) -> str:
    return text.replace("\n", " ").replace("|", "\\|").strip()


def _collect_table(tokens: list[Token], start: int) -> tuple[str, str, int]:
    """Serialize a markdown-it table into GFM + a linearized plain form.

    The plain form (text_embed / rerank input) is built from the inline
    *plain* text of each cell -- never from the markdown serialization --
    so embed text never carries ``**``/``[t](u)`` syntax (plan section A).
    """
    headers: list[str] = []
    headers_plain: list[str] = []
    rows: list[list[str]] = []
    rows_plain: list[list[str]] = []
    i = start + 1
    in_head = False
    current_row: list[str] | None = None
    current_plain: list[str] | None = None
    while i < len(tokens) and tokens[i].type != "table_close":
        tok = tokens[i]
        if tok.type == "thead_open":
            in_head = True
        elif tok.type == "thead_close":
            in_head = False
        elif tok.type == "tr_open":
            current_row = []
            current_plain = []
        elif tok.type == "tr_close":
            if current_row is not None:
                if in_head and not headers:
                    headers = current_row
                    headers_plain = current_plain or []
                else:
                    rows.append(current_row)
                    rows_plain.append(current_plain or [])
            current_row = None
            current_plain = None
        elif tok.type in ("th_open", "td_open"):
            inline = tokens[i + 1]
            cell_md = _escape_cell(_inline_to_md(inline))
            cell_plain = _inline_plain(inline)
            if current_row is not None:
                current_row.append(cell_md)
            if current_plain is not None:
                current_plain.append(cell_plain)
            i += 1
        i += 1

    if not headers:
        headers = [f"col{j + 1}" for j in range(max((len(r) for r in rows), default=1))]
        headers_plain = list(headers)
    width = max([len(headers)] + [len(r) for r in rows])
    headers += [""] * (width - len(headers))
    headers_plain += [""] * (width - len(headers_plain))
    rows = [r + [""] * (width - len(r)) for r in rows]
    rows_plain = [r + [""] * (width - len(r)) for r in rows_plain]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    md = "\n".join(lines)

    plain_rows = [
        " | ".join(f"{h}: {v}" for h, v in zip(headers_plain, row) if v)
        for row in rows_plain
    ]
    plain = "\n".join(plain_rows)
    return md, plain, i + 1


def _collect_list(tokens: list[Token], start: int) -> tuple[str, str, int]:
    """Serialize a (possibly nested) list into markdown + plain text."""
    open_tok = tokens[start]
    ordered = open_tok.tag == "ol"
    # Watch this list's OWN open/close token TYPES (markdown-it types are
    # bullet_list_*/ordered_list_*, not ul_*/ol_*). The old tag-based strings
    # never matched, the depth-0 break never fired, and _collect_list ran to
    # the end of the stream — silently dropping every block after the first
    # list in a document.
    marker_close = "ordered_list_close" if ordered else "bullet_list_close"

    items: list[tuple[list[str], list[str]]] = []  # (md_lines, plain_parts)
    i = start + 1
    current: tuple[list[str], list[str]] | None = None
    base_number = int(open_tok.attrGet("start") or 1)

    def close_item() -> None:
        nonlocal current
        if current is not None:
            items.append(current)
            current = None

    def ensure_item() -> tuple[list[str], list[str]]:
        # Never discard content: a fence/html/table/hr/inline token with no
        # open item lands in a synthetic item instead of being dropped.
        nonlocal current
        if current is None:
            current = ([], [])
        return current

    while i < len(tokens):
        tok = tokens[i]
        if tok.type in ("bullet_list_open", "ordered_list_open"):
            # Recurse into EVERY nested list, bullet and ordered alike. The old
            # code recursed only for tag == "ol" and tracked same-type bullets
            # with depth: after a nested list closed, its last list_item_close
            # had set current = None, so the OUTER item's continuation
            # (paragraph / fence / html) hit a None guard and was silently
            # discarded -- nested-bullet docs lost indented continuations with
            # NO drop record.
            nested_md, nested_plain, i = _collect_list(tokens, i)
            if current is not None:
                for line in nested_md.splitlines():
                    current[0].append("  " + line)
                current[1].append(nested_plain)
            else:  # list open directly inside list open without item: rare
                items.append(([f"  {ln}" for ln in nested_md.splitlines()], [nested_plain]))
            continue
        elif tok.type == marker_close:
            # Nested lists are fully consumed by the recursion above, so this
            # close is always OUR OWN list's close.
            close_item()
            break
        elif tok.type == "list_item_open":
            close_item()
            current = ([], [])
        elif tok.type == "list_item_close":
            close_item()
        elif tok.type == "paragraph_open":
            pass  # handled via inline tokens
        elif tok.type in ("fence", "code_block"):
            # Code fences inside list items are extremely common in runbooks
            # ("1. run: ```bash"). Only serializing inline tokens here made
            # 1,566 fences across 362 docs vanish with NO drop record —
            # the gate's lost-token/char-loss checks saw unexplained loss.
            item = ensure_item()
            info = (tok.info or "").strip() if tok.type == "fence" else ""
            code = tok.content.rstrip("\n")
            item[0].extend(_fence_block(info, code).splitlines())
            if code:
                item[1].append(code)
        elif tok.type == "html_block":
            converted = convert_fragment(tok.content)
            if converted.strip():
                item = ensure_item()
                for blk in blocks_from_markdown(converted):
                    if blk.md.strip():
                        item[0].extend(blk.md.splitlines())
                    if blk.plain.strip():
                        item[1].append(blk.plain)
        elif tok.type == "table_open":
            item = ensure_item()
            table_md, table_plain, j = _collect_table(tokens, i)
            item[0].extend(table_md.splitlines())
            if table_plain:
                item[1].append(table_plain)
            i = j - 1  # loop's trailing i += 1 lands on j
        elif tok.type == "hr":
            ensure_item()[0].append("---")
        elif tok.type == "inline":
            md = _inline_to_md(tok).strip()
            plain = _inline_plain(tok)
            if md:
                ensure_item()[0].append(md)
            if plain:
                # plain may exist even when md is empty (e.g. pure entity text)
                ensure_item()[1].append(plain)
        i += 1

    md_lines: list[str] = []
    plain_parts: list[str] = []
    for idx, (item_md, item_plain) in enumerate(items):
        prefix = f"{base_number + idx}." if ordered else "-"
        first, *rest = item_md or [""]
        md_lines.append(f"{prefix} {first}".rstrip())
        md_lines.extend(f"   {line}".rstrip() for line in rest)
        plain_parts.extend(item_plain)
    return "\n".join(md_lines), " ".join(plain_parts).strip(), i + 1


def _collect_blockquote(tokens: list[Token], start: int) -> tuple[str, str, int]:
    md_lines: list[str] = []
    plain_parts: list[str] = []
    i = start + 1
    while i < len(tokens) and tokens[i].type != "blockquote_close":
        tok = tokens[i]
        if tok.type == "inline":
            md_lines.append("> " + _inline_to_md(tok).strip())
            plain_parts.append(_inline_plain(tok))
        i += 1
    return "\n".join(md_lines), " ".join(plain_parts).strip(), i + 1


_FENCE_MARKER_RE = re.compile(r"^\s*(?:```|~~~)")
_TABLE_ROW_RE = re.compile(r"^\s*\|")


def _escape_code_span_pipes(line: str) -> str:
    """Escape unescaped pipes inside backtick spans of one table row."""
    out: list[str] = []
    span_run = 0
    in_span = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            out.append(c)
            if i + 1 < n:
                out.append(line[i + 1])
            i += 2
            continue
        if c == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            run = j - i
            if not in_span:
                in_span, span_run = True, run
            elif run == span_run:
                in_span = False
            out.append(line[i:j])
            i = j
            continue
        if c == "|" and in_span:
            out.append("\\|")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def escape_table_code_pipes(md: str) -> str:
    """Escape pipes inside inline-code spans on table rows.

    markdown-it's table rule splits cells on every unescaped pipe, even
    pipes inside backtick spans (GFM requires '\\|' there), and silently
    drops the cells after the split. Source files ship unescaped pipes in
    code (e.g. `register_{group|project}_runner`), losing whole sentences
    and links. Fenced blocks are left untouched.
    """
    lines = md.split("\n")
    in_fence = False
    out: list[str] = []
    for line in lines:
        if _FENCE_MARKER_RE.match(line):
            in_fence = not in_fence
            out.append(line)
        elif not in_fence and _TABLE_ROW_RE.match(line):
            out.append(_escape_code_span_pipes(line))
        else:
            out.append(line)
    return "\n".join(out)


def blocks_from_markdown(md: str) -> list[Block]:
    """Parse markdown (no frontmatter) into structural blocks."""
    if not md or not md.strip():
        return []
    tokens = _md().parse(escape_table_code_pipes(md))
    blocks: list[Block] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1]
            content = _inline_to_md(inline).strip()
            blocks.append(Block("heading", f"{'#' * level} {content}", _inline_plain(inline), level))
            i += 3
            continue
        elif tok.type == "paragraph_open":
            inline = tokens[i + 1]
            blocks.append(Block("prose", _inline_to_md(inline).strip(), _inline_plain(inline)))
            i += 3
            continue
        elif tok.type == "fence":
            info = (tok.info or "").strip()
            code = tok.content.rstrip("\n")
            blocks.append(Block("code", _fence_block(info, code), code))
            i += 1
            continue
        elif tok.type == "code_block":
            code = tok.content.rstrip("\n")
            blocks.append(Block("code", _fence_block("", code), code))
            i += 1
            continue
        elif tok.type == "table_open":
            table_md, table_plain, i = _collect_table(tokens, i)
            blocks.append(Block("table", table_md, table_plain))
            continue
        elif tok.type in ("bullet_list_open", "ordered_list_open"):
            list_md, list_plain, i = _collect_list(tokens, i)
            if list_md.strip():
                blocks.append(Block("list", list_md, list_plain))
            continue
        elif tok.type == "blockquote_open":
            quote_md, quote_plain, i = _collect_blockquote(tokens, i)
            if quote_md.strip():
                blocks.append(Block("prose", quote_md, quote_plain))
            continue
        elif tok.type == "hr":
            blocks.append(Block("prose", "---", ""))
            i += 1
            continue
        elif tok.type == "html_block":
            converted = convert_fragment(tok.content)
            if converted.strip():
                blocks.extend(blocks_from_markdown(converted))
            i += 1
            continue
        i += 1
    return blocks


def md_to_plain(md: str) -> str:
    """Plain-text form of an arbitrary markdown fragment (plan section A).

    Split-piece paths in the chunker receive the piece's markdown; without
    this, ``text_embed`` would carry raw markdown (links/emphasis/fences).
    Tables linearize via ``_collect_table``; markup and fences are stripped.
    """
    if not md or not md.strip():
        return ""
    parts = [b.plain for b in blocks_from_markdown(md) if b.plain.strip()]
    return "\n\n".join(parts).strip()


def parse_markdown(text: str, source_path: str = "(memory)") -> ParsedDoc:
    """Full markdown parse: frontmatter + shortcodes + blocks."""
    warnings: list[str] = []
    try:
        post = frontmatter.loads(text)
    except Exception as exc:  # malformed frontmatter must not abort the file
        warnings.append(f"frontmatter_error: {exc}")
        post = frontmatter.Post(text, None)

    meta = dict(post.metadata or {})
    body = preprocess(post.content or "")
    blocks = blocks_from_markdown(body)

    title = str(meta.get("title") or "").strip()
    if not title:
        for block in blocks:
            if block.kind == "heading" and block.plain:
                title = block.plain.strip()
                break
    if not title:
        title = source_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    return ParsedDoc(_SOURCE_TYPE, title, meta, blocks, warnings)
