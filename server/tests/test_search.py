import asyncio

from app.retrieval.generator import CitationGenerator
from app.retrieval.search import (
    CANDIDATE_WIDTH,
    MIN_CANDIDATE_CHARS,
    MIN_CANDIDATE_WORDS,
    HybridSearch,
    SearchResult,
    apply_safety_net,
    dedupe_by_content_hash,
    expand_query,
)


def make(rid, content, score=0.5, md=None):
    return SearchResult(id=rid, content=content, score=score, metadata=md or {})


# --- expand_query: punctuation fix (plan Phase 3) ---


def test_expand_query_keeps_punctuated_words():
    variants = expand_query("What are the employee leave policies?")

    assert variants[0] == "What are the employee leave policies?"
    assert "employee leave policies" in variants


def test_expand_query_keyword_variant_drops_stop_words():
    variants = expand_query("What are the employee leave policies?")

    assert variants[-1] == "employee leave policies"


def test_expand_query_skips_keyword_variant_identical_to_query():
    assert expand_query("leave policies") == ["leave policies"]


def test_expand_query_expansion_still_fires_despite_punctuation():
    variants = expand_query("Do I get parental time off?")

    assert any("vacation PTO" in v for v in variants)


# --- safety net (plan Phase 3) ---


def test_safety_net_drops_short_and_few_word_candidates():
    ok = make("ok", "Employees accrue paid time off at one day per month of service.")
    tiny = make("tiny", "See policy.")
    few_words = make("few", "one two three " + "." * 40)

    kept = apply_safety_net([ok, tiny, few_words])

    assert [r.id for r in kept] == ["ok"]


def test_safety_net_thresholds():
    assert MIN_CANDIDATE_CHARS == 50
    assert MIN_CANDIDATE_WORDS == 5
    assert CANDIDATE_WIDTH == 50


# --- dedupe by content_hash (plan Phase 3) ---


def test_dedupe_prefers_higher_score_same_hash():
    a = make("a", "same body", score=0.9, md={"content_hash": "h1"})
    b = make("b", "same body", score=0.7, md={"content_hash": "h1"})
    c = make("c", "other body", score=0.5, md={"content_hash": "h2"})

    kept = dedupe_by_content_hash([a, b, c])

    assert [r.id for r in kept] == ["a", "c"]


def test_dedupe_falls_back_to_sha256_of_content():
    a = make("a", "identical text without stored hash", score=0.8)
    b = make("b", "identical text without stored hash", score=0.6)

    kept = dedupe_by_content_hash([a, b])

    assert [r.id for r in kept] == ["a"]


# --- full search flow: wide fetch, no pre-rerank cut, final top_k ---


class FakePinecone:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    async def query_vectors(self, *, vector, top_k, filter, include_metadata):
        self.calls.append({"top_k": top_k, "filter": filter})
        return self.matches[:top_k]


class RecordingReranker:
    seen_sizes = []
    used_fallback = False

    def __init__(self):
        pass

    async def rerank_safe(self, query, results, top_k):
        RecordingReranker.seen_sizes.append(len(results))
        return results


def test_search_fetches_width_reranks_before_cut(monkeypatch):
    matches = []
    for i in range(CANDIDATE_WIDTH + 10):
        body = f"Candidate {i}: " + "employees may request personal leave. " * 5
        matches.append({
            "id": f"m{i}",
            "score": 1.0 - i * 0.01,
            "metadata": {
                "text": body,
                "content_hash": f"h{i}",
                "doc_id": f"d{i}",
                "source_title": "Leave Policy",
                "department": "hr",
            },
        })

    fake_pc = FakePinecone(matches)
    hs = HybridSearch()
    hs.pinecone = fake_pc

    async def fake_filter(user):
        return {"allowed_roles": {"$in": ["employee", "engineer"]}}

    async def fake_embed(texts):
        return [[float(i)] + [0.0] * 7 for i in range(len(texts))]

    monkeypatch.setattr(hs, "_get_filter", fake_filter)
    monkeypatch.setattr(hs, "_get_embeddings", fake_embed)
    RecordingReranker.seen_sizes.clear()
    monkeypatch.setattr(
        "app.retrieval.reranker.CohereReranker", RecordingReranker
    )

    results = asyncio.run(
        hs.search("employee leave policies", user=object(), top_k=6)
    )

    assert fake_pc.calls[0]["top_k"] == CANDIDATE_WIDTH
    assert fake_pc.calls[0]["filter"] == {"allowed_roles": {"$in": ["employee", "engineer"]}}
    # The full cleaned candidate set reaches the reranker (no pre-cut):
    # 50 candidates in, top_k=6 out — the cut happens only after rerank.
    assert RecordingReranker.seen_sizes == [CANDIDATE_WIDTH]
    assert hs.last_flow["fetched"] == CANDIDATE_WIDTH
    assert hs.last_flow["merged_by_id"] == CANDIDATE_WIDTH
    assert hs.last_flow["after_dedupe"] == CANDIDATE_WIDTH
    assert hs.last_flow["reranked"] is True
    assert len(results) == 6
    assert hs.last_flow["final"] == 6


