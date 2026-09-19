from app.retrieval.search import expand_query


def test_expand_query_turns_leave_hints_into_a_query_string():
    variants = expand_query("What are the employee leave policies?")

    assert variants == [
        "What are the employee leave policies?",
        "What are the employee leave policies? time off absence absence",
    ]
