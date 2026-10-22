"""Block packing into 300-500-token chunks (plan section C).

- Pack blocks; soft-close at >=300 tokens before exceeding 500; hard max 800.
- Oversized blocks split: prose by paragraphs (~50-token overlap), tables by
  rows with repeated header + caption, code by lines with balanced fences.
- Headings set the heading-path stack; each chunk snapshots its path.
- Merge chunks <200 chars in the same section; drop chunks that are <50
  chars, have <5 alphabetic words, no alphabetic characters, or are pure
  markdown syntax — every drop is logged with a reason.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .blocks import Block, ParsedDoc
from .md_parser import md_to_plain
from .records import DropRecord
from .tokens import count_tokens

TARGET_MIN = 300
SOFT_MAX = 500
HARD_MAX = 800
OVERLAP_TOKENS = 50
MERGE_MIN_CHARS = 200
DROP_MIN_CHARS = 50
DROP_MIN_WORDS = 5

# Mojibake / non-English gate (Phase 2 amendment).
# Krutidev-font PDFs decode Devanagari into Latin letters + latin-1 symbols.
# ONLY true mojibake/decoder residue stays here: latin-1 symbol noise plus
# Ã-lead pairs and ãõñþÿ. Legit Western-European letters (éèàçÉÀÇßÑ...), the
# guillemets, §, ® and © were removed — they made French policy text score
# ~7% "mojibake" (> 2% drop) and deleted 34 legitimate France-SAS chunks.
MOJIBAKE_CHARS = set(
    "ªº¿¡¾½¼³²µ±¢¥£¤¦¬¯°´¸¹"
    "ÃÕãõñþÿ"
)
MOJIBAKE_RATIO_DROP = 0.02  # of non-space chars
NON_ASCII_LETTER_RATIO_DROP = 0.35  # of letters (non-Latin scripts)
ENGLISH_LIKE_MIN_WORDS = 15
ENGLISH_LIKE_RATIO_DROP = 0.05  # stopword share below this => non-English garbage
VOWELLESS_RATIO_DROP = 0.10  # vowelless len>=5-word share above this => Krutidev garbage
# Raised 8 -> 16: at 8 evaluated words a SINGLE vowelless word scores 0.125
# and dropped pure-English fragments (22 md/txt non_english drops in dry-run
# #10 were exactly that: v=0.101..0.400, mojibake=0, non-ascii=0). The true
# labour-PDF Krutidev chunks evaluate 20-21 words (v=0.143..0.150), so 16
# keeps them caught with margin (>=24 would let them through).
VOWELLESS_MIN_WORDS = 16
# The vowelless signature is a scanned-PDF font-decoding artifact (Krutidev
# Latin garbage from labour-code PDFs). It only runs for PDF-sourced chunks;
# md/txt/SEC fragments never had this failure mode (evidence: dry-run #10).
VOWELLESS_SOURCE_TYPES = {"pdf"}
# Doc-level language flag needs TWO kinds of evidence: enough prose for the
# stopword sample to mean something, or strong non-Latin-script presence.
# An English roster page ("Meet the Engineering Managers": 75 words, 1.48%
# accented letters from names, table text has almost no stopwords) failed
# the bare likeness test; umlaut-poor foreign docs (German handbook rules:
# 1,760 words) pass the word-count branch. See doc_non_english().
DOC_FLAG_MIN_WORDS = 150
DOC_FLAG_MIN_NA_LETTERS = 0.03

# URL/brand tokens that are vowelless but perfectly normal in English docs.
_VOWELLESS_IGNORE = {
    "https", "http", "www", "html", "xhtml", "php", "aspx", "css", "svg",
    "png", "jpg", "jpeg", "gif", "inc", "llc", "ltd", "pdf", "href", "com",
    "org", "net", "json", "yaml", "xml", "sql", "rst", "txt",
}
_VOWELS = set("aeiou")

# Link destinations and bare URLs: their letter-runs ("Kpczt", "PLFGf",
# "NsQth") score as vowelless >=5-letter words and made pure-ASCII English
# link lists fail the Krutidev signature (customer-content "Day 5" chunk).
_MD_LINK_DEST_RE = re.compile(r"\]\([^)]*\)")
_BARE_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def _has_mixed_case(word: str) -> bool:
    return any(c.islower() for c in word) and any(c.isupper() for c in word)

# Common English function words for the English-likeness gate.
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "her", "was", "one", "our", "out", "has", "have", "had", "who", "its",
    "may", "she", "him", "his", "how", "now", "why", "were", "this", "that",
    "these", "those", "with", "from", "into", "than", "then", "them", "they",
    "their", "there", "would", "could", "should", "shall", "must", "will",
    "about", "after", "before", "under", "over", "between", "during",
    "without", "within", "upon", "also", "such", "each", "other", "some",
    "both", "few", "more", "most", "only", "own", "same", "too", "very",
    "just", "because", "while", "where", "when", "what", "which", "whom",
    "a", "an", "of", "to", "in", "on", "at", "by", "or", "as", "is", "be",
    "been", "being", "it", "if", "per", "via", "no", "do", "does", "did",
    "get", "got", "let", "made", "make", "see", "seen", "use", "used",
    "using", "well", "back", "even", "still", "here", "up", "down", "off",
    "he", "we", "me", "my", "our", "your", "i",
}

_SYNTAX_CHARS = set("#-|*>_`~:=")
_LOWER3_RE = re.compile(r"[a-z]{3,}")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_NON_SPACE_RE = re.compile(r"\S")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_WORD3_RE = re.compile(r"[A-Za-z']{2,}")
_WORD5_RE = re.compile(r"[A-Za-z]{5,}")
_UNI_WORDS_RE = re.compile(r"[^\W\d_]{2,}")  # Unicode letter runs (CJK/Devanagari/…)
# Scripts written without spaces (CJK/kana/hangul/thai/lao): run-counting says
# "1 word" for an entire paragraph, so the few_words check must not fire —
# length is already enforced by too_short.
_SPACELESS_SCRIPT_RE = re.compile(
    r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\uac00-\ud7af\u0e00-\u0e7f\u0e80-\u0eff]"
)
# Standalone page-number shapes: bare integer, "-36 -", "Page 7"/"pg.7".
# Dropped as page_number ONLY in the three page-bearing scanned source types;
# every other numeric-only block (section/clause numbers like "2.1"/"27.",
# handbook numerals) MERGES forward — never no_alpha (plan conditions 1-2).
# Tightened from 4 digits to 3 after the evidence audit: the only 4-digit
# hits were chart/table values ("1621", "3795", "2949"), never page numbers.
_PAGE_NUM_RE = re.compile(r"(?i)(?:page|pg\.)\s*\d{1,3}|\d{1,3}|-\s*\d{1,3}\s*-")
PAGE_NUMBER_SOURCE_TYPES = {"cuad_txt", "pdf", "sec_htm"}


def _has_letter(text: str) -> bool:
    """ANY Unicode letter (not ASCII): CJK/Devanagari/accented text is content."""
    return any(ch.isalpha() for ch in text)


def _numeric_only(text: str) -> bool:
    return any(ch.isdigit() for ch in text) and not _has_letter(text)


def _is_page_number(text: str) -> bool:
    return bool(_PAGE_NUM_RE.fullmatch(text.strip()))


def mojibake_ratio(text: str) -> float:
    non_space = _NON_SPACE_RE.findall(text)
    if not non_space:
        return 0.0
    hits = sum(1 for c in non_space if c in MOJIBAKE_CHARS)
    return hits / len(non_space)


def non_ascii_letter_ratio(text: str) -> float:
    letters = _LETTER_RE.findall(text)
    if not letters:
        return 0.0
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    return non_ascii / len(letters)


def english_likeness(text: str) -> float | None:
    """Share of common stopwords among words (None if too few words)."""
    words = _WORD3_RE.findall(text.lower())
    if len(words) < ENGLISH_LIKE_MIN_WORDS:
        return None
    return sum(1 for w in words if w in _STOPWORDS) / len(words)


def vowelless_word_ratio(text: str) -> float | None:
    """Share of len>=5 words with no vowel (Krutidev signature). None if sparse.

    Link destinations / bare URLs are stripped first (their id runs are
    vowelless noise). Mixed-case tokens are skipped ONLY when they START
    with an uppercase letter — acronym style (TzBfG, BetrVG, BGB). Krutidev
    garbage runs like ``jftLV``/``fnYyh`` start lowercase: counting them is
    what quarantines the labour PDF's decoded-Devanagari chunks.
    """
    text = _BARE_URL_RE.sub(" ", _MD_LINK_DEST_RE.sub(" ", text))
    words = [
        w.lower()
        for w in _WORD5_RE.findall(text)
        if w.lower() not in _VOWELLESS_IGNORE
        and not (_has_mixed_case(w) and w[0].isupper())
    ]
    if len(words) < VOWELLESS_MIN_WORDS:
        return None
    return sum(1 for w in words if not set(w) & _VOWELS) / len(words)


def mojibake_drop_reason(
    text: str,
    kinds: set[str] | None = None,
    source_type: str = "",
) -> str | None:
    if mojibake_ratio(text) > MOJIBAKE_RATIO_DROP:
        return "mojibake_suspect"
    if non_ascii_letter_ratio(text) > NON_ASCII_LETTER_RATIO_DROP:
        return "non_english"
    if source_type in VOWELLESS_SOURCE_TYPES:
        vowelless = vowelless_word_ratio(text)
        if vowelless is not None and vowelless >= VOWELLESS_RATIO_DROP:
            return "non_english"
    # NOTE: the stopword-based English-likeness test no longer runs here.
    # Applied per-fragment it misfired on English label lists, table cells,
    # checklists and diagrams (1,666/1,741 non_english drops were pure-ASCII
    # English) because fragments legitimately lack stopwords. Language is a
    # document property — see doc_non_english().
    return None


def doc_non_english(parsed: ParsedDoc) -> tuple[bool, float | None]:
    """Document-level language verdict from the stopword-likeness gate.

    Returns (is_non_english, likeness). Judged on the whole document's plain
    text: long-form prose carries enough stopwords to distinguish English
    (>= ENGLISH_LIKE_RATIO_DROP) from foreign text, while ASCII fragments
    alone never could. A low likeness additionally needs either
    DOC_FLAG_MIN_WORDS of sample or DOC_FLAG_MIN_NA_LETTERS of script
    evidence, so stopword-poor English tables stay in. ASCII documents are
    never flagged here — script and glyph evidence stays per-fragment in
    ``mojibake_drop_reason``.
    """
    text = "\n".join(b.plain for b in parsed.blocks if b.plain.strip())
    na_letters = non_ascii_letter_ratio(text)
    if na_letters == 0.0:
        return False, None
    likeness = english_likeness(text)
    if likeness is None or likeness >= ENGLISH_LIKE_RATIO_DROP:
        return False, None
    # Low likeness alone is not enough evidence: table-heavy English docs
    # (rosters, attribute tables) legitimately have almost no stopwords.
    # Require either a meaningful prose sample or strong script evidence.
    if (
        len(_WORD_RE.findall(text)) < DOC_FLAG_MIN_WORDS
        and na_letters < DOC_FLAG_MIN_NA_LETTERS
    ):
        return False, None
    return True, likeness


def _drop_block_reason(block: Block, source_type: str = "") -> str | None:
    """Block-level junk filter (front-matter fragments, separators, orphans).

    Plan conditions 1-2: standalone page numbers (bare integer, "- 36 -",
    "Page 7") drop as ``page_number`` ONLY in cuad_txt/pdf/sec_htm prose;
    every other numeric-only block (section/clause numbers like "2.1"/"27.",
    handbook numerals) returns None so it MERGES forward — never no_alpha.
    Lists are never junked for being short (they merge via the rescue pass).
    """
    if block.kind == "heading" and not block.plain.strip():
        return "empty_heading"
    if block.kind == "table" and not re.search(r"[^\W\d_]{2}", block.md, re.UNICODE):
        return "empty_table"
    if block.kind in ("prose", "list"):
        text = block.md.strip()
        if not text or _is_syntax_only(text):
            return "syntax_only"
        if (
            source_type in PAGE_NUMBER_SOURCE_TYPES
            and _is_page_number(text)
        ):
            # page identity beats kind: "- 36 -" parses as a list block but
            # the shape is a page marker in the three scanned sources
            return "page_number"
        if not _has_letter(text):
            if any(ch.isdigit() for ch in text):
                return None  # numeric-only -> merge forward (condition 1)
            return "no_alpha"
        if (
            block.kind == "prose"
            and len(text) < DROP_MIN_CHARS
            and len(_UNI_WORDS_RE.findall(text)) < DROP_MIN_WORDS
            and not _LOWER3_RE.search(text)
        ):
            return "junk_fragment"
    return None


@dataclass
class Draft:
    text_md: str
    plain: str
    heading_path: list[str]
    kinds: set[str] = field(default_factory=set)
    oversize_justification: str | None = None

    @property
    def token_count(self) -> int:
        return count_tokens(self.text_md)

    @property
    def block_type(self) -> str:
        if len(self.kinds) == 1:
            return next(iter(self.kinds))
        return "mixed"


def _path_from_stack(stack: dict[int, str]) -> list[str]:
    return [stack[level] for level in sorted(stack) if stack[level]]


def _merge_block(cur_md: list[str], cur_plain: list[str], cur_kinds: set[str],
                 block: Block) -> None:
    cur_md.append(block.md)
    if block.plain:
        cur_plain.append(block.plain)
    cur_kinds.add(block.kind)


def _draft_from(parts_md: list[str], parts_plain: list[str], kinds: set[str],
                path: list[str]) -> Draft | None:
    # NOT a bare .strip(): a draft that STARTS with an indented list fence
    # ("   ```bash …   ```") would lose the opener's indent while the closer
    # keeps its own — the closer then no longer closes under CommonMark.
    text_md = _strip_keep_fence_indent("\n\n".join(parts_md))
    if not text_md:
        return None
    plain = "\n\n".join(parts_plain).strip()
    return Draft(text_md, plain, list(path), set(kinds))


def _marker_run(stripped: str) -> int:
    """Length of the leading backtick run on a marker line."""
    run = 0
    for ch in stripped:
        if ch != "`":
            break
        run += 1
    return run


def _fence_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of fenced code blocks (plan: fences are atomic).

    Closer rule mirrors markdown-it/CommonMark: only an INFO-LESS marker at
    indent <= the opener's indent AND with a backtick-run >= the opener's
    closes the fence (``` cannot close ````). Info'd marker lines
    ("```markdown") and shorter/deeper markers are fence CONTENT — sources
    contain both, and a naive line-toggle mispairs them, which cut records
    mid-fence. An unterminated opener yields no span (the source was itself
    malformed there; splitting elsewhere is still correct).
    """
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    opener_indent = 0
    opener_run = 3
    off = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            indent = len(line) - len(line.lstrip())
            run = _marker_run(stripped)
            if open_at is None:
                open_at = off
                opener_indent = indent
                opener_run = run
            elif (
                not stripped[run:].strip()
                and indent <= opener_indent
                and run >= opener_run
            ):
                spans.append((open_at, off + len(line)))
                open_at = None
        off += len(line)
    return spans


