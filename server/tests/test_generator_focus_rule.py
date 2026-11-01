"""Phase-6 pre-embed checklist task 3: unmentioned country/entity guard.

When the question names a country/entity the retrieved sources never mention,
the generator must say what the sources cover instead of answering about it
(system rule 7 + dynamic UNMENTIONED FOCUS block). Japan and Germany are the
held-out regression cases.
"""
from __future__ import annotations

from app.retrieval.generator import CitationGenerator
from app.retrieval.search import SearchResult


def _res(doc_id: str, content: str) -> SearchResult:
    return SearchResult(
        id=f"{doc_id}#0000",
        content=content,
        score=0.7,
        metadata={
            "doc_id": doc_id,
            "source_title": f"Doc {doc_id}",
            "department": "general",
        },
    )


def test_focus_terms_detect_countries_and_entities():
    gen = CitationGenerator()
    jp = [t.lower() for t in gen._focus_terms("expense rules for business travel to Japan?")]
    assert "japan" in jp
    de = [t.lower() for t in gen._focus_terms("parental leave policy in Germany")]
    assert "germany" in de
    plain = [t.lower() for t in gen._focus_terms("how do expense reports work")]
    assert "japan" not in plain and "germany" not in plain


def test_rule_7_present_in_system_prompt():
    assert "countr" in CitationGenerator.SYSTEM_PROMPT.lower()
    assert "exception" in CitationGenerator.SYSTEM_PROMPT.lower()


def test_japan_guard_fires_when_no_source_mentions_japan():
    gen = CitationGenerator()
    results = [
        _res(
            "doc_finance_0042",
            "Expense reports must be submitted within 30 days of the transaction. "
            "Receipts are required for any single item over 25 USD.",
        )
    ]
    messages = gen._build_messages(
        "expense rules for business travel to Japan", results
    )
    user = messages[1]["content"]
    assert "UNMENTIONED FOCUS" in user
    assert "Japan" in user


def test_germany_guard_suppressed_when_sources_mention_germany():
    gen = CitationGenerator()
    results = [
        _res(
            "doc_general_0065",
            "GitLab GmbH (Germany): parental leave policy grants 14 weeks at full "
            "salary for primary caregivers.",
        )
    ]
    messages = gen._build_messages(
        "parental leave policy in Germany", results
    )
    assert "UNMENTIONED FOCUS" not in messages[1]["content"]


def test_germany_guard_is_country_presence_only_not_topic_coverage():
    """Characterize the guard: it does not catch country-mentioned/topic-uncovered.

    Rule 7 protects an unmentioned focus country/entity, not topical relevance.
    The normal source-only instruction remains the protection for this case.
    """
    gen = CitationGenerator()
    results = [
        _res(
            "doc_general_0099",
            "Germany travel reimbursement rules require receipts for rail fares and hotels.",
        )
    ]
    messages = gen._build_messages("parental leave policy in Germany", results)

    assert "UNMENTIONED FOCUS" not in messages[1]["content"]
    assert "Answer using ONLY the provided sources." in messages[0]["content"]
    assert "State briefly what the provided sources DO cover" in messages[0]["content"]


def test_guard_lists_multiple_uncovered_terms():
    gen = CitationGenerator()
    results = [
        _res("doc_hr_0001", "The leave policy covers vacation and sick leave only.")
    ]
    messages = gen._build_messages(
        "aguinaldo bonus rules in Mexico and France", results
    )
    user = messages[1]["content"]
    assert "UNMENTIONED FOCUS" in user
    assert "Mexico" in user and "France" in user
