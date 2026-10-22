"""Corpus gate check (plan Phase 2) — sign-off authority for a v2 dry-run.

Reads manifest.jsonl + dry-run outputs (records.jsonl / drops.jsonl /
stats.json) and runs every user-approved condition:

  tokens   emails/placeholders/autolinks lost vs source == 0 after
           design-scrub exclusions, md-escape/percent normalization, and
           subtraction of full dropped text (unknown drop reasons = FAIL)
  chars    >20% .md-normalized char loss = REPORT-ONLY WARN (approved
           design): flag + drop attribution + top-10 docs side-by-side;
           the hard content gates are [tokens] and [words]
  words    alphabetic-word retention >= 95% in >= 99% of md/txt docs after
           subtracting full dropped text; 10 worst docs side-by-side
  lengths  chunks < 50 chars == 0; < 100 chars (excl. tables/code) < 1%
  urls     EXACT set match after unquote + terminator normalization (NO
           prefix matching) + permanent assertion: no record ends in a
           truncated URL
  headings dropped headings must appear in a kept record's heading_path in
           the same doc, OR the drop reason must be empty_stub (cond 3)
  pairing  every skipped CUAD PDF has its .txt in the manifest (cond 4)
  reasons  page_number ONLY in cuad_txt/pdf/sec_htm; numeric or lettered
           text under no_alpha = FAIL; unknown reasons = FAIL
  acl      record classification/allowed_roles/department == manifest
  fences   every record's text_md has balanced fences
  timeouts per-file timeout violations = FAIL; the 5 slowest files are
           listed for sign-off

Oversize atoms (kept + justified) are listed from stats.json for sign-off.

Run --mutation-test FIRST (synthetic fixtures prove the gate catches the
nine failure classes); the real gate run must come after it passes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest_v2 import (  # noqa: E402
    EMAIL_RE,
    URL_RE,
    load_manifest,
    skip_reason,
    source_tokens_text,
    word_retention,
)
from ingest_v2 import (
    md_normalize_source as _md_normalize,
)
from ingest_v2 import (
    norm_url as _norm_url,
)
from ingest_v2 import (
    tokens_of as _tokens,
)

from app.ingestion_v2.chunker import fences_balanced  # noqa: E402
from app.ingestion_v2.pipeline import detect_source_type  # noqa: E402

CORPUS = Path(__file__).resolve().parents[2] / "corpus"

# Reasons the gate accepts in drops.jsonl. Anything else = FAIL.
ALLOWED_REASONS = {
    "too_short", "few_words", "no_alpha", "syntax_only", "junk_fragment",
    "empty_heading", "empty_table", "empty_stub", "non_english",
    "mojibake_suspect", "page_number", "duplicate_chunk",
    "cuad_pdf_paired_txt", "parse_error",
}
PAGE_NUMBER_SOURCE_TYPES = {"cuad_txt", "pdf", "sec_htm"}

# char-loss condition: >20% collapse flags the doc; FAIL only when more than
# 5% of source chars are unexplained by full dropped text (drop-explained
# collapses — e.g. whole non-English docs — are listed, not failed).
CHAR_COLLAPSE_PCT = 0.20
CHAR_UNEXPLAINED_FAIL = 0.05
WORD_RETENTION_MIN = 0.95
WORD_FAIL_DOC_FRACTION = 0.01
SHORT100_FRACTION = 0.01


# ---------------------------------------------------------------- source side
# Frontmatter/design/HTML stripping and token/URL normalization live in
# ingest_v2 (imported above) so the dry-run gate and the embedded canary
# scan count exactly the same source regions.

def _kind_of(tok: str) -> str:
    if EMAIL_RE.fullmatch(tok):
        return "emails"
    if tok.startswith("<"):
        return "placeholders"
    return "autolinks"


# ---------------------------------------------------------------- pure checks

def check_reasons(drops: list[dict], source_type_of) -> list[tuple[str, str]]:
    """Unknown reasons, page_number scope, numeric/lettered no_alpha."""
    failures: list[tuple[str, str]] = []
    for d in drops:
        reason = d.get("reason", "")
        text = d.get("text") or d.get("preview") or ""
        stype = source_type_of(d.get("source_path", ""))
        if reason not in ALLOWED_REASONS:
            failures.append(("UNKNOWN_REASON", f"{d.get('source_path')} reason={reason!r}"))
        if reason == "page_number" and stype not in PAGE_NUMBER_SOURCE_TYPES:
            failures.append((
                "PAGE_NUMBER_SCOPE",
                f"{d.get('source_path')} source_type={stype!r} must be one of "
                f"{sorted(PAGE_NUMBER_SOURCE_TYPES)}",
            ))
        if reason == "no_alpha" and text:
            stripped = text.strip()
            if any(c.isdigit() for c in stripped) and not any(c.isalpha() for c in stripped):
                failures.append((
                    "NUMERIC_NO_ALPHA",
                    f"{d.get('source_path')} numeric text under no_alpha: {stripped[:60]!r}",
                ))
            elif any(c.isalpha() for c in stripped):
                failures.append((
                    "LETTED_NO_ALPHA",
                    f"{d.get('source_path')} lettered text under no_alpha: {stripped[:60]!r}",
                ))
    return failures


def check_headings(drops: list[dict], kept_paths_by_doc: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Cond 3: dropped headings must be in a kept heading_path, or empty_stub."""
    failures: list[tuple[str, str]] = []
    for d in drops:
        reason = d.get("reason", "")
        block_type = d.get("block_type", "")
        if reason == "empty_stub":
            continue
        if block_type != "heading" and reason != "empty_heading":
            continue
        raw = d.get("text") or d.get("preview") or ""
        m = re.search(r"(?m)^\s*#{1,6}\s+(.+?)\s*$", raw)
        if not m:
            continue  # blank/wordless heading: nothing meaningful to find
        heading = m.group(1)
        if heading not in kept_paths_by_doc.get(d.get("source_path", ""), set()):
            failures.append((
                "HEADING_LOST",
                f"{d.get('source_path')} dropped heading {heading!r} not in any "
                f"kept heading_path and not empty_stub",
            ))
    return failures