def fences_balanced(text: str) -> bool:
    """True when no fence runs to end-of-text unterminated.

    Same closer rule as _fence_spans, used by the gate's balance canary:
    a record whose last fence is unclosed renders trailing content as code.
    """
    open_indent = 0
    open_run = 3
    open_at = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("```"):
            continue
        indent = len(line) - len(line.lstrip())
        run = _marker_run(stripped)
        if not open_at:
            open_at = True
            open_indent = indent
            open_run = run
        elif (
            not stripped[run:].strip()
            and indent <= open_indent
            and run >= open_run
        ):
            open_at = False
    return not open_at


def _strip_keep_fence_indent(p: str) -> str:
    """Strip a piece but keep the opener's leading indent if it starts a fence.

    A dedented opener with still-indented content/closer no longer closes
    under CommonMark (closer indent must be <= opener indent) — list fences
    ("   ```bash …   ```") arrive indented, and stripping only the opener
    produced records the gate correctly flags as unclosed.
    """
    s = p.strip()
    if s.startswith("```"):
        lead = p[: len(p) - len(p.lstrip())]
        if lead:
            return lead + s
    return s


def _paragraph_split(text: str) -> list[str]:
    """Split on blank lines that are NOT inside a fence (plan: atomic fences)."""
    spans = _fence_spans(text)
    parts: list[str] = []
    last = 0
    for m in re.finditer(r"\n\n+", text):
        a = m.start()
        if any(s < a < e for s, e in spans):
            continue
        parts.append(text[last:a])
        last = m.end()
    parts.append(text[last:])
    return [stripped for p in parts if (stripped := _strip_keep_fence_indent(p))]


