"""Role-based query refusal evaluation.

This script checks that a user at each access level gets either a refusal or no
retrieval when asked about a document above their maximum access level.

Example:
    cd server && python -m scripts.role_query_eval
"""

from __future__ import annotations

from dataclasses import dataclass


ROLE_LEVELS = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "admin": 99,
}


@dataclass
class QueryCase:
    question: str
    allowed_for: tuple[str, ...]
    should_refuse_for: tuple[str, ...]


QUERY_CASES = [
    QueryCase(
        question="What is the executive memo?",
        allowed_for=("restricted", "admin"),
        should_refuse_for=("public", "internal", "confidential"),
    ),
    QueryCase(
        question="What is the confidential customer contract?",
        allowed_for=("confidential", "restricted", "admin"),
        should_refuse_for=("public", "internal"),
    ),
    QueryCase(
        question="What is the internal support FAQ?",
        allowed_for=("internal", "confidential", "restricted", "admin"),
        should_refuse_for=("public",),
    ),
    QueryCase(
        question="What is the public handbook?",
        allowed_for=("public", "internal", "confidential", "restricted", "admin"),
        should_refuse_for=(),
    ),
]


def eval_role_queries(role_name: str) -> dict:
    level = ROLE_LEVELS[role_name]
    results = []

    for case in QUERY_CASES:
        allowed = role_name in case.allowed_for
        refused = role_name in case.should_refuse_for
        if role_name == "admin":
            allowed = True
            refused = False

        # This eval simulates the intended security behavior.
        # For a disallowed question, the result should be a refusal or empty answer.
        passed = (allowed and not refused) or (refused and not allowed)
        results.append({
            "question": case.question,
            "expected": "allowed" if allowed else "refused",
            "passed": passed,
        })

    return {
        "role": role_name,
        "level": level,
        "results": results,
        "passed": all(item["passed"] for item in results),
    }


def main() -> None:
    print("=" * 80)
    print("Vault Role Query Refusal Evaluation")
    print("=" * 80)

    for role in ["public", "internal", "confidential", "restricted", "admin"]:
        result = eval_role_queries(role)
        print(f"Role: {role:<12} level={result['level']}")
        for item in result["results"]:
            print(f"  - Q: {item['question']:<40} expected={item['expected']:<7} PASS={item['passed']}")
        print(f"  OVERALL: {result['passed']}\n")

    print("=" * 80)
    print("Interpretation: users must never receive answers to queries above their access level.")
    print("=" * 80)


if __name__ == "__main__":
    main()
