"""Phase 1 unit tests for ingestion_v2 (offline; no DB/network)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from app.ingestion_v2 import chunk_doc, detect_source_type, parse_file, process_file
from app.ingestion_v2.htmlconv import convert_fragment
from app.ingestion_v2.md_parser import escape_table_code_pipes, parse_markdown
from app.ingestion_v2.records import CHUNK_VERSION
from app.ingestion_v2.shortcodes import preprocess
from app.ingestion_v2.text_parser import parse_cuad_txt

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
HANDBOOK = CORPUS / "general" / "gitlab_handbook" / "about"

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ingest_v2 import (  # noqa: E402
    norm_url,
    source_tokens_text,
    tokens_of,
)


def _entry(rel: str, **overrides) -> dict:
    entry = {
        "path": rel,
        "department": "hr",
        "classification": "Internal",
        "allowed_roles": ["hr"],
        "source": "gitlab",
    }
    entry.update(overrides)
    return entry


def _first_file(directory: Path, pattern: str) -> Path | None:
    if not directory.is_dir():
        return None
    return next(iter(sorted(directory.glob(pattern))), None)


# ---------------------------------------------------------------- front matter

def test_front_matter_stripped_and_title_kept():
    path = HANDBOOK / "_index.md"
    if not path.is_file():
        pytest.skip("handbook _index.md missing")
    parsed = parse_file(path, str(path.relative_to(CORPUS)).replace("\\", "/"))
    assert parsed.frontmatter.get("title")
    assert parsed.doc_title == str(parsed.frontmatter["title"]).strip()
    joined = "\n".join(b.md for b in parsed.blocks)
    assert "weight:" not in joined
    assert not joined.startswith("---")


# ---------------------------------------------------------------- tables

def test_pipe_table_intact_small():
    path = HANDBOOK / "maintenance.md"
    if not path.is_file():
        pytest.skip("maintenance.md missing")
    parsed = parse_file(path, str(path.relative_to(CORPUS)).replace("\\", "/"))
    tables = [b for b in parsed.blocks if b.kind == "table"]
    assert tables, "expected at least one table block"
    for table in tables:
        lines = [ln for ln in table.md.splitlines() if ln.strip().startswith("|")]
        assert len(lines) >= 2
        assert set(lines[1].replace("|", "").replace(" ", "")) <= {"-", ":"}
        for row in lines:
            assert row.count("|") >= 2, f"malformed row: {row!r}"


def test_br_in_table_cell_becomes_space():
    # <br> inside a GFM cell used to vanish (convert_fragment strips the
    # newline it produced), jamming "**Name**Staff EBA" together.
    md = (
        "| Name | Role |\n| --- | --- |\n"
        "| **Jeanne Rotenberry**<br>Staff EBA | Bill Staples (CEO) |\n"
    )
    parsed = parse_markdown(f"# T\n\n{md}")
    table = next(b for b in parsed.blocks if b.kind == "table")
    assert "**Jeanne Rotenberry** Staff EBA" in table.md
    assert "**Jeanne Rotenberry**Staff" not in table.md
    # linearized embed form: no markdown syntax at all (plan section A)
    assert "Name: Jeanne Rotenberry Staff EBA" in table.plain
    assert "**" not in table.plain


def test_br_in_prose_keeps_newline_and_plain_space():
    parsed = parse_markdown("# T\n\nline one<br>line two")
    prose = next(b for b in parsed.blocks if b.kind == "prose")
    assert "line one\nline two" in prose.md
    assert prose.plain.strip() == "line one line two"


def test_oversized_table_split_repeats_header():
    rows = "\n".join(f"| row{i} val | more{i} |" for i in range(400))
    md = f"| Header A | Header B |\n| --- | --- |\n{rows}\n"
    parsed = parse_markdown(f"# Big table\n\n{md}")
    drafts, drops = chunk_doc(parsed)
    table_drafts = [d for d in drafts if d.block_type in ("table", "mixed")]
    assert len(table_drafts) > 1, "large table should split into multiple chunks"
    for draft in table_drafts:
        assert "| Header A | Header B |" in draft.text_md
        assert draft.token_count <= 850


# ---------------------------------------------------------------- code fences

def test_code_fence_balanced_after_split():
    code_lines = "\n".join(f"echo line {i}" for i in range(900))
    md = f"# Runbook\n\n```bash\n{code_lines}\n```\n"
    parsed = parse_markdown(md)
    drafts, _ = chunk_doc(parsed)
    code_drafts = [d for d in drafts if "code" in d.kinds]
    assert code_drafts
    for draft in code_drafts:
        fence_count = sum(
            1 for line in draft.text_md.splitlines() if line.strip().startswith("```")
        )
        assert fence_count % 2 == 0, "every chunk must have balanced fences"


# ---------------------------------------------------------------- placeholders

def test_autolinks_emails_placeholders_preserved():
    md = (
        "# Contact\n\n"
        "See <https://example.com/policy> and mail <FOIA@gitlab.com> "
        "or the <EBA name> placeholder inside this sentence about leave.\n\n"
        "<div>HTML block with <a href=\"https://example.org/x\">a link</a>.</div>\n"
    )
    parsed = parse_markdown(md)
    drafts, drops = chunk_doc(parsed)
    joined = "\n".join(d.text_md for d in drafts)
    embeds = "\n".join(d.plain for d in drafts)
    assert "<https://example.com/policy>" in joined
    assert "<FOIA@gitlab.com>" in joined
    assert "<EBA name>" in joined
    assert "https://example.com/policy" in embeds
    assert "FOIA@gitlab.com" in embeds


# ---------------------------------------------------------------- shortcodes

def test_shortcode_rules():
    body = (
        "Before.\n"
        "{{% include_relative footer.md %}}\n"
        "{{< video >}}inner video text{{< /video >}}\n"
        "{{< notice header=\"Heads up\" >}}Body text{{< /notice >}}\n"
        "{{< member member-by-name=\"Alice Doe\" >}}\n"
        "{{< youtube dQw4w9WgXcQ >}}\n"
        "{{< group-by-slugs=\"engineering/devops\" >}}\n"
        "orphan {{< /gone >}} end\n"
        "<!-- vale GitLab.Vale.Spelling = NO -->\n"
        "After.\n"
    )
    out = preprocess(body)
    assert "include_relative" not in out
    assert "inner video text" in out
    assert "Heads up" in out and "Body text" in out
    assert "Alice Doe" in out
    assert "dQw4w9WgXcQ" not in out
    assert "[video]" in out
    assert "engineering/devops" not in out
    assert "orphan" in out and "/gone" not in out
    assert "vale GitLab" not in out
    assert "Before." in out and "After." in out


def test_html_comment_and_unknown_tag_mask():
    md = "Keep <b>bold</b> and <EBA name> tokens; drop <!-- comment --> text.\n"
    out = convert_fragment(md)
    assert "<EBA name>" in out
    assert "comment" not in out
    assert "bold" in out


# ---------------------------------------------------------------- merge / drop

def test_small_chunks_merge_and_junk_dropped():
    md = (
        "# Section A\n\n"
        "Short line one.\n\n"
        "---\n\n"
        "##\n\n"
        "TBD\n\n"
        "This is a sufficiently long paragraph that talks about annual leave "
        "entitlements and should survive the junk filter without any trouble.\n"
    )
    parsed = parse_markdown(md)
    drafts, drops = chunk_doc(parsed)
    joined = "\n".join(d.text_md for d in drafts)
    assert "annual leave" in joined
    assert "TBD" not in joined
    assert "---" not in joined or "annual leave" in joined.split("---")[0]
    reasons = {d.reason for d in drops}
    assert reasons & {"syntax_only", "too_short", "few_words", "no_alpha"}
    for draft in drafts:
        assert len(draft.text_md.strip()) >= 50


def test_no_syntax_only_chunk_emitted():
    md = "# T\n\n|\n\n---\n\n***\n\n___\n"
    drafts, drops = chunk_doc(parse_markdown(md))
    assert drafts == [] or all(
        re.search(r"[A-Za-z]{2,}", d.text_md) for d in drafts
    )


# ---------------------------------------------------------------- heading path

def test_heading_path_prepended_to_embed_plain(tmp_path: Path):
    target = tmp_path / "levels.md"
    target.write_text(
        "# Doc Title\n\n## Level One\n\n### Level Two\n\n"
        "A real sentence with enough words to pass filters.\n",
        encoding="utf-8",
    )
    records, _, _ = process_file(target, _entry("hr/x/levels.md"), "doc_hr_0042")
    assert records
    record = records[0]
    assert record.heading_path == ["Doc Title", "Level One", "Level Two"]
    assert record.text_embed.startswith("Doc Title > Level One > Level Two\n\n")
    assert "A real sentence" in record.text_embed


def test_determinism_same_file_twice(tmp_path: Path):
    rel = "hr/synthetic/leave_policy.md"
    target = tmp_path / "leave_policy.md"
    target.write_text(
        "# Leave\n\nEmployees get 20 days of annual leave per calendar year "
        "in addition to public holidays observed in their region of work.\n",
        encoding="utf-8",
    )
    recs1, _, _ = process_file(target, _entry(rel), "doc_hr_0001")
    recs2, _, _ = process_file(target, _entry(rel), "doc_hr_0001")
    assert [(r.chunk_id, r.content_hash) for r in recs1] == [
        (r.chunk_id, r.content_hash) for r in recs2
    ]
    assert recs1[0].chunk_version == CHUNK_VERSION
    assert recs1[0].chunk_id.startswith("doc_hr_0001#")
    assert recs1[0].department == "hr"
    assert recs1[0].allowed_roles == ["hr"]


# ---------------------------------------------------------------- real corpus

def test_cuad_heading_path_includes_title_and_parties():
    directory = CORPUS / "legal" / "cuad"
    path = _first_file(directory, "*.txt")
    if path is None:
        pytest.skip("no CUAD sample")
    rel = str(path.relative_to(CORPUS)).replace("\\", "/")
    records, drops, _ = process_file(path, _entry(rel, department="legal", allowed_roles=["legal"]), "doc_legal_0001")
    assert records, "CUAD file should produce chunks"
    for record in records:
        assert record.heading_path, "every chunk carries a heading path"
        assert record.doc_title
        assert record.source_type == "cuad_txt"
        assert record.text_embed.startswith(record.doc_title) or record.doc_title in record.text_embed[:200]


def test_sec_10k_items_and_no_ix_noise():
    directory = CORPUS / "finance" / "sec_10k"
    path = _first_file(directory, "apple_10k*.htm") or _first_file(directory, "*10k*.htm")
    if path is None:
        pytest.skip("no SEC sample")
    rel = str(path.relative_to(CORPUS)).replace("\\", "/")
    records, drops, _ = process_file(
        path, _entry(rel, department="finance", allowed_roles=["finance"]), "doc_finance_0001"
    )
    assert len(records) > 5
    joined = "\n".join(r.text_md for r in records)
    assert "ix:" not in joined
    assert "<script" not in joined.lower()
    assert records[0].doc_title  # "Company 10-K (date)"
    assert re.search(r"10-?K", records[0].doc_title, re.I)
    item_paths = [
        r.heading_path for r in records
        if any(p.startswith("Item ") for p in r.heading_path)
    ]
    assert item_paths, "apple 10-K body headers should become Item heading paths"


def test_labour_pdf_sections():
    directory = CORPUS / "hr" / "direct"
    path = _first_file(directory, "code_on_wages*.pdf")
    if path is None:
        pytest.skip("no labour PDF sample")
    rel = str(path.relative_to(CORPUS)).replace("\\", "/")
    records, drops, _ = process_file(
        path, _entry(rel, department="hr", allowed_roles=["hr"]), "doc_hr_9001"
    )
    assert len(records) > 5
    section_paths = [
        r.heading_path for r in records if any(re.match(r"^\d+\.", p) for p in r.heading_path)
    ]
    assert section_paths, "statute sections should appear in heading paths"
    assert all(r.char_count >= 50 for r in records)


def test_detect_source_type_dispatch():
    assert detect_source_type("legal/cuad/x.txt") == "cuad_txt"
    assert detect_source_type("finance/sec_10k/apple_10k_2025-09-27.htm") == "sec_htm"
    assert detect_source_type("hr/direct/code_on_wages_2019.pdf") == "pdf"
    assert detect_source_type("general/gitlab_handbook/about/_index.md") == "md"


# ------------------------------------------------ Phase 2 amendments

def test_mojibake_gate_drops_garbage_keeps_english():
    from app.ingestion_v2.chunker import mojibake_drop_reason, mojibake_ratio

    garbage = (
        "jftLVªh lañ Mhñ ,yñ —( ,u ) 04@0007@2003 — 19\n\n"
        "vlk/kkj.k EXTRAORDINARY Hkkx II — [k.M 1 PART II — Section 1 "
        "izkf/kdkj ls izdkf'kr PUBLISHED BY AUTHORITY\n\n"
        "lañ 48] ubZ fnYyh] c`gLifrokj] vxLr 8] 2019@Jko.k 17] 1941 ]kSfiykt"
    )
    assert mojibake_ratio(garbage) > 0.02
    assert mojibake_drop_reason(garbage) == "mojibake_suspect"

    clean = (
        "Employees are entitled to twenty days of paid annual leave each "
        "calendar year, in addition to public holidays observed in their "
        "region. Unused leave may carry over up to five days (see §4.2). "
        "The em-dash — and © symbol and curly “quotes” are fine here."
    )
    assert mojibake_drop_reason(clean) is None


def test_oversize_split_or_justified():
    from app.ingestion_v2.chunker import chunk_doc

    # multi-sentence oversized prose must be split under the hard max
    sentences = " ".join(
        f"This is sentence number {i} with enough words to matter for packing."
        for i in range(120)
    )
    drafts, _ = chunk_doc(parse_markdown(f"# Split me\n\n{sentences}"))
    oversize = [d for d in drafts if d.token_count > 850]
    assert not oversize, f"multi-sentence prose must split: {[d.token_count for d in oversize]}"
    assert any(d.token_count > 300 for d in drafts)

    # a single unsplittable sentence is KEPT with a justification
    one_sentence = (
        "This remarkably long sentence, which contains commas and clauses and "
        "plenty of ordinary English words, never uses a full stop anywhere and "
        "therefore cannot be split at a sentence boundary by the chunker at all "
        "and must be kept whole with a justification"
    ) + " and the padding phrase" * 250 + "."
    drafts2, _ = chunk_doc(parse_markdown(f"# Atom\n\n{one_sentence.strip()}"))
    atoms = [d for d in drafts2 if d.oversize_justification]
    assert atoms, "single unsplittable unit must be kept with justification"
    assert "unsplittable" in atoms[0].oversize_justification


def test_giant_link_list_splits_no_duplicates():
    from app.ingestion_v2.chunker import HARD_MAX

    lines = "\n".join(
        f"- [Poster {i} of the state labor department](https://example.com/docs/poster_{i}_english.pdf)"
        for i in range(400)
    )
    drafts, _ = chunk_doc(parse_markdown(f"# Posters\n\n{lines}"))
    assert drafts, "link list must produce chunks"
    hashes = [d.text_md for d in drafts]
    assert len(hashes) == len(set(hashes)), "no duplicate chunks from giant link lists"
    over = [d.token_count for d in drafts if d.token_count > HARD_MAX]
    assert not over, f"link-list chunks must pack under HARD_MAX: {over}"


def test_labour_pdf_mojibake_chunks_quarantined():
    directory = CORPUS / "hr" / "direct"
    path = _first_file(directory, "code_on_wages*.pdf")
    if path is None:
        pytest.skip("no labour PDF sample")
    rel = str(path.relative_to(CORPUS)).replace("\\", "/")
    records, drops, meta = process_file(
        path, _entry(rel, department="hr", allowed_roles=["hr"]), "doc_hr_9001"
    )
    reasons = {d.reason for d in drops}
    assert reasons & {"mojibake_suspect", "non_english"}, "Krutidev garbage chunks must be quarantined"
    assert records, "clean English chunks must survive"
    for record in records:
        from app.ingestion_v2.chunker import english_likeness, mojibake_ratio

        assert mojibake_ratio(record.text_md) <= 0.02
        likeness = english_likeness(record.text_md)
        assert likeness is None or likeness >= 0.05


# ------------------------------------------------ plan-A / plan-gate regressions

def test_language_gate_runs_on_document_not_fragments():
    from app.ingestion_v2.chunker import chunk_doc, doc_non_english

    # English doc made of label lists, checklists and a diagram: per-fragment
    # stopword testing dropped 1,666/1,741 such fragments as non_english.
    md = (
        "## Lead to Cash Flow\n\n"
        "**Business Process**\n\n**Supporting System**\n\n"
        "Demand Gen Effort (Marketo)\n\nMarketing Ops\n\n"
        "Trial (Home Grown Application - Ruby on Rails)\n\n"
        "Fulfillment Engineers\n\n"
        "### Information required\n\n"
        "1. Reseller Name\n2. Contact Name\n3. Contact Email\n"
        "4. Quote Number\n5. End Customer Name\n6. Product Details\n\n"
        "## Architecture Diagram\n\n"
        "```mermaid\ngraph TB\nsubgraph Identity Platform Control Plane\n"
        'BLACK_CI["Terraform AWS GitOps"]:::yellow\nend\n```\n\n'
        "Our café team has seen this document read as follows. The teams that "
        "own it are the ones who update it, and they do so every quarter so "
        "that it stays accurate for everyone who needs it.\n"
    )
    parsed = parse_markdown(md)
    flagged, _ = doc_non_english(parsed)
    assert not flagged, "ASCII/English doc must not be flagged by stopword absence"
    drafts, drops = chunk_doc(parsed)
    assert not [d for d in drops if d.reason == "non_english"], [
        (d.reason, d.preview[:60]) for d in drops
    ]
    assert drafts, "English label/diagram sections must produce chunks"

    # accented foreign-language prose with no English stopwords: still dropped
    de = (
        "Die Teilnehmerin muss alle Angaben wahrheitsgemäß ausfüllen. "
        "Über die Gewinnchancen wird nicht diskutiert. Die Regeln gelten "
        "ausschließlich für volljährige Personen mit Wohnsitz in Deutschland. "
        "Eine Übertragung der Ansprüche ist ausgeschlossen und nicht zulässig. "
        "Alle Einsendungen bleiben der Veranstaltung vorbehalten, sofern nicht "
        "ausdrücklich etwas anderes angegeben ist."
    )
    parsed_de = parse_markdown(f"## Regeln\n\n{de}")
    flagged_de, _ = doc_non_english(parsed_de)
    assert flagged_de, "foreign-language doc must still be flagged"
    drafts_de, drops_de = chunk_doc(parsed_de)
    assert drafts_de == [], "whole foreign doc must be dropped"
    assert drops_de and all(d.reason == "non_english" for d in drops_de)


def test_blocks_after_list_survive():
    # _collect_list used ul_open/ol_close strings that never matched
    # markdown-it token types, so the collector ran to the end of the token
    # stream and everything after a document's first list was dropped.
    md = (
        "# T\n\n"
        "- item one\n"
        "- item two\n\n"
        "## After list\n\n"
        "Tail prose here with enough words to matter.\n\n"
        "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    )
    blocks = parse_markdown(md).blocks
    joined = "\n".join(b.md for b in blocks)
    assert "Tail prose here" in joined, f"blocks after list dropped: {[b.kind for b in blocks]}"
    assert "| 1 | 2 |" in joined, "table after list dropped"
    assert any(b.kind == "heading" and "After list" in b.md for b in blocks)


def test_fence_and_html_inside_list_survive():
    # _collect_list only serialized inline tokens, so every fence/html block
    # inside a list item (runbook pattern: "1. run: ```bash") vanished with
    # no drop record — 1,566 fences across 362 corpus docs.
    md = (
        "## Runbook\n\n"
        "1. Configure git to rewrite ssh remotes:\n"
        "   ```shell\n"
        '   git config --global url."https://gitlab.com/".insteadOf "git@gitlab.com:"\n'
        "   ```\n"
        "2. Test the connection with a token:\n"
        "   ```bash\n"
        "   ssh -T git@gitlab.com\n"
        "   ```\n"
        "3. Review the status panel:\n"
        "   <div class=\"panel\"><p>Status is green for all checks</p></div>\n"
    )
    blocks = parse_markdown(md).blocks
    joined = "\n".join(b.md for b in blocks)
    assert "git@gitlab.com" in joined, f"fence in list dropped: {[b.kind for b in blocks]}"
    assert "```shell" in joined, "fence info string lost"
    assert "Status is green" in joined, f"html block in list dropped: {joined[-300:]!r}"
    plains = " ".join(b.plain for b in blocks)
    assert "ssh -T git@gitlab.com" in plains, "fence plain text missing from embed path"


def test_long_fenced_list_splits_only_at_atomic_boundaries():
    # Once fences ride inside list blocks, oversize splits must keep every
    # fence whole: paragraph/sentence/overlap cuts inside a fence produce
    # records whose trailing content renders as code (unclosed fence).
    from app.ingestion_v2.chunker import chunk_doc, fences_balanced

    steps = []
    for i in range(60):
        steps.append(
            f"{i + 1}. Run step {i} against the host cluster now and verify.\n"
            f"   ```bash\n"
            f"   echo step {i} && curl -sf https://example.com/health/{i} || true\n"
            f"   ```\n"
        )
    drafts, _ = chunk_doc(parse_markdown("## Ops runbook\n\n" + "\n".join(steps)))
    assert drafts
    joined = "\n".join(d.text_md for d in drafts)
    assert joined.count("```bash") == 60, "fence opener lost during split"
    for draft in drafts:
        for line in draft.text_md.splitlines():
            if "```" in line:
                assert line.lstrip().startswith("```"), (
                    f"fence glued mid-line by overlap: {line[:80]!r}"
                )
        assert fences_balanced(draft.text_md), f"unclosed fence: {draft.text_md[:200]!r}"


def test_fence_balance_semantics_match_markdown_it():
    # Sources contain fences whose CONTENT looks like markers; only an
    # info-less line at <= opener indent may close.
    from app.ingestion_v2.chunker import fences_balanced

    # info'd marker line inside the fence is content, closer follows
    assert fences_balanced("```text\nprompt:\n```markdown\nmore\n```\nafter\n")
    # deeper-indented clean marker inside a list fence is content
    assert fences_balanced("1. step\n\n   ```yml\n     x\n     ```\n   ```\n\nnext\n")
    # genuinely cut fence (closer missing) must still be detected
    assert not fences_balanced("```bash\necho hi\n")
    # cut record that only carries the closer: lone opener stays unclosed
    assert not fences_balanced("   ```\nstray closer content\n")


def test_indented_list_fence_survives_paragraph_split():
    # List fences arrive indented ("   ```bash …   ```"); stripping only the
    # opener while content/closer keep their indent produced records whose
    # closer no longer closes (closer indent > opener indent).
    from app.ingestion_v2.chunker import chunk_doc, fences_balanced

    md = (
        "## Task B\n\n"
        "For this example, restart Rails:\n\n"
        "1. Stop the service now.\n"
        "2. Restart it:\n"
        "   ```bash\n"
        "   sudo gitlab-ctl restart puma\n"
        "   ```\n"
    )
    drafts, _ = chunk_doc(parse_markdown(md))
    assert drafts
    for draft in drafts:
        assert fences_balanced(draft.text_md), draft.text_md[:200]
    joined = "\n".join(d.text_md for d in drafts)
    assert "sudo gitlab-ctl restart puma" in joined


def test_outer_fence_with_inner_backticks_reemits_longer_delimiter():
    # A ```` fence whose content contains ``` lines must not be re-emitted as
    # ``` — the inner marker would close it early and the appended closer
    # would re-open, leaving an unclosed fence.
    from app.ingestion_v2.chunker import chunk_doc, fences_balanced

    md = (
        "## Config\n\n"
        "````markdown\n"
        "Example:\n"
        "```bash\n"
        "echo hi\n"
        "```\n"
        "````\n\n"
        "More prose after the fence.\n"
    )
    drafts, _ = chunk_doc(parse_markdown(md))
    assert drafts
    for draft in drafts:
        assert fences_balanced(draft.text_md), draft.text_md[:200]
    joined = "\n".join(d.text_md for d in drafts)
    assert "````markdown" in joined, "outer fence delimiter not lengthened"
    assert "echo hi" in joined


def test_short_english_doc_with_accents_not_flagged():
    # "Meet the Engineering Managers": 75 words, table text without
    # stopwords, a few accented names — the bare likeness test dropped it.
    from app.ingestion_v2.chunker import doc_non_english

    md = (
        "## Meet the Engineering Managers\n\n"
        "| Name | Title | Team |\n| --- | --- | --- |\n"
        "| Zoë Admin | Engineering Manager | Create |\n"
        "| José Engineer | Senior Manager | Plan |\n"
        "| Maria Lead | Director | Verify |\n"
        "| Ana Ops | Manager | Secure |\n"
        "| Luis Dev | Staff Engineer | Growth |\n"
        "| Sara PM | Product Manager | Monitor |\n"
        "| Tom SRE | Senior SRE | Infrastructure |\n"
        "| Nia Data | Data Engineer | Analytics |\n"
        "| Leo Infra | Platform Lead | Delivery |\n"
        "| Zoe BA | Business Analyst | Finance |\n"
    )
    flagged, _ = doc_non_english(parse_markdown(md))
    assert not flagged, "short accented English roster must not be flagged"


def test_embed_plains_never_carry_markdown():
    sentences = " ".join(
        f"Sentence **{i}** with a [link](https://example.com/x{i}) and bold text."
        for i in range(80)
    )
    drafts, _ = chunk_doc(parse_markdown(f"# Doc\n\n{sentences}"))
    assert drafts
    for draft in drafts:
        assert "**" not in draft.plain, f"markdown leaked into plain: {draft.plain[:120]!r}"
        assert "](" not in draft.plain, f"markdown link leaked into plain: {draft.plain[:120]!r}"


def test_oversize_table_plains_linearized_and_header_repeated():
    rows = "\n".join(
        f"| **row {i}** value | [doc {i}](https://example.com/{i}) |"
        for i in range(200)
    )
    md = f"| Head A | Head B |\n| --- | --- |\n{rows}\n"
    drafts, _ = chunk_doc(parse_markdown(f"# Big\n\n{md}"))
    table_drafts = [d for d in drafts if d.kinds == {"table"} or d.block_type == "table"]
    assert len(table_drafts) > 1, "oversize table must split by rows"
    for draft in table_drafts:
        assert "| Head A | Head B |" in draft.text_md, "header must repeat in every piece"
        assert draft.token_count <= 850
        assert draft.plain.strip(), f"table piece lost its plain: {draft.text_md[:80]!r}"
        assert "**" not in draft.plain, f"markdown leaked into table plain: {draft.plain[:120]!r}"
        assert "](" not in draft.plain, f"link leaked into table plain: {draft.plain[:120]!r}"


def test_table_empty_layout_rows_later_pieces_keep_plain():
    # _collect_table keeps all-empty layout rows as "" plain lines; the
    # chunker must not filter them out of alignment (44 head-only embeds).
    body = "\n".join(
        (
            f"| data {i} alpha | data {i} beta |\n|  |  |"
            if i % 2 == 0
            else f"| tail {i} alpha | tail {i} beta |"
        )
        for i in range(160)
    )
    md = f"| Col A | Col B |\n| --- | --- |\n{body}\n"
    drafts, _ = chunk_doc(parse_markdown(f"# Spaced\n\n{md}"))
    table_drafts = [d for d in drafts if "table" in d.kinds]
    assert len(table_drafts) > 1, "table with layout rows must still split"
    for draft in table_drafts:
        assert draft.plain.strip(), (
            f"empty plain for piece: md={draft.text_md[:100]!r}"
        )


def test_oversize_code_plains_have_no_fences():
    code_lines = "\n".join(f"echo line {i}" for i in range(900))
    md = f"# Runbook two\n\n```bash\n{code_lines}\n```\n"
    drafts, _ = chunk_doc(parse_markdown(md))
    code_drafts = [d for d in drafts if "code" in d.kinds]
    assert code_drafts
    for draft in code_drafts:
        assert "```" not in draft.plain, f"fence leaked into plain: {draft.plain[:120]!r}"


def test_heading_stub_merges_into_next_same_section():
    words = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog", "near", "riverbank"]
    long_sentence = " ".join(words * 10) + "."
    body = " ".join([long_sentence] * 10)
    heading = "# Merge me somewhere with enough words to stay afloat"
    drafts, _ = chunk_doc(parse_markdown(f"{heading}\n\n{body}\n"))
    stubs = [d for d in drafts if d.text_md.strip() == heading]
    assert not stubs, "heading-only stub must merge into its same-section successor"
    merged = [d for d in drafts if heading in d.text_md]
    assert merged and len(merged) == 1
    assert "riverbank" in merged[0].text_md


# ---------------- user-approved gate fixes: mojibake / vowelless / stubs

def test_french_prose_survives_language_gates():
    from app.ingestion_v2.chunker import mojibake_drop_reason

    fr = (
        "### 3. D\u00e9connexion du travail\n\n"
        "La d\u00e9connexion du travail signifie:\n\n"
        "- L'engagement de la Soci\u00e9t\u00e9 de ne pas solliciter le salari\u00e9 "
        "pendant les p\u00e9riodes de repos;\n\n"
        "Chez GitLab (ci-apr\u00e8s la \u00abSoci\u00e9t\u00e9\u00bb), nous veillons \u00e0 "
        "la s\u00e9curit\u00e9, \u00e0 la sant\u00e9 et au bien-\u00eatre."
    )
    assert mojibake_drop_reason(fr) is None, (
        "French accents/guillemets are not mojibake — must survive"
    )


def test_url_runs_and_acronyms_not_vowelless_garbage():
    from app.ingestion_v2.chunker import mojibake_drop_reason

    day5 = (
        "## Day 5\n\n"
        "- Watch the [DevSecOps](https://www.youtube.com/watch?v=PH9Z_znll40"
        "&list=PL05JrBw4t0Kpczt4pRtyF147Uvn2bGGvq&index=8) webinar - 30 minutes.\n"
        "- Read how to [secure your application]"
        "(https://docs.gitlab.com/ee/user/application_security/).\n"
    )
    assert mojibake_drop_reason(day5) is None, (
        "URL letter-runs must not score as Krutidev vowelless words"
    )
    german = (
        "### Statutory Part-Time Rights (\u00a7 8 TzBfG)\n\n"
        "Team members employed for 6+ months have the legal right to request "
        "permanent reduction of working hours under [\u00a7 8 TzBfG]"
        "(https://www.gesetze-im-internet.de/tzbfg/__8.html).\n"
    )
    assert mojibake_drop_reason(german) is None, (
        "mixed-case acronyms (TzBfG) must not trip the vowelless gate"
    )


def test_vowelless_gate_pdf_only_and_16_word_minimum():
    # Phase 3 (approved): the Krutidev signature is a scanned-PDF font-
    # decoding artifact — runs ONLY for pdf-sourced chunks, and needs 16
    # evaluated words (at 8, one vowelless word scored 0.125 and killed
    # 22 pure-English md/txt fragments in dry-run #10).
    from app.ingestion_v2.chunker import (
        VOWELLESS_MIN_WORDS,
        mojibake_drop_reason,
        vowelless_word_ratio,
    )

    assert VOWELLESS_MIN_WORDS == 16
    garbage = " ".join(["jftlv"] * 20)
    assert mojibake_drop_reason(garbage, source_type="pdf") == "non_english"
    assert mojibake_drop_reason(garbage, source_type="md") is None, (
        "vowelless gate must not run for non-PDF sources"
    )
    # labour-PDF garbage evaluates 20-21 words: still caught at min=16;
    # 15 evaluated words never fire (statistical-stability guard)
    short = " ".join(["jftlv"] * 15)
    assert vowelless_word_ratio(short) is None
    assert mojibake_drop_reason(short, source_type="pdf") is None


def test_inline_a_href_survives_md_roundtrip():
    # markdown-it emits <a href>text</a> as three separate inline tokens;
    # the opening tag alone used to serialize to "" and lose the href.
    from app.ingestion_v2.chunker import chunk_doc
    from app.ingestion_v2.md_parser import parse_markdown

    md = (
        "# Doc\n\n"
        'See <a href="https://example.com/docs?x=1">the docs</a> for '
        "background information on this procedure and its many details.\n\n"
        'Contact <a href="mailto:sec@example.com">sec@example.com</a> about '
        "anything related to this long paragraph of context words here.\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    assert drops == [], [(d.reason, d.preview) for d in drops]
    text = "\n".join(d.text_md for d in drafts)
    assert "[the docs](https://example.com/docs?x=1)" in text, (
        "inline <a href> must serialize with its href preserved"
    )
    assert "<sec@example.com>" in text, (
        "mailto anchor must become an autolink with href preserved"
    )


def test_sole_sub50_record_doc_dropped_as_stub():
    # doc-level stub rule (user-approved): a document whose entire kept
    # content is one draft under 50 chars (list-length exemption would have
    # kept it) drops as too_short — no sub-50 chunk may survive.
    from app.ingestion_v2.chunker import chunk_doc
    from app.ingestion_v2.md_parser import parse_markdown

    md = "### SEO and Keywords for Agile\n\n- Keyword\n- etc.\n"
    drafts, drops = chunk_doc(parse_markdown(md))
    assert drafts == [], [d.text_md for d in drafts]
    assert [d.reason for d in drops] == ["too_short"]


def test_empty_heading_stub_dropped_not_merged():
    pad = "This is real content with enough words to stay afloat here. "
    md = (
        "# Doc\n\n"
        f"## Section A\n\n{pad * 8}\n\n"
        "## Health & Well-Being\n\n"
        f"## Section B\n\n{pad * 8}\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    joined = "\n".join(d.text_md for d in drafts)
    assert "Health & Well-Being" not in joined, (
        "empty heading stub must be dropped, not merged into a neighbor"
    )
    reasons = {d.reason for d in drops}
    assert reasons & {"empty_stub", "too_short", "few_words"}


def test_cross_section_merge_keeps_host_path_inlines_stub_heading():
    pad = "This is real content with enough words to stay afloat here. "
    md = (
        "# Doc\n\n"
        f"## Section A\n\n{pad * 8}\n\n"
        "## Tiny Section\n\nOne-liner content that is small but real prose text.\n\n"
        f"## Section B\n\n{pad * 8}\n"
    )
    drafts, _ = chunk_doc(parse_markdown(md))
    host = [d for d in drafts if "One-liner" in d.text_md]
    assert host, "small non-empty section must cross-section merge, not drop"
    # forward pass runs first: the PREVIOUS chunk is the host, so the stub
    # heading stays inline while the host keeps its own heading_path
    assert host[0].heading_path[-1] == "Section A", "host keeps ITS heading_path"
    assert "## Tiny Section" in host[0].text_md, "stub heading stays inline"


def test_short_chunks_under_50_are_zero_in_dryrun_records():
    # invariant the new gate enforces on the real corpus; here we assert the
    # chunker itself never emits <50-char drafts for a realistic document
    pad = "Sentence about leave policy with enough ordinary words to survive. "
    md = "# T\n\n" + pad * 5 + "\n"
    drafts, _ = chunk_doc(parse_markdown(md))
    assert drafts
    assert all(len(d.text_md) >= 50 for d in drafts)


# ---------------- plan Phase 1 conditions 1-2: numeric / lists / placeholders

def test_page_number_dropped_only_in_three_scanned_sources():
    body = (
        "Agreement preamble with enough ordinary words to be kept as content "
        "here for the test to be meaningful and stable.\n\n"
    )
    tail = "\nMore agreement words follow in the body text of the document.\n"

    # cuad_txt: bare integer + "- N -" page shapes drop as page_number
    parsed = parse_cuad_txt(body + "36\n\n- 36 -\n" + tail)
    _, drops = chunk_doc(parsed)
    page_reasons = [d for d in drops if d.reason == "page_number"]
    assert len(page_reasons) == 2, [d.preview for d in drops]
    assert all(d.block_type == "prose" for d in page_reasons)
    assert not any(d.reason == "no_alpha" for d in drops)

    # pdf: "Page 7" shape (construct the pdf-typed doc from markdown blocks)
    parsed = parse_markdown(body + "Page 7\n" + tail)
    parsed.source_type = "pdf"
    _, drops = chunk_doc(parsed)
    assert [d.reason for d in drops if d.block_type == "prose"] == ["page_number"]

    # sec_htm: bare integer
    parsed = parse_markdown(body + "12\n" + tail)
    parsed.source_type = "sec_htm"
    _, drops = chunk_doc(parsed)
    assert [d.reason for d in drops] == ["page_number"]
    assert not any(d.reason == "no_alpha" for d in drops)


def test_page_number_never_drops_in_markdown_sources():
    # gate allowlist scope: page_number exists ONLY for cuad_txt/pdf/sec_htm;
    # in .md a bare number merges forward instead (handbook rule)
    body = "Start of the section with plenty of real content words here.\n\n"
    md = "# Doc\n\n" + body + "27\n\n" + body + "More prose continues the section.\n"
    drafts, drops = chunk_doc(parse_markdown(md))
    assert not any(d.reason == "page_number" for d in drops)
    assert not any(d.reason == "no_alpha" for d in drops)
    assert any(re.search(r"(?m)^27$", d.text_md) for d in drafts), (
        "bare number must survive by merging, never no_alpha/page_number"
    )


def test_section_number_prefixes_next_block():
    md = (
        "# Doc\n\n"
        "Start of the section with plenty of real content words here.\n\n"
        "2.1\n\n"
        "More prose continues the section with enough words to pass the gates.\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    assert not drops, [d.reason for d in drops]
    host = next(d for d in drafts if "More prose continues" in d.text_md)
    assert host.text_md.index("2.1") < host.text_md.index("More prose continues"), (
        "numeric block must merge forward as a prefix of the next block"
    )


def test_handbook_numeric_merges_never_dropped():
    # condition 1 (amended): numeric-only NEVER dies under no_alpha anywhere
    md = (
        "# Handbook Section\n\n"
        "Plenty of ordinary handbook prose keeps this chunk alive and safe.\n\n"
        "1042\n\n"
        "The next paragraph has enough ordinary words to remain in the corpus.\n"
    )
    for doc in (parse_markdown(md),):
        drafts, drops = chunk_doc(doc)
        assert drops == [], [d.reason for d in drops]
        assert any("1042" in d.text_md for d in drafts)
        assert all(d.reason != "no_alpha" for d in drops)


def test_unmergeable_letterless_numeric_drops_as_junk_not_kept():
    # plan canary (chunks with zero alphabetic words = 0): redaction residue
    # ([***] 201802) that neither merge pass can attach must drop as
    # junk_fragment — never kept (zero-alpha), never under no_alpha (gate [09]).
    from app.ingestion_v2.chunker import count_tokens

    words = (
        "The parties agree to observe the covenants obligations and "
        "representations set forth in this agreement at all times"
    ).split()

    def big_para() -> str:
        para = ""
        for w in words * 40:
            cand = f"{para} {w}".strip()
            if count_tokens(cand) > 796:
                break
            para = cand
        return para

    residue = "[***] [***] 201802 [***] [***] [***] 201804 [***]"
    md = f"{big_para()}\n\n{residue}\n\n{big_para()}\n"
    drafts, drops = chunk_doc(parse_markdown(md))
    kept = [d.text_md for d in drafts]
    assert kept and all(re.search(r"[A-Za-z]", t) for t in kept), (
        "no zero-alphabetic chunk may survive"
    )
    assert not any(residue in t for t in kept), "unmergeable residue must not be kept"
    junk = [d for d in drops if "201802" in d.text]
    assert junk, [(d.reason, d.preview[:60]) for d in drops]
    assert all(d.reason == "junk_fragment" for d in junk), [
        (d.reason, d.preview[:60]) for d in junk
    ]
    assert all(d.reason != "no_alpha" for d in junk)


def test_standalone_symbols_drop_but_inline_markers_retain():
    # condition 1 evidence: symbol_letterless ([***], [...***…]) may drop;
    # a block merely CONTAINING a redaction marker inline is real content
    pad = "Redaction context sentence with enough words to keep the chunk. "
    md = (
        "# Doc\n\n"
        f"{pad}Payload is [***] redacted in this paragraph. {pad}\n\n"
        "[***]\n\n"
        f"{pad * 3}\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    joined = "\n".join(d.text_md for d in drafts)
    assert "[***]" in joined, "inline redaction marker must stay in kept text"
    assert any(d.reason == "no_alpha" for d in drops), (
        "standalone [***] block still drops as no_alpha"
    )
    assert all("redacted" in d.text_md for d in drafts if "[***]" in d.text_md), (
        "the KEEPING of [***] must be inside a prose draft, not a dropped one"
    )


def test_list_items_never_drop_for_length():
    # condition 2: short list items merge (no junk_fragment/too_short/few_words)
    md = (
        "# H\n\n"
        "Enough prose words in this paragraph to keep it alive for sure here.\n\n"
        "- 2 FE\n- 1 BE\n\n"
        "Closing prose paragraph with enough words to remain in the corpus.\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    assert drops == [], [(d.reason, d.preview) for d in drops]
    assert any("- 2 FE" in d.text_md for d in drafts)


def test_secrets_manager_capacity_lists_survive_e2e():
    # end-to-end condition 2: the real doc that lost its capacity lists
    path = (
        CORPUS / "engineering" / "gitlab_handbook" / "engineering" / "devops"
        / "project-plans" / "secrets-manager.md"
    )
    if not path.is_file():
        pytest.skip("secrets-manager.md missing")
    parsed = parse_markdown(path.read_text(encoding="utf-8", errors="replace"))
    drafts, drops = chunk_doc(parsed)
    hosts = [d for d in drafts if "- 2 FE" in d.text_md]
    assert hosts, "capacity list items must survive into a kept chunk"
    for host in hosts:
        idx = host.text_md.index("- 2 FE")
        before = host.text_md[:idx]
        assert "Team Capacity" in before[-120:], (
            "the - 2 FE item must sit under its #### Team Capacity sub-heading"
        )
    assert all(len(d.text_md) >= 50 for d in drafts), "no tiny chunks"
    assert not any(d.reason == "junk_fragment" for d in drops), (
        "condition 2: list items are never junk_fragment"
    )
    stubs = [d for d in drops if d.reason == "empty_stub"]
    assert len(stubs) > 0, "condition 3: heading-only stubs listed as empty_stub"


def test_cjk_and_devanagari_are_letters_not_junk():
    # condition 1: Unicode letters (not ASCII) are content — they may be
    # dropped by the LANGUAGE gate (non_english, an English corpus), but they
    # must never be misclassified as letterless junk (no_alpha/junk/too short)
    cjk = "# 中文章节\n\n" + ("这是一段足够长的中文内容用于测试是否会被错误地丢弃掉并且保留下来。" * 2) + "\n"
    drafts, drops = chunk_doc(parse_markdown(cjk))
    reasons = {d.reason for d in drops}
    assert reasons <= {"non_english", "mojibake_suspect"}, reasons
    assert not reasons & {"no_alpha", "junk_fragment", "few_words", "too_short"}
    if not drafts:
        assert "non_english" in reasons, "CJK may only drop via the language gate"
    else:
        assert any("中文" in d.text_md for d in drafts), "CJK paragraph must be kept"

    deva = (
        "# हिन्दी\n\n"
        "यह एक परीक्षण है जो पर्याप्त शब्दों के साथ लिखा गया है ताकि यह "
        "पर्याप्त रूप से लंबा और अर्थपूर्ण बना रहे और इसे संग्रह में रखा जा सके।\n"
    )
    drafts, drops = chunk_doc(parse_markdown(deva))
    reasons = {d.reason for d in drops}
    assert not reasons & {"no_alpha", "junk_fragment", "few_words", "too_short"}, reasons
    assert reasons <= {"non_english", "mojibake_suspect"}, reasons


def test_placeholder_markers_survive_backticked_and_literal():
    # condition: placeholders stay (backticked in text_md, raw in plain/embed)
    md = (
        "# Doc\n\n"
        "Contact the approver: <Contact Name> will review this request with "
        "enough surrounding words to keep the paragraph safely above limits.\n\n"
        "> Escalate to <account owner\\> within the agreed upon time window.\n"
    )
    drafts, drops = chunk_doc(parse_markdown(md))
    joined = "\n".join(d.text_md for d in drafts)
    plains = "\n".join(d.plain for d in drafts)
    assert "`<Contact Name>`" in joined, "placeholder kept, backticked in text_md"
    assert "<Contact Name>" in plains, "placeholder literal in plain (embed text)"
    assert "`<account owner>" in joined or "<account owner>" in joined, (
        "escaped placeholder variant must also survive"
    )
    assert not any(d.reason == "no_alpha" for d in drops)


# ------------------------------------------------- table pipes + source scrub

def test_table_code_span_pipes_escaped_and_cells_kept():
    md = (
        "| Feature | Runner |\n"
        "|---|---|\n"
        "| auth | `register_{group|project}_runner` |\n"
        "| issues | see [issues/386712](https://github.com/x/y/issues/386712) `a|b` |\n"
        "| pre | `already\\|escaped` |\n"
    )
    parsed = parse_markdown(md)
    table = next(b for b in parsed.blocks if b.kind == "table")
    assert "register_{group\\|project}_runner" in table.md, "code-span pipe escaped"
    assert "issues/386712" in table.md, "cells after an in-span pipe are kept"
    assert "already\\|escaped" in table.md, "no double escape of pre-escaped pipes"
    assert "\\\\|" not in table.md, "never double backslash before pipe"
    assert "Feature" in table.md and "Runner" in table.md, "all header cells intact"


def test_escape_table_code_pipes_skips_fences_and_prose():
    md = (
        "prose with `code|pipe` stays\n"
        "```\n"
        "| not | a | table |\n"
        "```\n"
        "| a | `x|y` |\n"
    )
    out = escape_table_code_pipes(md)
    assert "| not | a | table |" in out, "fence content untouched"
    assert "prose with `code|pipe` stays" in out, "prose untouched"
    assert "| a | `x\\|y` |" in out, "table row escaped"


def test_source_tokens_md_drops_design_attrs_keeps_content():
    raw = (
        'keep <a href="https://ex.com/a">link</a> and <https://ex.com/auto> '
        "and <Marker Text> in text\n"
        '<img src="https://ex.com/i.png?w=100&amp;h=50" alt="x">\n'
        '<form action="https://ex.com/f"><input type="text"></form>\n'
        '<svg viewBox="0 0 1 1"><path d="https://ex.com/svg"/></svg>\n'
    )
    toks = tokens_of(source_tokens_text(raw, ".md"), with_urls=True)
    assert "https://ex.com/a" in toks, "anchor href is content"
    assert "https://ex.com/auto" in toks, "autolink is content"
    assert "<Marker Text>" in toks, "placeholder is content"
    assert not any("i.png" in t for t in toks), "img attribute URL excluded"
    assert not any("ex.com/f" in t for t in toks), "form action URL excluded"
    assert not any("ex.com/svg" in t for t in toks), "svg attribute URL excluded"


def test_source_tokens_html_hides_ix_hidden_comments_script():
    raw = (
        "<body><p>visible https://ex.com/vis</p>"
        "<ix:hidden><a href='https://ex.com/hidden'>x</a></ix:hidden>"
        "<!-- https://ex.com/comment -->"
        "<script>https://ex.com/js</script>"
        "</body>"
    )
    txt = source_tokens_text(raw, ".htm")
    assert "ex.com/vis" in txt, "visible content kept"
    assert "ex.com/hidden" not in txt, "ix:hidden XBRL region excluded"
    assert "ex.com/comment" not in txt, "HTML comment excluded"
    assert "ex.com/js" not in txt, "script block excluded"


def test_norm_url_cuts_table_pipes_and_scheme_only_is_empty():
    assert norm_url("https://|") == "", "scheme-only after pipe cut is not a URL"
    assert norm_url("https://x.example/a|Full|") == "https://x.example/a"
    assert norm_url("https://x.example/a,") == "https://x.example/a"
    toks = tokens_of("see https://| and https://x.example/b", with_urls=True)
    assert "https://x.example/b" in toks
    assert "" not in toks


def test_source_tokens_drops_silently_hidden_regions():
    # htmlconv._cleanup_soup decomposes aria-hidden divs and display:none
    # elements WITHOUT a drop record; the source side must not count them,
    # while visible content and placeholders around them stay.
    md_raw = (
        '<div class="modal fade" aria-hidden="true">\n'
        '  <a href="https://ex.com/hidden">Watch</a>\n'
        "</div>\n\n"
        "visible text with <Marker Text> and https://ex.com/visible\n"
        '<p style="display: none">gone https://ex.com/muted</p>\n'
    )
    txt = source_tokens_text(md_raw, ".md")
    toks = tokens_of(txt, with_urls=True)
    assert "https://ex.com/hidden" not in toks, "aria-hidden subtree excluded"
    assert "https://ex.com/muted" not in toks, "display:none element excluded"
    assert "https://ex.com/visible" in toks, "visible URL kept"
    assert "<Marker Text>" in toks, "placeholder survives the soup pass"
    assert "visible text with" in txt, "visible prose kept"


def test_drop_design_hidden_preserves_fences():
    raw = (
        "```html\n"
        '<div aria-hidden="true">https://ex.com/in-fence</div>\n'
        "```\n"
        "keep https://ex.com/outside\n"
    )
    txt = source_tokens_text(raw, ".md")
    assert "ex.com/in-fence" in txt, "fenced html is code, not a hidden region"
    assert "ex.com/outside" in txt
