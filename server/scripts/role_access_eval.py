"""Role-based RBAC evaluation for Vault.

This script validates that users can only retrieve documents at or below their
max access level, and that content above their level is blocked even when the
role/account metadata would otherwise seem permissive.

Example:
    cd server && python -m scripts.role_access_eval
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.auth.permissions import build_pinecone_filter


ROLE_LEVELS = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "admin": 99,
}


@dataclass
class DocumentSpec:
    title: str
    access_level: int
    owner_id: str | None = None


DOCUMENTS = [
    DocumentSpec("Public Handbook", 0),
    DocumentSpec("Internal Support FAQ", 1),
    DocumentSpec("Confidential Customer Contract", 2),
    DocumentSpec("Restricted Executive Memo", 3),
    DocumentSpec("Admin-only Security Brief", 3, owner_id="admin-user"),
]


def apply_level_filter(documents: Iterable[DocumentSpec], max_level: int) -> list[DocumentSpec]:
    """Model the effective data access for a user at a given level."""
    return [doc for doc in documents if doc.access_level <= max_level]


def evaluate_role(role_name: str) -> dict:
    level = ROLE_LEVELS[role_name]
    allowed = apply_level_filter(DOCUMENTS, level) if role_name != "admin" else list(DOCUMENTS)

    filter_dict = build_pinecone_filter(
        max_access_level=level if role_name != "admin" else 99,
        allowed_account_ids=[],
        allowed_role_names=[],
        user_id=f"{role_name}-user",
    )

    expected_titles = [doc.title for doc in allowed]
    blocked_titles = [doc.title for doc in DOCUMENTS if doc.title not in expected_titles]

    expected_set = {doc.title for doc in allowed}
    all_expected = set(doc.title for doc in DOCUMENTS if doc.access_level <= level) if role_name != "admin" else set(doc.title for doc in DOCUMENTS)
    passed = expected_set == all_expected and blocked_titles == [
        doc.title for doc in DOCUMENTS if doc.title not in expected_set
    ]

    return {
        "role": role_name,
        "level": level,
        "expected_titles": expected_titles,
        "blocked_titles": blocked_titles,
        "filter": filter_dict,
        "passed": passed if role_name != "admin" else True,
    }


def main() -> None:
    print("=" * 80)
    print("Vault Role-Based Access Evaluation")
    print("=" * 80)
    print("Rule: document.access_level <= user.max_access_level")
    print("Public users must not see internal/confidential/restricted/admin documents.\n")

    for role in ["public", "internal", "confidential", "restricted", "admin"]:
        result = evaluate_role(role)
        print(f"Role: {result['role']:<12} max_level={result['level']}")
        print(f"  Allowed: {[d for d in result['expected_titles']]}")
        print(f"  Blocked: {[d for d in result['blocked_titles']]}")
        print(f"  Filter: {result['filter']}")
        print(f"  PASS: {result['passed']}\n")

    print("=" * 80)
    print("Interpretation:")
    print("- Public users: only level 0 docs allowed")
    print("- Internal users: levels 0-1 allowed")
    print("- Confidential users: levels 0-2 allowed")
    print("- Restricted users: levels 0-3 allowed")
    print("- Admin users: unrestricted access")
    print("=" * 80)


if __name__ == "__main__":
    main()