def _sentence_pieces(text: str, budget: int = HARD_MAX) -> list[str]:
    """Split a single huge paragraph at sentence boundaries with ~50-token overlap.

    Piece size is measured on the exact joined text (not a sum of sentence
    counts) — BPE tokenization is not additive across sentence boundaries, and
    the sum undercounts by 1-2 tokens, which used to let 801-token pieces slip
    past HARD_MAX and then read as 'unsplittable atoms'.
    """
    if _fence_spans(text):
        return _fence_aware_pieces(text, budget)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    cur: list[str] = []

    for sentence in sentences:
        candidate = " ".join(cur + [sentence]) if cur else sentence
        if cur and count_tokens(candidate) > budget:
            pieces.append(" ".join(cur))
            overlap = _tail_tokens(pieces[-1], OVERLAP_TOKENS)
            # Skip a no-gain overlap (previous piece smaller than the overlap
            # budget -> tail == whole piece) — re-attaching it just regenerates
            # the same oversized piece forever in finalize's recursion.
            if overlap and count_tokens(overlap) < count_tokens(pieces[-1]):
                cur = [overlap]
            else:
                cur = []
        cur.append(sentence)
    if cur:
        pieces.append(" ".join(cur))
    return [p for p in pieces if p.strip()]


def _fence_aware_pieces(text: str, budget: int) -> list[str]:
    """Sentence-pack text whose fences must stay atomic.

    Fence segments ride along as single units (newline-joined to neighbors);
    only prose segments are sentence-split. A lone fence over budget stays a
    whole unit — _finalize_drafts then justifies it instead of cutting it.
    """
    segs: list[tuple[str, bool]] = []
    last = 0
    for a, b in _fence_spans(text):
        if text[last:a].strip():
            segs.append((text[last:a].strip(), False))
        segs.append((text[a:b].strip("\n"), True))
        last = b
    if text[last:].strip():
        segs.append((text[last:].strip(), False))

    units: list[str] = []
    fence_flags: list[bool] = []
    for seg, is_fence in segs:
        if is_fence:
            units.append(seg)
            fence_flags.append(True)
        else:
            for sentence in re.split(r"(?<=[.!?])\s+", seg):
                if sentence.strip():
                    units.append(sentence)
                    fence_flags.append(False)

    def join(cur: list[str], flags: list[bool]) -> str:
        out = cur[0]
        for i in range(1, len(cur)):
            sep = "\n" if (flags[i] or flags[i - 1]) else " "
            out = out + sep + cur[i]
        return out

    pieces: list[str] = []
    cur: list[str] = []
    cur_flags: list[bool] = []
    for unit, is_fence in zip(units, fence_flags):
        if cur:
            candidate = join([*cur, unit], [*cur_flags, is_fence])
            if count_tokens(candidate) > budget:
                pieces.append(join(cur, cur_flags))
                overlap = _tail_tokens(pieces[-1], OVERLAP_TOKENS)
                if overlap and count_tokens(overlap) < count_tokens(pieces[-1]):
                    cur = [overlap]
                    cur_flags = [False]
                else:
                    cur = []
                    cur_flags = []
        cur.append(unit)
        cur_flags.append(is_fence)
    if cur:
        pieces.append(join(cur, cur_flags))
    return [p for p in pieces if p.strip()]