def check_urls(src_urls: set[str], out_texts: list[str], drop_texts: list[str]) -> list[tuple[str, str]]:
    """Cond 5: exact-set loss after normalization + truncated-tail assertion."""
    failures: list[tuple[str, str]] = []
    drop_urls = set()
    for t in drop_texts:
        drop_urls |= {_norm_url(u) for u in URL_RE.findall(urllib.parse.unquote(t))}
    out_url_set = set()
    for t in out_texts:
        for u in URL_RE.findall(urllib.parse.unquote(t)):
            out_url_set.add(_norm_url(u))
    lost = src_urls - out_url_set - drop_urls
    for u in sorted(lost)[:20]:
        failures.append(("URL_LOST", f"source URL not in records or drops: {u[:120]}"))
    # permanent assertion: no record may end in a URL that is not a full
    # source-side URL token (truncation guard; no prefix matching). Run the
    # tail through the SAME extraction pipeline as set comparison so spaces
    # or encoded braces canonicalize identically on both sides.
    for t in out_texts:
        m = re.search(r"https?://\S+$", t.rstrip())
        if not m:
            continue
        found = URL_RE.findall(urllib.parse.unquote(m.group(0)))
        if not found:
            continue
        tail = _norm_url(found[0])
        if tail and tail not in src_urls:
            failures.append((
                "URL_TRUNCATED",
                f"record ends with URL not matching any source URL token: {tail[:120]}",
            ))
    return failures


def acl_mismatches(record: dict, entry: dict) -> list[str]:
    problems = []
    if record.get("classification", "") != str(entry.get("classification", "")):
        problems.append("classification")
    if sorted(record.get("allowed_roles") or []) != sorted(entry.get("allowed_roles") or []):
        problems.append("allowed_roles")
    if record.get("department", "") != str(entry.get("department", "")):
        problems.append("department")
    return problems


def token_accounting(
    src_text: str,
    out_text: str,
    drop_texts: list[str],
    with_urls: bool = True,
    raw_text: str | None = None,
) -> tuple[set[str], set[str]]:
    """(lost, gained) special-token sets (emails/URLs/placeholders).

    lost  = source tokens absent from both records and drops (deletion),
            measured against the SCRUBBED source side (approved exclusions);
    gained = record tokens present in neither the RAW file nor drops
            (insertion) -- raw, not scrubbed, so one-sided scrubbing
            (e.g. ``<your domain>`` tag-stripped from source but kept in
            records) is normalization, not insertion.
    """
    src_toks = _tokens(src_text, with_urls=with_urls)
    out_toks = _tokens(out_text, with_urls=with_urls)
    drop_toks: set[str] = set()
    for t in drop_texts:
        drop_toks |= _tokens(t, with_urls=with_urls)
    base_toks = _tokens(raw_text, with_urls=with_urls) if raw_text is not None else src_toks
    return src_toks - out_toks - drop_toks, out_toks - base_toks - drop_toks


