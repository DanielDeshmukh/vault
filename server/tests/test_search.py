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
