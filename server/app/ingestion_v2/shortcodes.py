"""Hugo shortcode preprocessing (plan section B).

Token-level handling of ``{{< ... >}}`` / ``{{% ... %}}`` macros and HTML
comments, per the plan's rules:

- ``{{% include %}}``: deleted (the payload lives in another file).
- Paired shortcodes: delimiters removed, inner text kept.
- ``header=`` / ``title=`` (and ``caption=``): replaced with the value.
- Name-like args (``member-by-name``, ``label``, ``name``, ``term``):
  replaced with the (quoted) value.
- ID/slug args (``youtube``, ``group-by-slugs``, ``team-by-manager-slug``,
  any ``*-slug(s)`` key): deleted; bare video renderers become ``[video]``.
- Bare directives and orphan closers: deleted.
- HTML comments (including ``<!-- vale ... -->``): deleted.
"""
from __future__ import annotations

import re
from typing import TypedDict


class _Tok(TypedDict):
    name: str
    close: bool
    args: str
    start: int
    end: int

_INCLUDE_RE = re.compile(r"\{\{%\s*include\b[^}]*%\}\}")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_TOKEN_RE = re.compile(r"\{\{([<%])\s*(/\s*)?([a-zA-Z][\w-]*)([^{}]*?)(?:/\s*)?[>%]\}\}")

_HEADER_KEYS = {"header", "title", "caption"}
_NAME_KEYS = {"label", "member-by-name", "name", "term", "subject", "person"}
_VIDEO_NAMES = {"youtube", "vimeo", "video", "playlist", "gist", "speakerdeck"}


def _parse_args(arg_str: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Split ``key="value" key=value "positional" pos`` into pairs + positionals."""
    pairs: list[tuple[str, str]] = []
    positionals: list[str] = []
    for m in re.finditer(r'([\w-]+)="([^"]*)"|([\w-]+)=(\S+)|"([^"]+)"|(\S+)', arg_str):
        if m.group(1) is not None:
            pairs.append((m.group(1).lower(), m.group(2)))
        elif m.group(3) is not None:
            pairs.append((m.group(3).lower(), m.group(4)))
        elif m.group(5) is not None:
            positionals.append(m.group(5))
        elif m.group(6) is not None:
            positionals.append(m.group(6))
    return pairs, positionals


def _is_slug_key(key: str) -> bool:
    return key.endswith("-slug") or key.endswith("-slugs") or key.endswith("_slug")


def _render(name: str, arg_str: str, inner: str | None) -> str:
    pairs, positionals = _parse_args(arg_str)
    parts: list[str] = []

    for key, value in pairs:
        if key in _HEADER_KEYS:
            if value.strip():
                parts.append(value.strip())
        elif key in _NAME_KEYS:
            if value.strip():
                parts.append(f'"{value.strip()}"')
        elif _is_slug_key(key) or key in ("youtube", "vimeo", "video"):
            continue  # ID/slug args are dropped entirely
        elif inner:
            continue  # unknown args: keep only inner text
        # bare directive with unknown args and no inner text: drop the arg
    if inner:
        text = inner.strip()
        if text:
            parts.append(text)
    elif not parts and name.lower() in _VIDEO_NAMES:
        parts.append("[video]")

    return " ".join(parts).strip()


def _apply_tokens(body: str) -> str:
    """Replace include-free shortcode tokens via a linear scan with pairing."""
    tokens: list[_Tok] = [
        {
            "name": m.group(3),
            "close": bool(m.group(2)),
            "args": m.group(4) or "",
            "start": m.start(),
            "end": m.end(),
        }
        for m in _TOKEN_RE.finditer(body)
    ]
    if not tokens:
        return body

    out: list[str] = []
    pos = 0
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok["close"]:  # orphan closer
            out.append(body[pos : tok["start"]])
            pos = tok["end"]
            i += 1
            continue

        # look for a matching closer of the same name
        j = i + 1
        pair_idx = None
        while j < len(tokens):
            if tokens[j]["close"] and tokens[j]["name"].lower() == tok["name"].lower():
                pair_idx = j
                break
            if not tokens[j]["close"]:
                break  # nested open before a matching close: treat as bare
            j += 1

        out.append(body[pos : tok["start"]])
        if pair_idx is not None:
            inner = body[tok["end"] : tokens[pair_idx]["start"]]
            # recurse into inner for nested shortcodes
            inner = preprocess(inner)
            out.append(_render(tok["name"], tok["args"], inner))
            pos = tokens[pair_idx]["end"]
            i = pair_idx + 1
        else:
            out.append(_render(tok["name"], tok["args"], None))
            pos = tok["end"]
            i += 1

    out.append(body[pos:])
    return "".join(out)


def preprocess(body: str) -> str:
    """Apply all shortcode + comment rules to a markdown body."""
    if not body:
        return body
    text = _INCLUDE_RE.sub("", body)
    text = _COMMENT_RE.sub("", text)
    text = _apply_tokens(text)
    return text