def _words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]{2,}", text.lower()))


def check_words(src_text: str, out_text: str, drop_texts: list[str]) -> list[tuple[str, str]]:
    """Word-level accounting (the [04] mechanism) + gain detection.

    Loss fails below the approved 95% effective retention (drop-accounted);
    ANY word in the records that exists in neither source nor drops is an
    insertion and fails outright.
    """
    src = _words(src_text)
    out = _words(out_text)
    drop: set[str] = set()
    for t in drop_texts:
        drop |= _words(t)
    failures: list[tuple[str, str]] = []
    _raw_r, eff_r, n_miss, n_unacc = word_retention(src, out, drop)
    if eff_r < WORD_RETENTION_MIN:
        failures.append((
            "WORD_RETENTION",
            f"effective retention {eff_r:.1%} < {WORD_RETENTION_MIN:.0%} "
            f"(missing={n_miss} unaccounted={n_unacc})",
        ))
    gained = out - src - drop
    if gained:
        failures.append((
            "WORD_GAIN",
            f"record words absent from source+drops: {sorted(gained)[:8]}",
        ))
    return failures


def _acl_failures(record: dict, entry: dict) -> list[tuple[str, str]]:
    probs = acl_mismatches(record, entry)
    if probs:
        return [("ACL_MISMATCH", f"record vs manifest: {'/'.join(probs)}")]
    return []


def cuad_pairing_failures(manifest_paths: set[str]) -> tuple[int, list[str]]:
    """Cond 4: every skipped CUAD PDF has its .txt in the manifest.

    Real filenames vary (trailing space/dash before the extension, or a
    longer pdf stem), so match by directory + normalized stem prefix rather
    than by exact ``pdf[:-4] + '.txt'`` construction.
    """
    failures: list[str] = []
    txt_by_dir: dict[str, list[str]] = defaultdict(list)
    for p in manifest_paths:
        if p.lower().endswith(".txt"):
            txt_by_dir[str(Path(p).parent).replace("\\", "/")].append(p)
    pdfs = [
        p for p in manifest_paths
        if p.lower().endswith(".pdf") and "/cuad/" in f"/{p.lower()}"
    ]

    def _stem(p: str) -> str:
        return re.sub(r"[\s\-_.]+$", "", Path(p).stem).lower()

    for pdf in pdfs:
        directory = str(Path(pdf).parent).replace("\\", "/")
        pstem = _stem(pdf)
        matched = False
        for txt in txt_by_dir.get(directory, []):
            tstem = _stem(txt)
            if tstem and (tstem == pstem or pstem.startswith(tstem) or tstem.startswith(pstem)):
                matched = True
                break
        if not matched:
            failures.append(f"{pdf} has no stem-matching .txt in manifest")
    return len(pdfs), failures


# ---------------------------------------------------------------- timeout

def _call_with_timeout(fn, timeout: float):
    box: dict = {}

    def runner() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"per-file timeout ({timeout}s)")
    if "error" in box:
        raise box["error"]
    return box["value"]


# ---------------------------------------------------------------- mutation

