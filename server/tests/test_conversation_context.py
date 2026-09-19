from app.retrieval.generator import CitationGenerator
from app.retrieval.search import SearchResult


def test_build_messages_uses_conversation_context_to_resolve_follow_ups():
    generator = CitationGenerator.__new__(CitationGenerator)
    result = SearchResult(
        id="leave-policy",
        content="Employees may request personal leave.",
        score=0.9,
        metadata={"document_id": "leave-policy", "title": "Leave policy"},
    )

    messages = generator._build_messages(
        "Explain each in one line.",
        [result],
        conversation_context="User: What are the employee leave policies?\nAssistant: Bereavement and personal leave are covered.",
    )

    assert "CONVERSATION CONTEXT" in messages[1]["content"]
    assert "What are the employee leave policies?" in messages[1]["content"]
    assert "resolving references" in messages[1]["content"]
