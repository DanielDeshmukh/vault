"""Phase-2 dry-run for ingestion v2: build chunks + quality-gate report.

Reads corpus/manifest.jsonl, runs every file through ingestion_v2.pipeline,
writes JSONL outputs under corpus/v2_dryrun/ (gitignored via corpus/), and
prints the full gate report to stdout. NO embeddings, NO Pinecone, NO DB.

Usage:
    python server/scripts/ingest_v2.py [--limit N] [--seed 42] [--out DIR]
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"
sys.path.insert(0, str(REPO / "server"))

from bs4 import BeautifulSoup  # noqa: E402

from app.ingestion_v2.chunker import HARD_MAX, SOFT_MAX, fences_balanced  # noqa: E402
from app.ingestion_v2.htmlconv import _cleanup_soup, _mask, _restore  # noqa: E402
from app.ingestion_v2.pipeline import process_file  # noqa: E402

REQUIRED_RECORD_KEYS = {
    "chunk_id",
    "doc_id",
    "chunk_index",
    "source_path",
    "source_type",
    "doc_title",
    "heading_path",
    "block_type",
    "text_md",
    "text_embed",
    "token_count",
    "char_count",
    "content_hash",
    "department",
    "classification",
    "allowed_roles",
    "chunk_version",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s<>)\]\"']+")
PLACEHOLDER_RE = re.compile(r"<[A-Za-z][^<>\n]* [^<>\n]*>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SHORTCODE_RE = re.compile(r"\{\{[%<][\s\S]*?[%>]\}\}")
IFRAME_RE = re.compile(r"(?is)<iframe\b[\s\S]*?</iframe>")
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b[\s\S]*?</\1>")
IMG_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
HTML_TAGS = {
    "a", "abbr", "address", "article", "aside", "b", "blockquote", "br",
    "button", "caption", "cite", "code", "dd", "del", "details", "div",
    "dl", "dt", "em", "figcaption", "figure", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "img", "input", "ins", "kbd", "label",
    "li", "mark", "nav", "ol", "option", "p", "pre", "q", "s", "section",
    "select", "small", "span", "strong", "sub", "summary", "sup", "table",
    "tbody", "td", "textarea", "tfoot", "th", "thead", "time", "tr", "u",
    "ul", "video", "wbr",
}

IX_HIDDEN_RE = re.compile(r"(?is)<ix:hidden\b[^>]*>.*?</ix:hidden\s*>")
_A_OPEN_TAG_RE = re.compile(r"(?is)<a\b[^>]*>")
_AUTOLINK_TAG_RE = re.compile(r"(?is)<(?:https?|mailto):[^<>\s]+>")
WORD_RE = re.compile(r"[A-Za-z]{2,}")


# --------------------------------------------------- shared source-side logic
# gate_check imports these: the dry-run gate and the embedded canary scan must
# count exactly the same source regions or their verdicts drift.

def frontmatter_strip(raw: str) -> str:
    return re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|$)", "", raw, count=1, flags=re.S)


def design_scrub(text: str) -> str:
    """Drop design-only markdown regions: HTML comments, Hugo/custom
    shortcodes, iframes, script/style blocks, markdown images."""
    text = HTML_COMMENT_RE.sub(" ", text)
    text = SHORTCODE_RE.sub(" ", text)
    text = IFRAME_RE.sub(" ", text)
    text = SCRIPT_STYLE_RE.sub(" ", text)
    text = IMG_MD_RE.sub(" ", text)
    return text


def strip_design_html(text: str) -> str:
    """Remove non-anchor HTML tags from a token/URL source string.

    The renderer never emits attribute URLs of img/form/svg/... tags (they are
    masked as design markup), so the source side must not count them as
    content. Anchor hrefs, autolinks and <Marker Text> placeholders are
    content the parser keeps - they are protected through the strip.
    """
    keep: list[str] = []

    def _keep(match: re.Match[str]) -> str:
        keep.append(match.group(0))
        return f"\x00{len(keep) - 1}\x00"

    def _placeholder(match: re.Match[str]) -> str:
        token = match.group(0)
        if "=" in token or token[1:].split()[0].lower() in HTML_TAGS:
            return token  # tag-shaped: let HTML_TAG_RE strip it
        return _keep(match)

    text = PLACEHOLDER_RE.sub(_placeholder, text)
    text = _A_OPEN_TAG_RE.sub(_keep, text)
    text = _AUTOLINK_TAG_RE.sub(_keep, text)
    text = HTML_TAG_RE.sub(" ", text)
    for i, kept in enumerate(keep):
        text = text.replace(f"\x00{i}\x00", kept)
    return text


_FENCE_BLOCK_RE = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~")
_HIDDEN_TRIGGER_RE = re.compile(
    r"aria-hidden|\bdisplay\s*:\s*none|<(?:object|embed|noscript)\b", re.I
)


def drop_design_hidden(text: str) -> str:
    """Remove regions the parser decomposes silently (htmlconv._cleanup_soup):
    aria-hidden div/span/i subtrees, display:none elements, object/embed/
    noscript blocks. These leave no drop record, so without this the source
    side counts content no record can ever contain (e.g. a link inside a
    Bootstrap modal). Runs the parser's OWN soup cleanup (structure-aware,
    never regex-parsed), after masking code/autolinks/emails/fences/
    placeholders so they survive untouched.
    """
    if "<" not in text or not _HIDDEN_TRIGGER_RE.search(text):
        return text
    masked, saved = _mask(text)

    def stash(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return f"\x02ing:{len(saved) - 1}\x02"

    def stash_placeholder(match: re.Match[str]) -> str:
        token = match.group(0)
        if "=" in token or token[1:].split()[0].lower() in HTML_TAGS:
            return token
        return stash(match)

    masked = _FENCE_BLOCK_RE.sub(stash, masked)
    masked = PLACEHOLDER_RE.sub(stash_placeholder, masked)
    soup = BeautifulSoup(masked, "html.parser")
    _cleanup_soup(soup)
    out = str(soup)
    for _ in range(3):  # restore outer stashes first (fences may nest inner)
        out = _restore(out, saved)
        if "\x02ing:" not in out:
            break
    return out


def source_tokens_text(raw: str, ext: str) -> str:
    """Source string for token/URL/placeholder comparison.

    md/txt: frontmatter + design regions stripped, then non-anchor tags
    stripped (anchors/autolinks/placeholders protected). htm/html: script/
    style, comments and ix:hidden regions stripped, then all tags stripped.
    """
    if ext in {".md", ".txt"}:
        text = design_scrub(frontmatter_strip(raw))
        text = drop_design_hidden(text)
        return strip_design_html(text)
    text = SCRIPT_STYLE_RE.sub(" ", raw)
    text = HTML_COMMENT_RE.sub(" ", text)
    text = IX_HIDDEN_RE.sub(" ", text)
    text = drop_design_hidden(text)
    return html.unescape(HTML_TAG_RE.sub(" ", text))


def md_normalize_source(raw: str) -> str:
    """Char/word comparison source: design regions and ALL tags removed."""
    text = frontmatter_strip(raw)
    text = design_scrub(text)
    text = drop_design_hidden(text)
    text = HTML_TAG_RE.sub(" ", text)
    return html.unescape(text)


def norm_tok(tok: str) -> str:
    # markdown-it escapes specials in hrefs (\>, \(, \.) and percent-encodes
    # brackets; unwrap both forms so source and record tokens compare equal.
    unescaped = re.sub(r"\\(.)", r"\1", tok)
    return html.unescape(unescaped).replace("\\_", "_")


def norm_url(url: str) -> str:
    """Unquote + terminator normalization, NO prefix matching.

    Returns '' for scheme-only leftovers: a bare 'https://' (e.g. a table cell
    like 'DO NOT include https://|' once '|' is cut) is a corpus artefact,
    never a real link, and records can never produce it.
    """
    u = html.unescape(url)
    u = urllib.parse.unquote(u)
    u = norm_tok(u)
    # a raw '|' immediately after a URL is a markdown-table cell separator
    # (or a legend suffix like "...|Full|"), never part of the URL itself
    u = u.split("|", 1)[0].rstrip(URL_TERMINATORS)
    if u.lower() in {"http://", "https://"}:
        return ""
    return u


def placeholders_of(text: str) -> set[str]:
    return {
        m
        for m in PLACEHOLDER_RE.findall(text)
        if "=" not in m and m[1:].split()[0].lower() not in HTML_TAGS
    }


def tokens_of(text: str, *, with_urls: bool) -> set[str]:
    found = {norm_tok(m) for m in EMAIL_RE.findall(text)}
    found |= {norm_tok(m) for m in placeholders_of(text)}
    if with_urls:
        # unquote the TEXT first: records store hrefs percent-encoded
        # (%5B%5D) while source has literal brackets; URL_RE stops at ']', so
        # both sides must see the same literal form before extraction.
        decoded = urllib.parse.unquote(text)
        found |= {u for m in URL_RE.findall(decoded) if (u := norm_url(m))}
    return found


def word_retention(
    src_words: set[str], out_words: set[str], drop_words: set[str],
) -> tuple[float, float, int, int]:
    """(raw_retention, effective_retention, missing, unaccounted)."""
    if not src_words:
        return 1.0, 1.0, 0, 0
    missing = src_words - out_words
    unaccounted = missing - drop_words
    raw = len(src_words & out_words) / len(src_words)
    effective = 1.0 - len(unaccounted) / len(src_words)
    return raw, effective, len(missing), len(unaccounted)


URL_TERMINATORS = ".,;:!?)]}'\"<>\\*`~_"


def load_manifest() -> list[dict]:
    entries: list[dict] = []
    with (CORPUS / "manifest.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def skip_reason(entry: dict) -> str | None:
    rel = str(entry["path"]).replace("\\", "/")
    if rel.lower().endswith(".pdf") and "/cuad/" in f"/{rel.lower()}":
        return "cuad_pdf_paired_txt"
    if not (CORPUS / rel).is_file():
        return "missing_file"
    return None


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="process only first N eligible files")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(CORPUS / "v2_dryrun"))
    ap.add_argument(
        "--report",
        default="",
        help="write the gate report to this UTF-8 file instead of stdout "
        "(stdout via PowerShell mangles UTF-8 into OEM codepage mojibake)",
    )
    args = ap.parse_args()

    if args.report:
        sys.stdout = open(args.report, "w", encoding="utf-8", newline="\n")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = load_manifest()

    counters: Counter[str] = Counter()
    doc_id_of: dict[str, str] = {}
    for e in entries:
        dept = str(e.get("department") or "general")
        counters[dept] += 1
        doc_id_of[str(e["path"]).replace("\\", "/")] = f"doc_{dept}_{counters[dept]:04d}"

    records_path = out_dir / "records.jsonl"
    drops_path = out_dir / "drops.jsonl"
    stats_path = out_dir / "stats.json"

    drop_counter: Counter[str] = Counter()
    drop_type_counter: Counter[str] = Counter()  # "reason | block_type"
    dept_files: Counter[str] = Counter()
    dept_chunks: Counter[str] = Counter()
    dept_tokens: Counter[str] = Counter()
    dept_zero_files: Counter[str] = Counter()
    token_counts: list[int] = []
    all_records: list[dict] = []
    oversize_atoms: list[dict] = []
    skipped_counter: Counter[str] = Counter()
    parse_errors: list[tuple[str, str]] = []
    processed_rels: list[str] = []
    source_md: dict[str, list[str]] = {}
    apple_table_chunk: dict | None = None
    cuad_chunks = 0
    cuad_title_hit = 0
    apple_item_paths: set[str] = set()
    labour_kept = 0
    labour_non_english_drops = 0
    per_file_secs: list[tuple[float, str]] = []
    drop_spans: dict[str, tuple[int, int]] = {}

    t0 = time.time()
    processed = 0
    limit = args.limit or len(entries)

    with records_path.open("w", encoding="utf-8") as records_fh, \
            drops_path.open("w", encoding="utf-8") as drops_fh:
        for entry in entries:
            if processed >= limit:
                break
            rel = str(entry["path"]).replace("\\", "/")
            drop_start = drops_fh.tell()
            skip = skip_reason(entry)
            if skip:
                skipped_counter[skip] += 1
                drops_fh.write(json.dumps({
                    "source_path": rel,
                    "doc_id": None,
                    "reason": skip,
                    "preview": "",
                    "heading_path": [],
                }, ensure_ascii=False) + "\n")
                continue

            doc_id = doc_id_of[rel]
            dept = str(entry.get("department") or "general")
            file_t0 = time.time()
            try:
                records, drops, meta = process_file(CORPUS / rel, entry, doc_id)
            except Exception as exc:  # noqa: BLE001 - dry-run must survive bad files
                skipped_counter["parse_error"] += 1
                parse_errors.append((rel, str(exc)[:300]))
                drops_fh.write(json.dumps({
                    "source_path": rel,
                    "doc_id": doc_id,
                    "reason": "parse_error",
                    "preview": str(exc)[:200],
                    "heading_path": [],
                }, ensure_ascii=False) + "\n")
                continue
            per_file_secs.append((time.time() - file_t0, rel))

            dept_files[dept] += 1
            dept_chunks[dept] += len(records)
            dept_tokens[dept] += sum(r.token_count for r in records)
            if not records:
                dept_zero_files[dept] += 1
            processed_rels.append(rel)
            source_md[rel] = [r.text_md for r in records]

            for r in records:
                d = r.to_dict()
                all_records.append(d)
                token_counts.append(r.token_count)
                records_fh.write(json.dumps(
                    {"id": r.chunk_id, "metadata": d, "values": []},
                    ensure_ascii=False,
                ) + "\n")
                if r.source_path.startswith("legal/cuad/"):
                    cuad_chunks += 1
                    if r.doc_title and r.doc_title.lower() in r.text_embed[:300].lower():
                        cuad_title_hit += 1
                if r.source_path.startswith("finance/sec_10k/"):
                    for hp in r.heading_path:
                        if hp.lower().startswith("item "):
                            apple_item_paths.add(hp)
                if (r.source_path.startswith("finance/sec_10k/")
                        and r.block_type in ("table", "mixed")
                        and sum(1 for ln in r.text_md.splitlines() if ln.count("|") >= 3) >= 6
                        and ("Net sales" in r.text_md or "Gross margin" in r.text_md
                             or "In millions" in r.text_md or "Adjusted" in r.text_md)):
                    score = (
                        (100 if "apple_10k" in r.source_path else 0)
                        + (50 if "Net sales" in r.text_md else 0)
                        + sum(1 for ln in r.text_md.splitlines() if ln.count("|") >= 3)
                    )
                    if apple_table_chunk is None or score > apple_table_chunk["_score"]:
                        chunk_dict = d
                        chunk_dict["_score"] = score
                        apple_table_chunk = chunk_dict
                if r.source_path.startswith("hr/direct/") and r.source_type == "pdf":
                    labour_kept += 1

            for atom in meta["oversize_atoms"]:
                atom["source_path"] = rel
                atom["doc_id"] = doc_id
                oversize_atoms.append(atom)

            for dr in drops:
                if dr.reason in {"mojibake_suspect", "non_english"} and rel.startswith("hr/direct/"):
                    labour_non_english_drops += 1
                drop_counter[dr.reason] += 1
                drop_type_counter[f"{dr.reason} | {dr.block_type}"] += 1
                drops_fh.write(json.dumps({
                    "source_path": rel,
                    "doc_id": doc_id,
                    "reason": dr.reason,
                    "block_type": dr.block_type,
                    "preview": dr.preview[:200],
                    "text": dr.text[:100_000],
                    "heading_path": dr.heading_path,
                }, ensure_ascii=False) + "\n")
            drop_spans[rel] = (drop_start, drops_fh.tell())

            processed += 1
            if processed % 250 == 0 or processed >= 4450:
                print(
                    f"... {processed} files / {len(all_records)} chunks "
                    f"({time.time() - t0:.0f}s)",
                    file=sys.stderr,
                    flush=True,
                )

    print(
        f"[phase] ingest loop complete: {processed} files",
        file=sys.stderr,
        flush=True,
    )

    # ---------------- canaries (in-memory + light reprocessing)
    print("[phase] canaries: sampling", file=sys.stderr, flush=True)
    canaries: list[tuple[str, bool, str]] = []

    rng = random.Random(args.seed)
    sample_depts: dict[str, list[dict]] = defaultdict(list)
    for d in all_records:
        sample_depts[d["department"]].append(d)
    sample: list[dict] = []
    total = len(all_records)
    for dept, recs in sorted(sample_depts.items()):
        want = max(2, round(30 * len(recs) / total)) if total else 0
        want = min(want, len(recs))
        sample.extend(rng.sample(recs, want))
    sample = sample[:30] if len(sample) >= 30 else sample
    while len(sample) < 30 and total > len(sample):
        extra = [d for d in all_records if d not in sample]
        sample.append(rng.choice(extra))

    # 1. schema validation
    bad_schema = 0
    oversize_ids = {a["doc_id"] for a in oversize_atoms}
    for d in all_records:
        if not REQUIRED_RECORD_KEYS.issubset(d.keys()):
            bad_schema += 1
        elif d["token_count"] > HARD_MAX and d["doc_id"] not in oversize_ids:
            bad_schema += 1
    canaries.append((
        "schema_valid (keys + <=HARD_MAX or justified atom)",
        bad_schema == 0,
        f"{bad_schema} violations / {total} records",
    ))

    # 2. determinism: reprocess up to 5 already-processed files, compare ids+hashes
    print("[phase] canaries: determinism", file=sys.stderr, flush=True)
    first_files = []
    seen = set()
    for entry in entries:
        rel = str(entry["path"]).replace("\\", "/")
        if rel in seen or skip_reason(entry):
            continue
        seen.add(rel)
        first_files.append(entry)
        if len(first_files) >= 5:
            break
    det_ok = True
    det_note = ""
    orig_by_path = defaultdict(list)
    for d in all_records:
        orig_by_path[d["source_path"]].append((d["chunk_id"], d["content_hash"]))
    for entry in first_files:
        rel = str(entry["path"]).replace("\\", "/")
        try:
            recs2, _, _ = process_file(CORPUS / rel, entry, doc_id_of[rel])
        except Exception as exc:  # noqa: BLE001
            det_ok = False
            det_note = f"reprocess error {rel}: {exc}"
            break
        seq2 = [(r.chunk_id, r.content_hash) for r in recs2]
        if seq2 != orig_by_path.get(rel, []):
            det_ok = False
            det_note = f"mismatch on {rel}"
            break
    canaries.append((
        "determinism (5-file reprocess)",
        det_ok,
        det_note or f"{len(first_files)} files identical",
    ))

    # 3. junk is dropped, not embedded
    junk_drops = drop_counter.get("junk_fragment", 0) + drop_counter.get("no_alpha", 0) + drop_counter.get("too_short", 0)
    canaries.append((
        "junk_fragment/no_alpha/too_short dropped",
        junk_drops > 0,
        f"{junk_drops} junk candidates dropped",
    ))

    # 4. Apple 10-K Item paths promoted
    canaries.append((
        "apple_10k Item headings promoted (>=2 distinct)",
        len(apple_item_paths) >= 2,
        f"{sorted(apple_item_paths)[:6]}",
    ))

    # 5. CUAD title in text_embed
    frac = (cuad_title_hit / cuad_chunks) if cuad_chunks else 0.0
    canaries.append((
        "cuad title-in-embed >= 90%",
        frac >= 0.90,
        f"{cuad_title_hit}/{cuad_chunks} = {frac:.1%}",
    ))

    # 6. labour PDF: clean kept AND garbage quarantined
    canaries.append((
        "labour_pdf split: clean kept + garbage quarantined",
        labour_kept > 0 and labour_non_english_drops > 0,
        f"{labour_kept} kept, {labour_non_english_drops} mojibake/non_english drops",
    ))

    # 7. oversize atoms are justified, nothing unjustified over HARD_MAX
    unjustified = [d for d in all_records if d["token_count"] > HARD_MAX and d["doc_id"] not in oversize_ids]
    canaries.append((
        f"oversize: every chunk >{HARD_MAX} tok is a justified atom",
        not unjustified,
        f"{len(oversize_atoms)} justified atoms, {len(unjustified)} unjustified over {HARD_MAX}",
    ))

    # ---- plan quality-gate conditions (plan lines 87-93) ----

    # 8a. chunks under 50 chars = 0 (gate)
    under50 = [d for d in all_records if d["char_count"] < 50]
    canaries.append((
        "chunks under 50 chars = 0 (gate)",
        not under50,
        f"{len(under50)} found"
        + (f" e.g. {under50[0]['chunk_id']} {under50[0]['text_md'][:40]!r}" if under50 else ""),
    ))

    # 8b. chunks under 100 chars: < 1% excluding tables and code (a one-row
    # table or single-line fence is legitimately tiny; user-approved gate).
    short_elig = [
        d for d in all_records
        if d["char_count"] < 100 and d["block_type"] not in {"table", "code"}
    ]
    short_n = len(short_elig)
    short_frac = short_n / total if total else 0.0
    canaries.append((
        "chunks under 100 chars < 1% excluding tables/code (gate)",
        short_frac < 0.01,
        f"{short_n}/{total} = {short_frac:.2%}",
    ))

    # 9. chunks with zero alphabetic words: 0
    zero_alpha = sum(1 for d in all_records if not re.search(r"[A-Za-z]", d["text_md"]))
    canaries.append((
        "chunks with zero alphabetic words = 0 (plan)",
        zero_alpha == 0,
        f"{zero_alpha} found",
    ))

    # 10. no text_embed repeated more than 3 times
    print("[phase] canaries: embed dup + fences", file=sys.stderr, flush=True)
    embed_counts = Counter(d["text_embed"] for d in all_records)
    dup_embed, dup_count = embed_counts.most_common(1)[0] if embed_counts else ("", 0)
    canaries.append((
        "text_embed max duplication <= 3 (plan)",
        dup_count <= 3,
        f"max x{dup_count}: {dup_embed[:70]!r}",
    ))

    # 11. department/classification/allowed_roles populated from the manifest
    missing_meta = sum(
        1
        for d in all_records
        if not d.get("department") or not d.get("classification") or not d.get("allowed_roles")
    )
    canaries.append((
        "department/classification/allowed_roles populated (plan)",
        missing_meta == 0,
        f"{missing_meta} records with empty metadata",
    ))

    # 12. every record's fences close inside text_md (plan). Semantic check,
    # not a line-toggle: source fences legitimately CONTAIN ```-looking lines
    # ("```markdown" with info, deeper-indented clean markers) that a naive
    # toggle counts as closers.
    unbalanced = [
        d["chunk_id"]
        for d in all_records
        if not fences_balanced(d["text_md"])
    ]
    canaries.append((
        "fences balanced in 100% of text_md (plan)",
        not unbalanced,
        f"{len(unbalanced)} unbalanced: {unbalanced[:4]}",
    ))

    # 13/14. tokens preserved vs source; per-doc char/word loss (user-approved
    # gate). Scope: text-based sources only (.md/.txt/.htm/.html). Counted with
    # the SAME shared helpers gate_check imports: design regions, non-anchor
    # HTML tag attributes (img/form/svg) and ix:hidden/comment URLs are not
    # content, while anchor hrefs, autolinks and <Marker Text> placeholders
    # are. Token and retention counts are drop-accounted (content in a doc's
    # dropped text is not "lost"). Char collapse >20% is report-only WARN
    # (user-approved); word retention >= 95% in >= 99% of docs is hard.

    def _drop_texts_for(rel: str) -> list[str]:
        span = drop_spans.get(rel)
        if not span:
            return []
        start, end = span
        if end <= start:
            return []
        with drops_path.open("rb") as fh:
            fh.seek(start)
            chunk = fh.read(end - start).decode("utf-8", errors="replace")
        texts: list[str] = []
        for line in chunk.splitlines():
            line = line.strip()
            if line:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                texts.append(d.get("text") or d.get("preview") or "")
        return texts

    loss_flagged: list[tuple[str, int, int, float, float]] = []
    word_flagged: list[tuple[str, float, int, int, str, str]] = []
    lost_tokens: dict[str, list[tuple[str, str]]] = defaultdict(list)
    source_docs_scanned = 0
    print(
        f"[phase] source-loss scan: {len(processed_rels)} rels",
        file=sys.stderr,
        flush=True,
    )
    for rel in processed_rels:
        ext = Path(rel).suffix.lower()
        if ext not in {".md", ".txt", ".htm", ".html"}:
            continue
        try:
            raw = (CORPUS / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        src_text = source_tokens_text(raw, ext)
        src_norm = md_normalize_source(raw) if ext in {".md", ".txt"} else src_text
        out_text = "\n".join(source_md.get(rel, []))
        drop_texts = _drop_texts_for(rel)
        source_docs_scanned += 1

        src_chars = len(src_norm.strip())
        out_chars = len(out_text.strip())
        if src_chars and any(c.isalpha() for c in src_norm):
            loss = 1.0 - out_chars / src_chars
            drop_chars = sum(len(t.strip()) for t in drop_texts)
            gap = max(0, src_chars - out_chars)
            unexp = max(0, gap - drop_chars) / src_chars
            if loss > 0.20:
                loss_flagged.append((rel, src_chars, out_chars, loss, unexp))

        with_urls = ext in {".md", ".txt"}
        if ext in {".md", ".txt"}:
            src_words = set(WORD_RE.findall(src_norm.lower()))
            out_words = set(WORD_RE.findall(out_text.lower()))
            drop_words: set[str] = set()
            for t in drop_texts:
                drop_words |= set(WORD_RE.findall(t.lower()))
            if src_words:
                raw_r, eff_r, n_miss, n_unacc = word_retention(
                    src_words, out_words, drop_words,
                )
                del raw_r, n_miss
                if eff_r < 0.95:
                    word_flagged.append((
                        rel, eff_r, len(src_words), n_unacc,
                        " ".join(src_norm.split())[:180],
                        " ".join(out_text.split())[:180],
                    ))

        drop_toks: set[str] = set()
        for t in drop_texts:
            drop_toks |= tokens_of(t, with_urls=with_urls)
        lost = (
            tokens_of(src_text, with_urls=with_urls)
            - tokens_of(out_text, with_urls=with_urls)
            - drop_toks
        )
        for tok in sorted(lost):
            if EMAIL_RE.fullmatch(tok):
                kind = "emails"
            elif tok.startswith("<"):
                kind = "placeholders"
            else:
                kind = "autolinks"
            lost_tokens[kind].append((rel, tok))

    print(
        f"[phase] source-loss scan complete: {source_docs_scanned} scanned",
        file=sys.stderr,
        flush=True,
    )

    lost_total = sum(len(v) for v in lost_tokens.values())
    lost_detail = "; ".join(
        f"{kind}: {len(items)} (e.g. {items[0][0]} {items[0][1][:50]!r})"
        for kind, items in sorted(lost_tokens.items())
        if items
    ) or "none"
    canaries.append((
        "0 autolinks/emails/placeholders lost vs source "
        "(design regions/non-anchor tags/ix:hidden excluded; drop-accounted)",
        lost_total == 0,
        f"{lost_total} lost across {source_docs_scanned} text docs — {lost_detail}",
    ))
    canaries.append((
        "char-loss >20% per doc: WARN report-only "
        "(word retention is the hard condition, user-approved)",
        True,
        f"{len(loss_flagged)} docs >20% raw loss of {source_docs_scanned} "
        f"scanned (listed below)",
    ))
    word_fail_frac = len(word_flagged) / source_docs_scanned if source_docs_scanned else 0.0
    canaries.append((
        "word retention >= 95% in >= 99% of md/txt docs (drop-accounted)",
        word_fail_frac < 0.01,
        f"{len(word_flagged)} docs below 95% of {source_docs_scanned} "
        f"scanned = {word_fail_frac:.2%}",
    ))

    elapsed = time.time() - t0
    sorted_tokens = sorted(token_counts)
    gate_pass = all(ok for _, ok, _ in canaries)
    slowest = sorted(per_file_secs, reverse=True)[:5]
    stub_counts = Counter(
        " ".join(d["text_md"].split())[:120] for d in short_elig
    )

    # ---------------- stats.json
    stats = {
        "manifest_entries": len(entries),
        "processed": processed,
        "skipped": dict(skipped_counter),
        "chunks": total,
        "tokens_total": sum(token_counts),
        "token_stats": {
            "min": min(token_counts) if token_counts else 0,
            "p50": percentile(sorted_tokens, 0.50),
            "p90": percentile(sorted_tokens, 0.90),
            "max": max(token_counts) if token_counts else 0,
        },
        "drop_reasons": dict(drop_counter),
        "drop_reasons_by_type": dict(drop_type_counter),
        "oversize_atoms": len(oversize_atoms),
        "oversize_atoms_list": oversize_atoms,
        "per_department": {
            dept: {
                "files": dept_files[dept],
                "chunks": dept_chunks[dept],
                "tokens": dept_tokens[dept],
                "zero_chunk_files": dept_zero_files[dept],
            }
            for dept in sorted(dept_files)
        },
        "canaries": [
            {"name": name, "pass": ok, "detail": detail}
            for name, ok, detail in canaries
        ],
        "gate_pass": gate_pass,
        "elapsed_seconds": round(elapsed, 1),
        "source_checks": {
            "docs_scanned": source_docs_scanned,
            "lost_tokens": {kind: len(v) for kind, v in sorted(lost_tokens.items())},
            "lost_examples": {
                kind: v[:20] for kind, v in sorted(lost_tokens.items()) if v
            },
            "lost_all": {
                kind: v for kind, v in sorted(lost_tokens.items()) if v
            },
            "loss_flagged_docs": [
                {
                    "path": rel,
                    "src_chars": s,
                    "out_chars": o,
                    "loss_pct": round(pct, 3),
                    "unexplained_pct": round(unexp, 3),
                }
                for rel, s, o, pct, unexp in sorted(
                    loss_flagged, key=lambda t: -t[3]
                )
            ],
            "word_flagged_docs": [
                {
                    "path": rel,
                    "retained_effective": round(ret, 4),
                    "src_words": n_src,
                    "unaccounted_words": n_unacc,
                    "src_head": s_head,
                    "out_head": o_head,
                }
                for rel, ret, n_src, n_unacc, s_head, o_head in sorted(
                    word_flagged, key=lambda t: t[1]
                )[:25]
            ],
        },
        "short_stubs": [
            {"count": n, "text": text} for text, n in stub_counts.most_common(20)
        ],
        "slowest_files": [
            {"seconds": round(s, 1), "path": rel} for s, rel in slowest
        ],
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("[phase] stats written; rendering report", file=sys.stderr, flush=True)

    # ---------------- stdout report
    print("=" * 78)
    print("INGESTION v2 DRY-RUN GATE REPORT")
    print("=" * 78)
    print(f"manifest entries : {len(entries)}")
    print(f"processed files  : {processed}")
    print(f"skipped          : {dict(skipped_counter)}")
    if parse_errors:
        print("parse errors:")
        for rel, err in parse_errors[:10]:
            print(f"  - {rel}: {err}")
    print(f"chunks written   : {total}  ->  {records_path}")
    print(f"drops written    : {sum(drop_counter.values())} (+ {sum(skipped_counter.values())} file-level)  ->  {drops_path}")
    print(f"tokens total     : {sum(token_counts)}")
    if token_counts:
        print(
            f"tokens per chunk : min={min(token_counts)} "
            f"p50={percentile(sorted_tokens, 0.50)} "
            f"p90={percentile(sorted_tokens, 0.90)} "
            f"max={max(token_counts)}  (target {SOFT_MAX}, hard max {HARD_MAX})"
        )
    print(f"elapsed          : {elapsed:.1f}s")

    print("\n--- per-department coverage ---")
    print(f"{'dept':<14} {'files':>7} {'chunks':>8} {'tokens':>10} {'zero-chunk':>11}")
    for dept in sorted(dept_files):
        print(
            f"{dept:<14} {dept_files[dept]:>7} {dept_chunks[dept]:>8} "
            f"{dept_tokens[dept]:>10} {dept_zero_files[dept]:>11}"
        )
    print(
        f"{'TOTAL':<14} {sum(dept_files.values()):>7} {sum(dept_chunks.values()):>8} "
        f"{sum(dept_tokens.values()):>10} {sum(dept_zero_files.values()):>11}"
    )

    print("\n--- drop-reason histogram ---")
    for reason, count in drop_counter.most_common():
        print(f"  {reason:<28} {count:>7}")
    print("\n--- drop-reason histogram (reason | block type) ---")
    for key, count in drop_type_counter.most_common():
        print(f"  {key:<36} {count:>7}")

    print(f"\n--- oversize atoms (kept + justified): {len(oversize_atoms)} ---")
    for atom in oversize_atoms:
        print(
            f"  {atom['doc_id']} tok={atom['tokens']} "
            f"why={atom['justification']!r} head={atom['preview'][:60]!r}"
        )

    print("\n--- slowest files (top 5) ---")
    for s, rel in slowest:
        print(f"  {s:7.1f}s  {rel}")

    print("\n--- short stubs (<100 chars, excl. tables/code): top 20 by frequency ---")
    for text, n in stub_counts.most_common(20):
        print(f"  x{n:<4} {text[:110]!r}")

    print("\n--- canaries ---")
    for name, ok, detail in canaries:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}: {detail}")
    print(f"\nGATE: {'PASS' if gate_pass else 'FAIL'}")

    if lost_total:
        print("\n--- lost tokens vs source (top) ---")
        for kind, items in sorted(lost_tokens.items()):
            for rel, tok in items[:15]:
                print(f"  {kind:<13} {rel}: {tok[:90]!r}")
        for kind in ("emails", "placeholders"):
            items = lost_tokens.get(kind) or []
            if items:
                print(f"\n--- ALL lost {kind} ({len(items)}) ---")
                for rel, tok in items:
                    print(f"  {rel}: {tok[:90]!r}")
    if loss_flagged:
        print("\n--- docs flagged >20% normalized char loss "
              "(WARN report-only; top 25 by loss) ---")
        for rel, s, o, pct, unexp in sorted(loss_flagged, key=lambda t: -t[3])[:25]:
            print(f"  {pct:6.1%} (unexp {unexp:5.1%})  {rel}  src={s:,} out={o:,}")
    if word_flagged:
        print("\n--- 10 worst docs by effective word retention (side-by-side) ---")
        for rel, ret, n_src, n_unacc, s_head, o_head in sorted(
            word_flagged, key=lambda t: t[1]
        )[:10]:
            print(f"  {rel}  effective={ret:.1%}  unaccounted={n_unacc}/{n_src} words")
            print(f"    src: {s_head!r}")
            print(f"    out: {o_head!r}")
        print(f"\n  ({len(word_flagged)} docs total below 95% word retention)")

    # ---------------- sampled 30 chunks
    print("\n" + "=" * 78)
    print(f"SAMPLED {len(sample)} CHUNKS (seed={args.seed}, stratified by department)")
    print("=" * 78)
    for i, d in enumerate(sample, 1):
        preview = " ".join(d["text_md"].split())[:500]
        print(f"\n[{i:02d}] {d['chunk_id']}  ({d['department']} / {d['source_type']} / {d['token_count']} tok)")
        print(f"     path: {' > '.join(d['heading_path']) or '(none)'}")
        print(f"     {preview}")

    # ---------------- rendered 10-K financial table chunk
    print("\n" + "=" * 78)
    print("RENDERED 10-K FINANCIAL TABLE CHUNK (text_md, up to 1500 chars)")
    print("=" * 78)
    if apple_table_chunk:
        print(f"chunk: {apple_table_chunk['chunk_id']}  ({apple_table_chunk['token_count']} tok, "
              f"{apple_table_chunk['block_type']})")
        print("path :", " > ".join(apple_table_chunk["heading_path"]) or "(none)")
        print("-" * 78)
        print(apple_table_chunk["text_md"][:1500])
    else:
        print("NOT FOUND — no chunk contained 'Adjusted Cost'/'Net sales' + '|'")

    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