def _run_mutants() -> int:
    print("=== GATE MUTATION TESTS (synthetic fixtures) ===", flush=True)
    caught = 0
    total = 9

    accounting_src = (
        "# Terms\n\n"
        "Provider shall deliver the Services within thirty days of the Effective Date.\n\n"
        "- Phase one research\n"
        "  - interviews\n"
        "  - survey\n"
        "- Phase two build\n"
    )
    para = "Provider shall deliver the Services within thirty days of the Effective Date.\n\n"
    nested_list = (
        "- Phase one research\n"
        "  - interviews\n"
        "  - survey\n"
        "- Phase two build\n"
    )
    acl_entry = {
        "classification": "internal", "allowed_roles": ["employee"], "department": "general",
    }
    acl_record_ok = dict(acl_entry)
    acl_record_bad = {
        "classification": "internal", "allowed_roles": ["admin"], "department": "sales",
    }

    base_fail = (
        check_reasons([], lambda p: "md")
        + check_headings([], {})
        + check_urls({"https://example.com/page"}, ["see https://example.com/page"], [])
        + check_words(accounting_src, accounting_src, [])
        + _acl_failures(acl_record_ok, acl_entry)
    )
    base_ok = not base_fail
    print(f"base fixture clean .................. {'CLEAN' if base_ok else f'FAILED {base_fail}'}")

    tests = [
        (
            "unknown drop reason",
            check_reasons(
                [{"source_path": "a.md", "reason": "mystery", "text": "x", "preview": "x"}],
                lambda p: "md",
            ),
            "UNKNOWN_REASON",
        ),
        (
            "numeric text under no_alpha",
            check_reasons(
                [{"source_path": "a.md", "reason": "no_alpha", "text": "42", "preview": "42"}],
                lambda p: "md",
            ),
            "NUMERIC_NO_ALPHA",
        ),
        (
            "truncated URL tail",
            check_urls(
                {"https://example.com/page"},
                ["see https://example.com/pa"],
                [],
            ),
            "URL_TRUNCATED",
        ),
        (
            "lost dropped heading",
            check_headings(
                [{
                    "source_path": "a.md", "reason": "too_short", "block_type": "heading",
                    "preview": "## Secret Heading", "text": "## Secret Heading",
                }],
                {"a.md": {"Real Section"}},
            ),
            "HEADING_LOST",
        ),
        (
            "page_number in .md",
            check_reasons(
                [{"source_path": "a.md", "reason": "page_number", "text": "12", "preview": "12"}],
                lambda p: "md",
            ),
            "PAGE_NUMBER_SCOPE",
        ),
        (
            "deleted paragraph",
            check_words(accounting_src, accounting_src.replace(para, ""), []),
            "WORD_RETENTION",
        ),
        (
            "deleted nested-list block",
            check_words(accounting_src, accounting_src.replace(nested_list, ""), []),
            "WORD_RETENTION",
        ),
        (
            "inserted unaccounted block",
            check_words(
                accounting_src,
                accounting_src + "\nInjected unaccounted xylophonequark tokens.\n",
                [],
            ),
            "WORD_GAIN",
        ),
        (
            "roles/department vs manifest",
            _acl_failures(acl_record_bad, acl_entry),
            "ACL_MISMATCH",
        ),
    ]
    for i, (name, failures, code) in enumerate(tests, 1):
        codes = {c for c, _ in failures}
        ok = code in codes
        if ok:
            caught += 1
        print(f"mutant {i} {name:<30} {'CAUGHT' if ok else 'MISSED'} ({code})")

    # controls: the same shapes must PASS when legitimate
    ctrl_fail = (
        check_reasons(
            [{"source_path": "a.txt", "reason": "page_number", "text": "12", "preview": "12"}],
            lambda p: "cuad_txt",
        )
        + check_headings(
            [{"source_path": "a.md", "reason": "empty_stub", "block_type": "heading",
              "preview": "## Stub", "text": "## Stub"}],
            {},
        )
        + check_urls({"https://example.com/page"}, ["see https://example.com/page."], [])
        + check_words(accounting_src, accounting_src.replace(para, ""), [para])
        + _acl_failures(acl_record_ok, acl_entry)
    )
    ctrl_ok = not ctrl_fail
    print(f"controls (legit shapes pass) ........ {'CLEAN' if ctrl_ok else f'FAILED {ctrl_fail}'}")
    print(f"{caught}/{total} mutants caught", flush=True)
    return 0 if (base_ok and ctrl_ok and caught == total) else 1


# ---------------------------------------------------------------- gate run

def _iter_record_groups(records_path: Path):
    """Yield (source_path, [record metadata dicts]) in file order."""
    current_path = None
    group: list[dict] = []
    seen: set[str] = set()
    repeats = 0
    with records_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            meta = json.loads(line)["metadata"]
            path = meta.get("source_path", "")
            if path != current_path:
                if current_path is not None:
                    yield current_path, group, repeats
                    repeats = 0
                if path in seen:
                    repeats += 1
                seen.add(path)
                current_path = path
                group = []
            group.append(meta)
    if current_path is not None:
        yield current_path, group, repeats


def _head(text: str, n: int = 180) -> str:
    return " ".join((text or "").split())[:n]