def test_search_dedupes_and_safety_nets_before_rerank(monkeypatch):
    long_text = "Employees may request personal leave. " * 4
    matches = [
        {"id": "dup1", "score": 0.9,
         "metadata": {"text": long_text, "content_hash": "same", "doc_id": "d1"}},
        {"id": "dup2", "score": 0.8,
         "metadata": {"text": long_text, "content_hash": "same", "doc_id": "d2"}},
        {"id": "junk", "score": 0.7, "metadata": {"text": "ok.", "doc_id": "d3"}},
        {"id": "real", "score": 0.6,
         "metadata": {"text": "A fully valid policy chunk that clears both safety checks.",
                      "content_hash": "other", "doc_id": "d4"}},
    ]

    fake_pc = FakePinecone(matches)
    hs = HybridSearch()
    hs.pinecone = fake_pc

    async def fake_filter(user):
        return None

    async def fake_embed(texts):
        return [[0.0] for _ in texts]

    monkeypatch.setattr(hs, "_get_filter", fake_filter)
    monkeypatch.setattr(hs, "_get_embeddings", fake_embed)
    RecordingReranker.seen_sizes.clear()
    monkeypatch.setattr(
        "app.retrieval.reranker.CohereReranker", RecordingReranker
    )

    results = asyncio.run(hs.search("leave", user=object(), top_k=5))

    assert hs.last_flow["merged_by_id"] == 4
    assert hs.last_flow["after_safety_net"] == 3  # "ok." dropped
    assert hs.last_flow["after_dedupe"] == 2      # dup2 + junk hash-dupes removed
    assert RecordingReranker.seen_sizes == [2]
    assert [r.id for r in results] == ["dup1", "real"]


# --- citation access check (plan Phase 3) ---


def test_extract_citations_only_returns_accessed_results():
    gen = CitationGenerator.__new__(CitationGenerator)
    results = [
        make(
            "chunk-1",
            "Employees may request personal leave.",
            score=0.9,
            md={"doc_id": "doc_a", "source_title": "Leave Policy", "department": "hr"},
        )
    ]

    answer = "Policies apply [doc_a], but also cite [doc_secret] which was filtered out."
    citations = gen.extract_citations(answer, results)

    assert [c["document_id"] for c in citations] == ["doc_a"]


# --- hydration ACL re-check (plan Phase 6 / line 138) ---
#
# An id the RBAC filter does not allow must never enter the Postgres IN list,
# and ids without a document_chunks_v2 row (legacy corpus) keep their
# metadata content so production behaviour is unchanged until the switch.


class HydrationSpy:
    """Stands in for _fetch_full_text and records exactly which ids were asked for."""

    def __init__(self, rows: dict[str, str]):
        self.rows = rows
        self.asked: list[list[str]] = []

    async def fetch(self, ids: list[str]) -> dict[str, str]:
        self.asked.append(list(ids))
        return {i: self.rows[i] for i in ids if i in self.rows}


def hydrate(results, filter_dict, rows):
    hs = HybridSearch()
    spy = HydrationSpy(rows)
    hs._fetch_full_text = spy.fetch
    hydrated, checked = asyncio.run(hs._hydrate(results, filter_dict))
    return hydrated, checked, spy


def test_hydrate_fetches_only_acl_allowed_ids():
    ok = make(
        "ok",
        "snippet",
        md={"allowed_roles": ["Engineer"]},  # mixed case on purpose
    )
    forbidden = make(
        "secret",
        "restricted snippet",
        md={"allowed_roles": ["legal"]},
    )
    filt = {"allowed_roles": {"$in": ["engineer", "admin"]}}

    hydrated, checked, spy = hydrate(
        [ok, forbidden], filt, {"ok": "full text from postgres"}
    )

    assert spy.asked == [["ok"]]
    assert (hydrated, checked) == (1, 1)
    assert ok.content == "full text from postgres"
    assert forbidden.content == "restricted snippet"


def test_hydrate_all_rejected_never_queries_postgres():
    a = make("a", "x", md={"allowed_roles": ["legal"]})
    b = make("b", "y", md={"allowed_roles": ["hr"]})
    filt = {"allowed_roles": {"$in": ["engineer"]}}

    hydrated, checked, spy = hydrate([a, b], filt, {"a": "should not be read"})

    assert spy.asked == []
    assert (hydrated, checked) == (0, 0)
    assert a.content == "x" and b.content == "y"


def test_hydrate_without_filter_checks_everything():
    a = make("a", "snip a")
    b = make("b", "snip b")

    hydrated, checked, spy = hydrate([a, b], None, {"a": "full a"})

    assert spy.asked == [["a", "b"]]
    assert (hydrated, checked) == (1, 2)
    assert a.content == "full a"
    assert b.content == "snip b"  # no v2 row -> metadata content kept


def test_hydrate_legacy_id_without_v2_row_keeps_metadata_content():
    legacy = make("doc_hr_0001#0001", "legacy metadata text",
                  md={"allowed_roles": ["hr"]})
    filt = {"allowed_roles": {"$in": ["hr"]}}

    hydrated, checked, spy = hydrate([legacy], filt, {})

    assert spy.asked == [["doc_hr_0001#0001"]]
    assert (hydrated, checked) == (0, 1)
    assert legacy.content == "legacy metadata text"


def test_hydrate_empty_results_returns_zero_without_fetch():
    spy_rows = {"x": "text"}
    hydrated, checked, spy = hydrate([], None, spy_rows)

    assert (hydrated, checked) == (0, 0)
    assert spy.asked == []