def _split_prose(block: Block) -> list[Draft]:
    paragraphs = _paragraph_split(block.md)
    plain_parts = [p.strip() for p in (block.plain or "").split("\n\n") if p.strip()]
    # (md, plain, already_overlapped) — oversized paragraphs are split by
    # _sentence_pieces, which already prepends its own overlap; the packing
    # loop must not prepend a second copy of the same tail.
    units: list[tuple[str, str, bool]] = []
    for idx, para in enumerate(paragraphs):
        para_plain = plain_parts[idx] if idx < len(plain_parts) else ""
        if count_tokens(para) > HARD_MAX:
            for piece in _sentence_pieces(para):
                # plain must be stripped of markdown (plan A), never the md itself
                units.append((piece, md_to_plain(piece), True))
        else:
            units.append((para, para_plain, False))

    pieces: list[Draft] = []
    cur_md: list[str] = []
    cur_plain: list[str] = []

    def close() -> None:
        nonlocal cur_md, cur_plain
        draft = _draft_from(cur_md, cur_plain, {"prose"}, [])
        if draft:
            pieces.append(draft)
        cur_md, cur_plain = [], []

    for para, para_plain, already_overlapped in units:
        if cur_md and count_tokens("\n\n".join(cur_md + [para])) > HARD_MAX:
            close()
            # ~50-token overlap: tail of the previous piece (unless the next
            # unit already begins with that tail from _sentence_pieces)
            if pieces and not already_overlapped:
                overlap = _tail_tokens(pieces[-1].text_md, OVERLAP_TOKENS)
                if overlap:
                    cur_md.append(overlap)
                    cur_plain.append(_tail_tokens(pieces[-1].plain, OVERLAP_TOKENS))
        cur_md.append(para)
        if para_plain:
            cur_plain.append(para_plain)
    close()
    return pieces