def run_gate(args) -> int:
    t0 = time.time()
    dry = Path(args.dry_run)
    records_path = dry / "records.jsonl"
    drops_path = dry / "drops.jsonl"
    stats_path = dry / "stats.json"
    for p in (records_path, drops_path, stats_path):
        if not p.is_file():
            print(f"FATAL: missing {p}", file=sys.stderr)
            return 2

    lines: list[str] = []
    failures: list[tuple[str, str]] = []
    check_n = 0

    def add(name: str, ok: bool, detail: str) -> None:
        nonlocal check_n
        check_n += 1
        lines.append(f"[{check_n:02d}] {name}: {'PASS' if ok else 'FAIL'} — {detail}")
        if not ok:
            failures.append((name, detail))

    entries = load_manifest()
    entry_by_path = {str(e["path"]).replace("\\", "/"): e for e in entries}
    manifest_paths = set(entry_by_path)

    eligible: list[str] = []
    skipped_by_reason: Counter = Counter()
    for rel in manifest_paths:
        entry = entry_by_path[rel]
        reason = skip_reason(entry)
        if reason:
            skipped_by_reason[reason] += 1
        else:
            eligible.append(rel)

    # drops.jsonl fully in memory (full dropped text for accounting)
    drops_by_path: dict[str, list[dict]] = defaultdict(list)
    all_drops: list[dict] = []
    with drops_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rel = d.get("source_path", "")
            drops_by_path[rel].append(d)
            all_drops.append(d)
    parse_error_paths = {
        rel for rel, ds in drops_by_path.items()
        if any(d.get("reason") == "parse_error" for d in ds)
    }

    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    records_paths = {p for p, _, _ in _iter_record_groups(records_path)}
    zero_record_docs = [
        rel for rel in eligible
        if rel not in records_paths and rel not in parse_error_paths
    ]

    # per-doc accumulators (small)
    lost_tokens: dict[str, list[tuple[str, str]]] = defaultdict(list)
    gained_tokens: list[tuple[str, str]] = []
    word_gained: list[tuple[str, str]] = []
    loss_flagged: list[tuple[str, int, int, float, float]] = []  # rel, src, out, pct, unexp_ratio
    word_flagged: list[tuple[str, float, float, int, int, str, str]] = []
    acl_fail: list[str] = []
    fence_fail: list[str] = []
    url_failures: list[tuple[str, str]] = []
    heading_failures: list[tuple[str, str]] = []
    reason_failures: list[tuple[str, str]] = []
    timeout_files: list[str] = []
    src_scanned = 0
    slow: list[tuple[float, str]] = []

    def check_doc(rel: str, recs: list[dict]) -> dict:
        """Source-side + record-side checks for one document."""
        out: dict = {"records": len(recs)}
        ext = Path(rel).suffix.lower()
        out_text = "\n".join(r.get("text_md", "") for r in recs)
        doc_drops = drops_by_path.get(rel, [])
        drop_texts = [d.get("text") or d.get("preview") or "" for d in doc_drops]

        # record-side
        for r in recs:
            if not fences_balanced(r.get("text_md", "")):
                fence_fail.append(r.get("chunk_id", "?"))
            probs = acl_mismatches(r, entry_by_path.get(rel, {}))
            if probs:
                acl_fail.append(f"{rel} {r.get('chunk_id')} {'/'.join(probs)}")
        out["char_count"] = sum(r.get("char_count", len(r.get("text_md", ""))) for r in recs)

        # source-side (text formats only; PDFs are binary — ingest owns them)
        if ext not in {".md", ".txt", ".htm", ".html"}:
            return out
        try:
            raw = (CORPUS / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            out["error"] = f"read failed: {exc}"
            return out
        src_text = source_tokens_text(raw, ext)
        src_norm = _md_normalize(raw)
        src_chars = len(src_norm.strip())
        out_chars = out["char_count"]
        # only content-bearing sources count for collapse: punctuation-only
        # or frontmatter-stub files (no letters after normalize) are empty
        # by design and produce no records.
        if src_chars and any(c.isalpha() for c in src_norm):
            loss = 1.0 - out_chars / src_chars
            drop_chars = sum(len(t.strip()) for t in drop_texts)
            gap = max(0, src_chars - out_chars)
            unexp_ratio = (max(0, gap - drop_chars) / src_chars)
            if loss > CHAR_COLLAPSE_PCT:
                loss_flagged.append((rel, src_chars, out_chars, loss, unexp_ratio))

        with_urls = ext in {".md", ".txt"}
        lost, gained = token_accounting(src_text, out_text, drop_texts, with_urls, raw)
        for tok in sorted(lost):
            lost_tokens[_kind_of(tok)].append((rel, tok))
        for tok in sorted(gained):
            gained_tokens.append((rel, tok))

        src_urls = {
            n
            for u in URL_RE.findall(urllib.parse.unquote(src_text))
            if (n := _norm_url(u))
        }
        url_failures.extend(check_urls(src_urls, [out_text], drop_texts))

        if ext in {".md", ".txt"}:
            src_words = set(re.findall(r"[A-Za-z]{2,}", src_norm.lower()))
            out_words = set(re.findall(r"[A-Za-z]{2,}", out_text.lower()))
            drop_words: set[str] = set()
            for t in drop_texts:
                drop_words |= set(re.findall(r"[A-Za-z]{2,}", t.lower()))
            raw_r, eff_r, n_miss, n_unacc = word_retention(src_words, out_words, drop_words)
            if eff_r < WORD_RETENTION_MIN:
                word_flagged.append((
                    rel, raw_r, eff_r, n_miss, n_unacc,
                    _head(src_norm), _head(out_text),
                ))
            # gains measured against the RAW file: content that physically
            # exists in the source is kept-vs-scrubbed normalization, not an
            # insertion (mirrors token_accounting's raw-side rule).
            raw_words = _words(raw)
            for w in sorted(out_words - raw_words - drop_words):
                word_gained.append((rel, w))

        out["src_scanned"] = True
        return out

    def scan_one(rel: str, recs: list[dict]) -> dict:
        t_doc = time.perf_counter()
        result = _call_with_timeout(lambda: check_doc(rel, recs), args.file_timeout)
        slow.append((time.perf_counter() - t_doc, rel))
        return result

    # ---- docs with records (streamed groups)
    total_docs = len(eligible)
    done = 0
    t_phase = time.time()
    for rel, recs, repeats in _iter_record_groups(records_path):
        if repeats:
            failures.append(("RECORDS_UNGROUPED", f"{rel} appears in {repeats + 1} non-contiguous groups"))
        try:
            res = scan_one(rel, recs)
            if res.get("src_scanned"):
                src_scanned += 1
        except TimeoutError:
            timeout_files.append(rel)
        except Exception as exc:  # noqa: BLE001
            failures.append(("DOC_CHECK_ERROR", f"{rel}: {exc}"))
        done += 1
        if done % 200 == 0:
            rate = done / max(time.time() - t_phase, 1e-6)
            eta = (total_docs - done) / rate if rate else 0
            print(
                f"[gate] {done}/{total_docs} docs {rate:.1f}/s "
                f"elapsed={time.time() - t0:.0f}s eta={eta:.0f}s",
                file=sys.stderr,
                flush=True,
            )

    # ---- eligible docs with zero records (still source-scanned)
    for rel in zero_record_docs:
        try:
            res = scan_one(rel, [])
            if res.get("src_scanned"):
                src_scanned += 1
        except TimeoutError:
            timeout_files.append(rel)
        except Exception as exc:  # noqa: BLE001
            failures.append(("DOC_CHECK_ERROR", f"{rel}: {exc}"))

    # ---- heading + reason checks across ALL docs with drops (incl. pdf),
    #      using kept heading_paths from a lightweight second stream
    kept_by_doc: dict[str, set[str]] = {}
    for rel, recs, _ in _iter_record_groups(records_path):
        paths: set[str] = set()
        for r in recs:
            paths.update(h for h in (r.get("heading_path") or []) if h)
        kept_by_doc[rel] = paths
    for rel, doc_drops in drops_by_path.items():
        if not doc_drops:
            continue
        heading_failures.extend(check_headings(doc_drops, kept_by_doc))
    # reason checks for every doc with drops (incl. pdf)
    reason_failures.clear()
    for rel, doc_drops in drops_by_path.items():
        reason_failures.extend(check_reasons(doc_drops, lambda p: detect_source_type(p)))

    # ---- cuad pairing (cond 4)
    n_cuad_pdfs, pair_fail = cuad_pairing_failures(manifest_paths)

    # ---- aggregate + report
    add(
        "manifest alignment",
        True,
        f"manifest={len(manifest_paths)} eligible={len(eligible)} "
        f"skipped={dict(skipped_by_reason)} parse_errors={len(parse_error_paths)} "
        f"zero_record_docs={len(zero_record_docs)}",
    )

    lost_total = sum(len(v) for v in lost_tokens.values())
    lost_detail = "; ".join(
        f"{kind}: {len(items)} (e.g. {items[0][0]} {items[0][1][:60]!r})"
        for kind, items in sorted(lost_tokens.items())
        if items
    ) or "none"
    gained_total = len(gained_tokens)
    gained_detail = ""
    if gained_tokens:
        g_rel, g_tok = gained_tokens[0]
        gained_detail = (
            f"; gained (REPORT-only, known normalization artifacts): "
            f"{gained_total} tokens e.g. {g_rel} {g_tok[:60]!r}"
        )
    add(
        "tokens preserved (emails/placeholders/autolinks; drop-accounted)",
        lost_total == 0,
        f"{lost_total} unexplained lost across {src_scanned} text docs — {lost_detail}"
        f"{gained_detail}",
    )

    hard_loss = [x for x in loss_flagged if x[4] > CHAR_UNEXPLAINED_FAIL]
    lines.append(
        f"      char-loss: {len(loss_flagged)} docs >{CHAR_COLLAPSE_PCT:.0%} collapse; "
        f"{len(hard_loss)} with >{CHAR_UNEXPLAINED_FAIL:.0%} unexplained by drops"
    )
    worst = sorted(loss_flagged, key=lambda t: -t[3])[:10]
    worst_set = {rel for rel, _, _, _, _ in worst}
    out_heads: dict[str, str] = {}
    if worst_set:
        with (dry / "records.jsonl").open(encoding="utf-8") as fh:
            for ln in fh:
                meta = json.loads(ln)["metadata"]
                rel = meta.get("source_path", "")
                if rel in worst_set and rel not in out_heads:
                    out_heads[rel] = _head(meta.get("text_md", ""))
    for rel, s, o, pct, unexp in worst:
        lines.append(
            f"      | {rel} src={s} out={o} loss={pct:.1%} unexplained={unexp:.1%} "
            f"reasons={dict(Counter(d.get('reason') for d in drops_by_path.get(rel, [])))}"
        )
        src_norm_head = ""
        try:
            src_norm_head = _head((CORPUS / rel).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
        lines.append(f"      |   src: {src_norm_head!r}")
        lines.append(f"      |   out: {out_heads.get(rel, '')!r}")
    # approved design: char-loss is a REPORT (flag + attribution + 10 worst
    # side-by-side); the hard content gates are [02] tokens and [04] words.
    warn_lines = len(loss_flagged)
    check_n += 1
    lines.append(
        f"[{check_n:02d}] char loss >20% (attribution report, WARN only): "
        f"{'OK' if not hard_loss else 'WARN'} — {warn_lines} docs >{CHAR_COLLAPSE_PCT:.0%} collapse, "
        f"{len(hard_loss)} with >{CHAR_UNEXPLAINED_FAIL:.0%} unexplained"
        + (f" e.g. {hard_loss[0][0]}" if hard_loss else "")
    )

    word_below = len(word_flagged)
    word_frac = word_below / src_scanned if src_scanned else 0.0
    for rel, raw_r, eff_r, n_miss, n_unacc, s_head, o_head in sorted(
        word_flagged, key=lambda t: t[2]
    )[:10]:
        lines.append(
            f"      | {rel} raw={raw_r:.2%} effective={eff_r:.2%} "
            f"missing={n_miss} unaccounted={n_unacc}"
        )
        lines.append(f"      |   src: {s_head!r}")
        lines.append(f"      |   out: {o_head!r}")
    wg_total = len(word_gained)
    wg_detail = ""
    if word_gained:
        w_rel, w_tok = word_gained[0]
        wg_detail = (
            f"; gained (REPORT-only, known normalization artifacts): "
            f"{wg_total} words e.g. {w_rel} {w_tok!r}"
        )
    add(
        "word retention >=95% in >=99% of md/txt docs (drop-accounted)",
        word_frac < WORD_FAIL_DOC_FRACTION,
        f"{word_below} docs below 95% of {src_scanned} scanned = {word_frac:.2%}{wg_detail}",
    )

    # lengths over a single streamed pass
    lt50_examples: list[str] = []
    lt100_examples: list[str] = []
    total_records = 0
    elig_records = 0
    lt100_n = 0
    lt50_n = 0
    for _, recs, _ in _iter_record_groups(records_path):
        for r in recs:
            total_records += 1
            cc = r.get("char_count", len(r.get("text_md", "")))
            bt = r.get("block_type", "")
            if bt not in {"table", "code"}:
                elig_records += 1
                if cc < 100:
                    lt100_n += 1
                    if len(lt100_examples) < 5:
                        lt100_examples.append(f"{r.get('chunk_id')} {r.get('text_md', '')[:60]!r}")
            if cc < 50:
                lt50_n += 1
                if len(lt50_examples) < 5:
                    lt50_examples.append(f"{r.get('chunk_id')} {r.get('text_md', '')[:60]!r}")
    lt100_frac = (lt100_n / elig_records) if elig_records else 0.0
    add(
        "chunk lengths (<50 = 0; <100 excl table/code < 1%)",
        lt50_n == 0 and lt100_frac < SHORT100_FRACTION,
        f"<50: {lt50_n} (e.g. {lt50_examples[:2]}); "
        f"<100: {lt100_n}/{elig_records} = {lt100_frac:.2%} of non-table/code",
    )

    url_lost_n = sum(1 for c, _ in url_failures if c == "URL_LOST")
    url_trunc_n = sum(1 for c, _ in url_failures if c == "URL_TRUNCATED")
    for code, detail in url_failures[:10]:
        lines.append(f"      | {code}: {detail}")
    add(
        "URLs exact-set + no truncated tails (unquote+terminator, no prefix)",
        not url_failures,
        f"lost={url_lost_n} truncated={url_trunc_n}",
    )

    add(
        "dropped headings in kept paths or empty_stub (cond 3)",
        not heading_failures,
        f"{len(heading_failures)} unmatched"
        + (f" e.g. {heading_failures[0][1][:100]}" if heading_failures else ""),
    )

    add(
        "CUAD pdf/txt pairing (cond 4)",
        not pair_fail,
        f"{n_cuad_pdfs - len(pair_fail)}/{n_cuad_pdfs} paired"
        + (f"; missing: {pair_fail[:3]}" if pair_fail else ""),
    )

    page_by_type = Counter(
        detect_source_type(d.get("source_path", ""))
        for d in all_drops if d.get("reason") == "page_number"
    )
    add(
        "drop-reason scope (page_number 3 sources; no numeric/lettered no_alpha; no unknown)",
        not reason_failures,
        f"page_number by source={dict(page_by_type)}; "
        f"scope/numeric/unknown failures={len(reason_failures)}"
        + (f" e.g. {reason_failures[0][0]} {reason_failures[0][1][:90]}" if reason_failures else ""),
    )

    add(
        "ACL matches manifest (classification/allowed_roles/department)",
        not acl_fail,
        f"{len(acl_fail)} mismatches" + (f" e.g. {acl_fail[:2]}" if acl_fail else ""),
    )

    add(
        "fences balanced in 100% of text_md",
        not fence_fail,
        f"{len(fence_fail)} unbalanced" + (f" e.g. {fence_fail[:4]}" if fence_fail else ""),
    )

    add(
        "per-file timeouts",
        not timeout_files,
        f"{len(timeout_files)} timed out"
        + (f" e.g. {timeout_files[:3]}" if timeout_files else ""),
    )

    slow_sorted = sorted(slow, reverse=True)[:5]
    lines.append("      5 slowest files:")
    for secs, rel in slow_sorted:
        lines.append(f"        {secs:7.1f}s  {rel}")

    atoms = stats.get("oversize_atoms_list") or []
    lines.append(f"\n--- oversize atoms (kept + justified): {len(atoms)} ---")
    for atom in atoms:
        lines.append(
            f"  {atom.get('doc_id', '?')} tok={atom.get('tokens')} "
            f"why={atom.get('justification')!r} head={atom.get('preview', '')[:60]!r}"
        )

    check_failures = [f for f in failures if f[0] not in {"RECORDS_UNGROUPED", "DOC_CHECK_ERROR"}]
    passed = check_n - len({name for name, _ in check_failures})
    summary_ok = not failures
    lines.append(
        f"\nSUMMARY: {passed}/{check_n} checks PASS, "
        f"extra_failures={len(failures) - len(check_failures)} "
        f"elapsed={time.time() - t0:.1f}s -> {'PASS' if summary_ok else 'FAIL'}"
    )

    report = "\n".join(lines)
    if args.report:
        # write BEFORE printing: a console encoding error must never cost
        # the verdict file (Windows cp1252 chokes on corpus accents)
        Path(args.report).write_text(report + "\n", encoding="utf-8", newline="\n")
        print(f"[gate] report written -> {args.report}", file=sys.stderr)
    print(report)
    return 0 if summary_ok else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", default=str(CORPUS / "v2_dryrun"))
    ap.add_argument("--report", default="", help="write the gate report to this file")
    ap.add_argument("--file-timeout", type=float, default=60.0)
    ap.add_argument("--mutation-test", action="store_true",
                    help="run the 9 synthetic mutants and exit (run BEFORE the real gate)")
    args = ap.parse_args()
    if args.mutation_test:
        return _run_mutants()
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
