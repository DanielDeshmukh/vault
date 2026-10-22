"""Phase 4 / CP3-decision tests: chunk hydration ACL, no-answer threshold,
rerank score write-back, citation chunk handles.

Logic-level tests (no network, no database): the endpoint's security
decision and the score-scale gate are pure functions, so they are exercised
directly; the live hydration path is verified against the running server at
CHECKPOINT 4.
"""

import asyncio
from types import SimpleNamespace

from app.api.documents import acl_grants
from app.api.queries import NO_ANSWER_TEXT, below_relevance_threshold
from app.config import settings
from app.retrieval.generator import CitationGenerator
from app.retrieval.search import HybridSearch, SearchResult

# --- chunk ACL (deny-by-default) -------------------------------------------


def test_acl_admin_bypasses_any_acl():
    assert acl_grants(None, {"legal"}) is True
    assert acl_grants(None, set()) is True


def test_acl_requires_role_intersection():
    assert acl_grants(["employee", "engineer"], {"engineer"}) is True
    assert acl_grants(["employee"], {"legal", "finance"}) is False


def test_acl_denies_roleless_user_even_with_open_acl():
    # A user holding no roles must never match, even on a wide-open ACL.
    assert acl_grants([], {"employee", "legal"}) is False
    assert acl_grants([], set()) is False


def test_acl_matches_case_insensitively():
    # Corpus ACLs are lowercase; legacy tier roles arrive as "Internal".
    assert acl_grants(["Internal"], {"internal"}) is True


# --- no-answer threshold (plan decision locked at CP3) ---------------------


def _flow(search: HybridSearch, *, reranked: bool, fallback: bool) -> None:
    search.last_flow = {"reranked": reranked, "rerank_fallback": fallback}


def _result(score: float) -> SearchResult:
    return SearchResult(id="doc_x#0001", content="body " * 20, score=score, metadata={})


def test_threshold_triggers_when_no_results():
    hs = HybridSearch()
    _flow(hs, reranked=True, fallback=False)
    assert below_relevance_threshold(hs, []) is True


def test_threshold_gates_low_rerank_score():
    hs = HybridSearch()
    _flow(hs, reranked=True, fallback=False)
    low = max(settings.RERANK_NO_ANSWER_THRESHOLD - 0.05, 0.0)
    assert below_relevance_threshold(hs, [_result(low)]) is True


def test_threshold_passes_strong_rerank_score():
    hs = HybridSearch()
    _flow(hs, reranked=True, fallback=False)
    strong = min(settings.RERANK_NO_ANSWER_THRESHOLD + 0.3, 1.0)
    assert below_relevance_threshold(hs, [_result(strong)]) is False


def test_threshold_skips_vector_score_scale():
    # Fallback keeps cosine scores: a different scale than the rerank
    # threshold, so gating on it would randomly deny good answers.
    hs = HybridSearch()
    _flow(hs, reranked=True, fallback=True)
    assert below_relevance_threshold(hs, [_result(0.12)]) is False

    _flow(hs, reranked=False, fallback=False)
    assert below_relevance_threshold(hs, [_result(0.12)]) is False


def test_no_answer_text_is_stable_and_nonempty():
    # The UI wording for the gate is fixed server-side, not model-generated.
    assert isinstance(NO_ANSWER_TEXT, str) and len(NO_ANSWER_TEXT) > 20


# --- rerank relevance score write-back -------------------------------------


def test_rerank_replaces_score_with_relevance_score():
    from app.retrieval.reranker import CohereReranker

    reranker = CohereReranker.__new__(CohereReranker)
    reranker.model = "rerank-english-v3.0"

    candidates = [
        SearchResult(id="a", content="first candidate text", score=0.99, metadata={}),
        SearchResult(id="b", content="second candidate text", score=0.98, metadata={}),
        SearchResult(id="c", content="third candidate text", score=0.97, metadata={}),
    ]

    def fake_rerank(*, query, documents, top_n, model):
        assert len(documents) == 3
        # Cohere returns best-first with relevance scores that disagree with
        # the vector order; both must be reflected on the results.
        return SimpleNamespace(
            results=[
                SimpleNamespace(index=2, relevance_score=0.91),
                SimpleNamespace(index=0, relevance_score=0.42),
            ]
        )

    reranker.client = SimpleNamespace(rerank=fake_rerank)
    reranked = asyncio.run(reranker.rerank("q", candidates, top_k=2))

    assert [r.id for r in reranked] == ["c", "a"]
    assert reranked[0].score == 0.91
    assert reranked[1].score == 0.42


def test_rerank_safe_flags_fallback_and_keeps_order():
    from app.retrieval.reranker import CohereReranker

    reranker = CohereReranker.__new__(CohereReranker)

    def exploding_rerank(**kwargs):
        raise RuntimeError("rate limited")

    reranker.client = SimpleNamespace(rerank=exploding_rerank)
    candidates = [_result(0.9), _result(0.8)]
    kept = asyncio.run(reranker.rerank_safe("q", candidates, top_k=5))

    assert reranker.used_fallback is True
    assert [r.id for r in kept] == [r.id for r in candidates]


# --- citation chunk handles -------------------------------------------------


def test_extract_citations_carries_chunk_id_for_preview():
    gen = CitationGenerator.__new__(CitationGenerator)
    results = [
        SearchResult(
            id="doc_hr_0001#0002",
            content="Employees accrue vacation time.",
            score=0.93,
            metadata={"doc_id": "doc_hr_0001", "source_title": "Leave Policy", "department": "hr"},
        )
    ]
    citations = gen.extract_citations("Vacation rules apply. [doc_hr_0001]", results)
    assert citations[0]["chunk_id"] == "doc_hr_0001#0002"