def _tail_tokens(text: str, budget: int) -> str:
    """Return the last ~budget tokens of text, snapped to a sentence boundary."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chosen: list[str] = []
    used = 0
    for sentence in reversed(sentences):
        tokens = count_tokens(sentence)
        if used + tokens > budget and chosen:
            break
        if tokens > budget and not chosen:
            # Single sentence dwarfs the budget (e.g. a giant link list with
            # no periods): take a word-sliced tail instead of the whole text —
            # otherwise the "overlap" becomes the entire chunk, duplicated.
            words = sentence.split()
            tail_words: list[str] = []
            used_w = 0
            for word in reversed(words):
                wt = count_tokens(word) + 1
                if used_w + wt > budget and tail_words:
                    break
                tail_words.append(word)
                used_w += wt
            chosen.append(" ".join(reversed(tail_words)))
            break
        chosen.append(sentence)
        used += tokens
    tail = " ".join(reversed(chosen)).strip()
    # An overlap that carries fence markers gets glued mid-line onto the next
    # piece ("prose. ```bash"), which the gate's line-based balance check counts
    # as an opener without a closer — and a partial fence is never useful in a
    # duplicate tail anyway. Cut at the first marker; the full fence remains in
    # the piece it was copied from.
    if "```" in tail:
        tail = tail[: tail.find("```")].strip()
    return tail


def _is_separator_line(line: str) -> bool:
    if "|" not in line:
        return False
    bare = line.replace("|", "").replace(":", "").replace(" ", "").replace("*", "")
    return bool(bare) and set(bare) <= {"-"}


def _split_table(block: Block, caption: str = "") -> list[Draft]:
    lines = [ln for ln in block.md.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    sep_idx = next((i for i, line in enumerate(lines) if _is_separator_line(line) and i > 0), None)
    if sep_idx is None or sep_idx + 1 >= len(lines):
        # malformed: treat the whole table as one piece if it fits, else prose-split
        return _split_prose(block)
    prefix = lines[: sep_idx - 1] if sep_idx >= 1 else []  # caption lines above header
    header = lines[sep_idx - 1]
    sep = lines[sep_idx]
    body = [ln for ln in lines[sep_idx + 1 :] if "|" in ln]
    if not body:
        return _split_prose(block)

    # Unfiltered splitlines: _collect_table keeps empty layout rows as ""
    # lines, and they must stay aligned 1:1 with body rows — dropping them
    # shifts plain rows onto the wrong chunks and exhausts them entirely.
    plain_rows = (block.plain or "").splitlines()

    def _piece_md(rows: list[str]) -> str:
        md_parts = []
        if caption:
            md_parts.append(caption)
        md_parts.extend(prefix)
        md_parts.append("\n".join([header, sep, *rows]))
        return "\n\n".join(md_parts)

    pieces: list[Draft] = []
    cur_rows: list[str] = []
    cur_plains: list[str] = []

    def close() -> None:
        nonlocal cur_rows, cur_plains
        if not cur_rows:
            return
        # plain stays rows-only (aligned 1:1 with body rows, same convention
        # as _collect_table) so finalize-time row resplits stay aligned;
        # the caption still rides along in text_md.
        pieces.append(Draft(_piece_md(cur_rows), "\n".join(cur_plains), [], {"table"}))
        cur_rows = []
        cur_plains = []

    for idx, row in enumerate(body):
        # Budget is measured on the *joined* piece (BPE is not additive over
        # rows — summing row counts let an 801-token piece slip past HARD_MAX).
        if cur_rows and count_tokens(_piece_md([*cur_rows, row])) > HARD_MAX:
            close()
        cur_rows.append(row)
        if idx < len(plain_rows):
            cur_plains.append(plain_rows[idx])
    close()
    return pieces


def _split_code(block: Block) -> list[Draft]:
    lines = block.md.splitlines()
    pieces: list[Draft] = []
    cur: list[str] = []

    def close() -> None:
        nonlocal cur
        if not cur:
            return
        text_md = _strip_keep_fence_indent("\n".join(cur))
        if text_md:
            # plain never carries fences/markdown (plan A)
            pieces.append(Draft(text_md, md_to_plain(text_md), [], {"code"}))
        cur = []

    for line in lines:
        # Measure the *stripped* candidate: close() strips, and trailing
        # blank lines shift BPE tokenization — an unstripped check let an
        # 802-token piece through, which then resplit forever in finalize.
        candidate = ("\n".join(cur + [line])).strip() if cur else line.strip()
        if cur and count_tokens(candidate) > HARD_MAX:
            close()
        cur.append(line)
    close()

    balanced: list[Draft] = []
    for draft in pieces:
        if fences_balanced(draft.text_md):
            balanced.append(draft)
            continue
        # mid-fence cut: re-close with the opener's own delimiter/indent
        # (a line-toggle parity check mispairs content that looks like
        # markers and appended the wrong closer).
        opener = next(
            (
                ln
                for ln in draft.text_md.splitlines()
                if ln.strip().startswith("```")
            ),
            "```",
        )
        lead = opener[: len(opener) - len(opener.lstrip())]
        run = re.match(r"`+", opener.strip())
        ticks = run.group(0) if run else "```"
        balanced.append(Draft(
            draft.text_md + f"\n{lead}{ticks}",
            draft.plain,  # body-only plain stays body-only
            [],
            {"code"},
        ))
    return balanced


def _split_block(block: Block, caption: str = "") -> list[Draft]:
    if block.kind == "table":
        return _split_table(block, caption)
    if block.kind == "code":
        return _split_code(block)
    return _split_prose(block)


def _is_syntax_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return all(c in _SYNTAX_CHARS or c.isspace() for c in stripped)


def _drop_reason(text: str, kinds: set[str] | None = None) -> str | None:
    """Draft-level drop reason (plan conditions 1-2).

    Letterless NUMERIC drafts return None — they were merged by the rescue
    pass and must never die under no_alpha (gate FAILURE condition). List
    drafts never drop for being short (only empty/punctuation-only ones do,
    via syntax_only/no_alpha). Length rules apply to prose/heading/table/code.
    """
    stripped = text.strip()
    if _is_syntax_only(stripped):
        return "syntax_only"
    if not _has_letter(stripped):
        if any(ch.isdigit() for ch in stripped):
            return None  # numeric-only survives: merge-rescued, never no_alpha
        return "no_alpha"
    if kinds is not None and "list" in kinds:
        return None  # condition 2: list drafts never drop for length/word count
    if len(stripped) < DROP_MIN_CHARS:
        return "too_short"
    if (
        not _SPACELESS_SCRIPT_RE.search(stripped)
        and len(_UNI_WORDS_RE.findall(stripped)) < DROP_MIN_WORDS
    ):
        return "few_words"
    return None


def _table_body_rows(md: str) -> int:
    lines = [ln for ln in md.splitlines() if ln.strip() and "|" in ln]
    return max(len(lines) - 2, 0)  # minus header + separator


def _split_at_newlines(text: str, budget: int = HARD_MAX) -> list[str]:
    """Pack standalone lines (e.g. markdown link lists) up to budget.

    Fallback for oversized prose with no sentence boundaries: link-list lines
    are self-contained units, so splitting between lines is safe and keeps
    giant navigation lists from becoming 12k-token atoms.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    # Same fence-group lines must ride together (plan: atomic fences): group id
    # via the opener/content/closer rule from _fence_spans — info'd, shorter,
    # or deeper marker lines are content, only a clean line at <= opener
    # indent with run >= opener run closes — and only cut at group boundaries.
    groups: list[int | None] = []
    group_id = 0
    open_id: int | None = None
    open_indent = 0
    open_run = 3
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            indent = len(ln) - len(ln.lstrip())
            run = _marker_run(stripped)
            if open_id is None:
                group_id += 1
                open_id = group_id
                open_indent = indent
                open_run = run
                groups.append(group_id)
            elif (
                not stripped[run:].strip()
                and indent <= open_indent
                and run >= open_run
            ):
                groups.append(open_id)
                open_id = None
            else:
                groups.append(open_id)
        elif open_id is not None:
            groups.append(open_id)
        else:
            groups.append(None)
    pieces: list[str] = []
    cur: list[str] = []
    for idx, line in enumerate(lines):
        candidate = "\n".join(cur + [line]) if cur else line
        same_fence = (
            groups[idx] is not None and idx > 0 and groups[idx] == groups[idx - 1]
        )
        if cur and count_tokens(candidate) > budget and not same_fence:
            pieces.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        pieces.append("\n".join(cur))
    return pieces if len(pieces) >= 2 else []


def _code_body_lines(md: str) -> int:
    return sum(
        1
        for ln in md.splitlines()
        if ln.strip() and not ln.strip().startswith("```")
    )


def _finalize_drafts(drafts: list[Draft]) -> tuple[list[Draft], list[Draft]]:
    """Enforce HARD_MAX: split further when possible; justify structural atoms.

    Recurses on split pieces because _sentence_pieces keeps its own ~50-token
    overlap, so a piece can still land just over HARD_MAX and need one more
    split (or an atom justification if it truly has no boundary left).
    """
    out: list[Draft] = []
    atoms: list[Draft] = []
    for draft in drafts:
        tokens = draft.token_count
        if tokens <= HARD_MAX:
            out.append(draft)
            continue
        if draft.kinds == {"table"} and _table_body_rows(draft.text_md) <= 1:
            draft.oversize_justification = "single table row (plan: never split inside a table row)"
            atoms.append(draft)
            out.append(draft)
            continue
        if draft.kinds == {"code"} and _code_body_lines(draft.text_md) <= 1:
            draft.oversize_justification = "single code line (plan: never split inside a code fence line)"
            atoms.append(draft)
            out.append(draft)
            continue
        if draft.kinds == {"table"} and _table_body_rows(draft.text_md) > 1:
            # Oversize table: split by ROWS with the header repeated (plan C).
            # Sentence-splitting would cut inside a row and leak markdown.
            resplit = _split_table(Block("table", draft.text_md, draft.plain))
            if len(resplit) > 1 and max(p.token_count for p in resplit) < draft.token_count:
                sub_out, sub_atoms = _finalize_drafts(resplit)
                out.extend(sub_out)
                atoms.extend(sub_atoms)
                continue
            draft.oversize_justification = "single table row over budget (never split inside a row)"
            atoms.append(draft)
            out.append(draft)
            continue
        if draft.kinds == {"code"}:
            resplit = _split_code(Block("code", draft.text_md, draft.plain))
            # Progress guard: a split that reproduces the same oversize piece
            # (BPE edge) must become a justified atom, not recurse forever.
            if len(resplit) > 1 and max(p.token_count for p in resplit) < draft.token_count:
                sub = [
                    Draft(p.text_md, p.plain, list(draft.heading_path), set(draft.kinds))
                    for p in resplit
                ]
                sub_out, sub_atoms = _finalize_drafts(sub)
                out.extend(sub_out)
                atoms.extend(sub_atoms)
                continue
            draft.oversize_justification = "single code unit over budget (fence kept balanced)"
            atoms.append(draft)
            out.append(draft)
            continue
        pieces = _sentence_pieces(draft.text_md)
        made_progress = len(pieces) > 1 and max(len(p) for p in pieces) < len(draft.text_md)
        if not made_progress and draft.kinds <= {"prose", "list"} and "\n" in draft.text_md:
            line_pieces = _split_at_newlines(draft.text_md)
            if line_pieces:
                sub = [
                    Draft(piece, md_to_plain(piece), list(draft.heading_path), set(draft.kinds))
                    for piece in line_pieces
                ]
                sub_out, sub_atoms = _finalize_drafts(sub)
                out.extend(sub_out)
                atoms.extend(sub_atoms)
                continue
        if not made_progress:
            draft.oversize_justification = "single unsplittable unit (no sentence or line boundary under budget)"
            atoms.append(draft)
            out.append(draft)
            continue
        sub = [
            Draft(piece, md_to_plain(piece), list(draft.heading_path), set(draft.kinds))
            for piece in pieces
        ]
        sub_out, sub_atoms = _finalize_drafts(sub)
        out.extend(sub_out)
        atoms.extend(sub_atoms)
    return out, atoms


def _is_empty_stub(text_md: str) -> bool:
    """Heading-only draft: no body content beyond headings and rules."""
    for ln in text_md.splitlines():
        s = ln.strip()
        if not s or s in {"---", "***", "___"}:
            continue
        if re.fullmatch(r"#{1,6}\s.*", s):
            continue
        return False
    return True


def _rescue_must_merge(drafts: list[Draft], skip_ids: set[int]) -> list[Draft]:
    """Conditions 1-2: numeric-only and sub-50 list drafts must MERGE.

    Numeric drafts prefer the NEXT draft (they land as a prefix of the next
    block's content — a section number prefixes its body); list drafts try
    next then prev. Oversized atoms are skipped. A draft with no mergeable
    host passes through (visible to the gate) — this pass never drops.
    """
    i = 0
    while i < len(drafts):
        d = drafts[i]
        must = _numeric_only(d.text_md) or (
            "list" in d.kinds and len(d.text_md) < DROP_MIN_CHARS
        )
        if not must or id(d) in skip_ids:
            i += 1
            continue
        merged_at: int | None = None
        for j in (i + 1, i - 1):
            if not (0 <= j < len(drafts)) or id(drafts[j]) in skip_ids:
                continue
            host = drafts[j]
            first, second = (d, host) if j > i else (host, d)
            if count_tokens(first.text_md + "\n\n" + second.text_md) > HARD_MAX:
                continue
            merged_at = j
            drafts[min(i, j)] = Draft(
                first.text_md + "\n\n" + second.text_md,
                (first.plain + "\n\n" + second.plain).strip(),
                host.heading_path,
                first.kinds | second.kinds,
            )
            del drafts[max(i, j)]
            break
        if merged_at is None:
            i += 1  # unmergeable: keep it (gate sees it) — never silently drop
            continue
        # re-evaluate the merged draft at its new position (may chain)
        i = i if merged_at > i else i - 1
    return drafts


def chunk_doc(parsed: ParsedDoc) -> tuple[list[Draft], list[DropRecord]]:
    """Pack a ParsedDoc into drafts; returns (drafts, drops)."""
    drafts: list[Draft] = []
    drops: list[DropRecord] = []

    stack: dict[int, str] = {}
    cur_md: list[str] = []
    cur_plain: list[str] = []
    cur_kinds: set[str] = set()
    cur_path: list[str] = []
    cur_tokens = 0
    last_non_heading_plain = ""

    def flush() -> None:
        nonlocal cur_md, cur_plain, cur_kinds, cur_tokens, cur_path
        draft = _draft_from(cur_md, cur_plain, cur_kinds, cur_path)
        if draft:
            drafts.append(draft)
        elif any(p.strip() for p in cur_md):
            # no-silent-drops invariant: non-whitespace must become a draft
            # (process_file catches this and reports it as a parse_error)
            raise RuntimeError("silent draft loss: non-whitespace produced no draft")
        cur_md, cur_plain, cur_kinds, cur_tokens = [], [], set(), 0
        cur_path = []

    block_drops = 0
    block_kept = 0
    for block in parsed.blocks:
        block_reason = _drop_block_reason(block, parsed.source_type)
        if block_reason:
            drops.append(
                DropRecord(
                    block_reason,
                    block.md[:120],
                    _path_from_stack(stack),
                    block.kind,
                    block.md[:100_000],
                )
            )
            block_drops += 1
            continue
        block_kept += 1
        if block.kind == "heading":
            flush()
            level = block.level or 1
            for existing in [lv for lv in stack if lv >= level]:
                del stack[existing]
            stack[level] = block.plain.strip()
            last_non_heading_plain = block.plain.strip()
            cur_path = _path_from_stack(stack)
            _merge_block(cur_md, cur_plain, cur_kinds, block)
            cur_tokens = count_tokens(block.md)
            continue

        block_tokens = count_tokens(block.md)
        if block_tokens > HARD_MAX:
            flush()
            caption = " ".join(last_non_heading_plain.split())[:160]
            for piece in _split_block(block, caption):
                piece.heading_path = list(_path_from_stack(stack))
                drafts.append(piece)
            continue

        if cur_md and count_tokens("\n\n".join(cur_md + [block.md])) > SOFT_MAX and cur_tokens >= TARGET_MIN:
            flush()
            cur_path = list(_path_from_stack(stack))
        elif cur_md and count_tokens("\n\n".join(cur_md + [block.md])) > HARD_MAX:
            flush()
            cur_path = list(_path_from_stack(stack))

        if not cur_md:
            cur_path = list(_path_from_stack(stack))
        _merge_block(cur_md, cur_plain, cur_kinds, block)
        cur_tokens += block_tokens
        if block.kind == "prose" and block.plain.strip():
            last_non_heading_plain = block.plain.strip()[:200]

    # no-silent-drops invariant: every parsed block was dropped or kept
    if block_drops + block_kept != len(parsed.blocks):
        raise RuntimeError(
            f"silent block loss: accounted {block_drops + block_kept} "
            f"of {len(parsed.blocks)} blocks"
        )
    flush()

    # merge small chunks inside the same section (plan: chunks < 200 chars
    # merge into an ADJACENT chunk of the same section; the token cap keeps a
    # merge from pushing the result past HARD_MAX — _finalize_drafts must
    # never see merged markdown-carrying drafts)
    merged: list[Draft] = []
    for draft in drafts:
        if (
            merged
            and len(draft.text_md) < MERGE_MIN_CHARS
            and merged[-1].heading_path == draft.heading_path
            and count_tokens(merged[-1].text_md + "\n\n" + draft.text_md) <= HARD_MAX
        ):
            prev = merged[-1]
            merged[-1] = Draft(
                prev.text_md + "\n\n" + draft.text_md,
                (prev.plain + "\n\n" + draft.plain).strip(),
                prev.heading_path,
                prev.kinds | draft.kinds,
            )
        else:
            merged.append(draft)
    # trailing tiny chunk: merge backwards if same path
    while (
        len(merged) >= 2
        and len(merged[-1].text_md) < MERGE_MIN_CHARS
        and merged[-1].heading_path == merged[-2].heading_path
        and count_tokens(merged[-2].text_md + "\n\n" + merged[-1].text_md) <= HARD_MAX
    ):
        tail = merged.pop()
        prev = merged[-1]
        merged[-1] = Draft(
            prev.text_md + "\n\n" + tail.text_md,
            (prev.plain + "\n\n" + tail.plain).strip(),
            prev.heading_path,
            prev.kinds | tail.kinds,
        )
    # backward pass: a SMALL PREVIOUS chunk (e.g. a heading-only section
    # stub) merges into its same-section successor — the forward pass above
    # only handles "small next into prev", which left ~400 heading stubs
    # under 100 chars.
    fixed: list[Draft] = []
    i = 0
    while i < len(merged):
        d = merged[i]
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        if (
            nxt is not None
            and len(d.text_md) < MERGE_MIN_CHARS
            and d.heading_path == nxt.heading_path
            and count_tokens(d.text_md + "\n\n" + nxt.text_md) <= HARD_MAX
        ):
            merged[i + 1] = Draft(
                d.text_md + "\n\n" + nxt.text_md,
                (d.plain + "\n\n" + nxt.plain).strip(),
                nxt.heading_path,
                d.kinds | nxt.kinds,
            )
            i += 1
            continue
        fixed.append(d)
        i += 1
    merged = fixed

    # Cross-section merge (user-approved): remaining <MERGE_MIN_CHARS chunks
    # at section boundaries absorb into the adjacent chunk of the SAME
    # document (always true here — chunk_doc is per file). The host keeps
    # ITS heading_path; the stub's heading text stays inline in text_md.
    # Forward first (stub into previous host), then backward (stub into
    # next host); token cap HARD_MAX on every merge.
    i = 0
    while i < len(merged):
        d = merged[i]
        prv = merged[i - 1] if i > 0 else None
        if (
            prv is not None
            and len(d.text_md) < MERGE_MIN_CHARS
            and len(prv.text_md) >= MERGE_MIN_CHARS
            and not _is_empty_stub(d.text_md)
            and count_tokens(prv.text_md + "\n\n" + d.text_md) <= HARD_MAX
        ):
            merged[i - 1] = Draft(
                prv.text_md + "\n\n" + d.text_md,
                (prv.plain + "\n\n" + d.plain).strip(),
                prv.heading_path,
                prv.kinds | d.kinds,
            )
            merged.pop(i)
            continue
        i += 1
    i = 0
    while i < len(merged):
        d = merged[i]
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        if (
            nxt is not None
            and len(d.text_md) < MERGE_MIN_CHARS
            and len(nxt.text_md) >= MERGE_MIN_CHARS
            and not _is_empty_stub(d.text_md)
            and count_tokens(d.text_md + "\n\n" + nxt.text_md) <= HARD_MAX
        ):
            merged[i + 1] = Draft(
                d.text_md + "\n\n" + nxt.text_md,
                (d.plain + "\n\n" + nxt.plain).strip(),
                nxt.heading_path,
                d.kinds | nxt.kinds,
            )
            merged.pop(i)
            continue
        i += 1

    enforced, _oversize_atoms = _finalize_drafts(merged)
    enforced = _rescue_must_merge(enforced, {id(a) for a in _oversize_atoms})

    # doc-level stub rule (user-approved): a document whose ENTIRE kept
    # content is one draft under DROP_MIN_CHARS had no neighbor to merge
    # with — drop it as too_short so no sub-50 chunk can survive. Prose
    # drafts <50 are already caught by _drop_reason in the final loop; this
    # catches only drafts that length rules exempt (lists, numerics).
    if len(enforced) == 1:
        sole = enforced[0]
        if (
            len(sole.text_md.strip()) < DROP_MIN_CHARS
            and _drop_reason(sole.text_md, sole.kinds) is None
        ):
            drops.append(
                DropRecord(
                    "too_short", sole.text_md[:100], sole.heading_path,
                    sole.block_type, sole.text_md[:100_000],
                )
            )
            enforced = []

    non_english_doc, doc_likeness = doc_non_english(parsed)
    final: list[Draft] = []
    for draft in enforced:
        # empty_stub FIRST (condition 3): heading-only stubs are listed under
        # a single explicit reason so the gate can enumerate them
        reason: str | None
        if _is_empty_stub(draft.text_md):
            reason = "empty_stub"
        else:
            reason = _drop_reason(draft.text_md, draft.kinds)
            if (
                reason is None
                and not draft.oversize_justification
                and not _has_letter(draft.text_md)
                and any(ch.isdigit() for ch in draft.text_md)
            ):
                # Post-rescue letterless+digit residue ([***] 201802 [***]):
                # _rescue_must_merge already tried both neighbors and failed.
                # Keeping it emits a zero-alphabetic chunk (plan canary);
                # dropping it as no_alpha fails gate [09]. Honest reason:
                # junk (redaction markers + bare digits carry no content).
                reason = "junk_fragment"
        if not reason:
            if non_english_doc:
                reason = "non_english"
                preview = f"doc-likeness={doc_likeness:.3f} " + draft.text_md[:100]
                drops.append(
                    DropRecord(
                        reason, preview, draft.heading_path, draft.block_type,
                        draft.text_md[:100_000],
                    )
                )
                continue
            reason = mojibake_drop_reason(
                draft.text_md, draft.kinds, parsed.source_type
            )
            if reason:
                preview = f"ratio={mojibake_ratio(draft.text_md):.3f} " + draft.text_md[:100]
                drops.append(
                    DropRecord(
                        reason, preview, draft.heading_path, draft.block_type,
                        draft.text_md[:100_000],
                    )
                )
                continue
        if reason:
            drops.append(
                DropRecord(
                    reason,
                    draft.text_md[:120],
                    draft.heading_path,
                    draft.block_type,
                    draft.text_md[:100_000],
                )
            )
        else:
            final.append(draft)
    return final, drops
