"""Golden evaluation set based on the actual GitLab handbook corpus.

Every question targets content that exists in the ingested corpus (4,879
documents) so the evaluator can verify real answers instead of querying for
fictional companies that never appear in the vector store.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class QuestionCategory(str, Enum):
    EASY_LOOKUP = "easy_lookup"
    CROSS_DOC_SYNTHESIS = "cross_doc_synthesis"
    PERMISSION_BOUNDARY = "permission_boundary"
    EDGE_CASE = "edge_case"


@dataclass
class GoldenQuestion:
    """A single evaluation question targeting the GitLab handbook corpus."""
    id: str
    question: str
    category: QuestionCategory
    expected_keywords: list[str] = field(default_factory=list)
    """Keywords that should appear in a good answer (for relevance scoring)."""
    should_refuse: bool = False
    difficulty: str = "medium"
    notes: str = ""
    quick_select: str = ""
    """For --quick mode: 'easy', 'tricky', or 'out_of_scope'. Empty = not in quick set."""


GOLDEN_SET: list[GoldenQuestion] = [
    # ============================================================
    # EASY LOOKUP (15 questions)
    # Single-source factual questions about the GitLab handbook
    # ============================================================
    GoldenQuestion(
        id="EL-001",
        question="What is the cloud native tools strategy?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["cloud-native", "kubernetes", "platform"],
        difficulty="easy",
        notes="Working group document exists in corpus",
        quick_select="easy",
    ),
    GoldenQuestion(
        id="EL-002",
        question="How does the onboarding process work at GitLab?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["onboarding", "buddy", "first week", "orientation"],
        difficulty="easy",
        notes="Onboarding handbook section",
    ),
    GoldenQuestion(
        id="EL-003",
        question="What are the working groups at GitLab?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["working group", "wg", "team"],
        difficulty="easy",
        notes="Company working groups section",
    ),
    GoldenQuestion(
        id="EL-004",
        question="What is GitLab's remote work policy?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["remote", "distributed", "async", "time zone"],
        difficulty="easy",
        notes="GitLab is famously all-remote",
    ),
    GoldenQuestion(
        id="EL-005",
        question="What are the code of conduct rules?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["conduct", "behavior", "harassment", "respect"],
        difficulty="easy",
        notes="Code of conduct document",
    ),
    GoldenQuestion(
        id="EL-006",
        question="What is the NIST Cybersecurity Framework?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["NIST", "cybersecurity", "framework", "security"],
        difficulty="easy",
        notes="Security handbook section",
    ),
    GoldenQuestion(
        id="EL-007",
        question="What are the employee leave policies?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["leave", "vacation", "PTO", "sick", "parental"],
        difficulty="easy",
        notes="HR policies section",
    ),
    GoldenQuestion(
        id="EL-008",
        question="What benefits are offered to employees?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["benefits", "health", "insurance", "401k", "retirement"],
        difficulty="easy",
        notes="Benefits handbook",
    ),
    GoldenQuestion(
        id="EL-009",
        question="What is the drug-free workplace policy?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["drug", "substance", "workplace", "policy"],
        difficulty="easy",
        notes="HR policy document",
    ),
    GoldenQuestion(
        id="EL-010",
        question="What is the security incident response process?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["incident", "response", "security", "escalation"],
        difficulty="easy",
        notes="Security handbook",
    ),
    GoldenQuestion(
        id="EL-011",
        question="What are the laptop security configuration standards?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["laptop", "security", "encryption", "password"],
        difficulty="easy",
        notes="IT handbook section",
    ),
    GoldenQuestion(
        id="EL-012",
        question="What is the Okta Verify setup process?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["okta", "verify", "MFA", "authentication"],
        difficulty="easy",
        notes="Security systems handbook",
    ),
    GoldenQuestion(
        id="EL-013",
        question="What is GitLab's approach to automated dependency updates?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["dependency", "update", "automated", "merge request"],
        difficulty="easy",
        notes="Engineering ADR documents",
    ),
    GoldenQuestion(
        id="EL-014",
        question="What are the product principles at GitLab?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["product", "principles", "cloud-native", "open"],
        difficulty="easy",
        notes="Product handbook",
    ),
    GoldenQuestion(
        id="EL-015",
        question="What is the Duo messaging service architecture?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_keywords=["duo", "messaging", "service", "architecture"],
        difficulty="easy",
        notes="Engineering ADR documents",
    ),

    # ============================================================
    # CROSS-DOC SYNTHESIS (5 questions)
    # Requires combining info from multiple handbook sections
    # ============================================================
    GoldenQuestion(
        id="CS-001",
        question="What security frameworks and standards does GitLab follow?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_keywords=["NIST", "SOC 2", "ISO", "compliance", "security"],
        difficulty="hard",
        notes="Spans security, compliance, and policy docs",
        quick_select="tricky",
    ),
    GoldenQuestion(
        id="CS-002",
        question="How does GitLab handle employee onboarding and training?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_keywords=["onboarding", "training", "buddy", "orientation"],
        difficulty="medium",
        notes="Spans HR, onboarding, and training docs",
    ),
    GoldenQuestion(
        id="CS-003",
        question="What are the key engineering practices and standards?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_keywords=["engineering", "ADR", "architecture", "review"],
        difficulty="hard",
        notes="Spans engineering handbook and ADRs",
    ),
    GoldenQuestion(
        id="CS-004",
        question="What IT and security tools does GitLab use for employees?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_keywords=["okta", "security", "laptop", "MFA", "tools"],
        difficulty="medium",
        notes="Spans IT and security handbook sections",
    ),
    GoldenQuestion(
        id="CS-005",
        question="What is GitLab's approach to work-life balance and employee well-being?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_keywords=["leave", "benefits", "remote", "flexible", "well-being"],
        difficulty="medium",
        notes="Spans HR policies and benefits docs",
    ),

    # ============================================================
    # PERMISSION BOUNDARY (5 questions)
    # Intern should see fewer results than admin
    # ============================================================
    GoldenQuestion(
        id="PB-001",
        question="What restricted security policies exist?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        expected_keywords=["security", "policy", "restricted"],
        difficulty="medium",
        notes="Intern should see fewer restricted docs than admin",
    ),
    GoldenQuestion(
        id="PB-002",
        question="What confidential contracts are in the system?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        expected_keywords=["contract", "confidential"],
        difficulty="medium",
        notes="Intern should see fewer results than admin",
    ),
    GoldenQuestion(
        id="PB-003",
        question="Show me all internal engineering documents",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        expected_keywords=["engineering", "internal"],
        difficulty="medium",
        notes="Role-filtered retrieval should limit intern access",
    ),
    GoldenQuestion(
        id="PB-004",
        question="What are the fault tolerance standards?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        expected_keywords=["fault", "tolerance", "isolation"],
        difficulty="medium",
        notes="May be restricted to certain roles",
    ),
    GoldenQuestion(
        id="PB-005",
        question="What database security policies are in place?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        expected_keywords=["database", "security", "policy"],
        difficulty="medium",
        notes="May be restricted to certain roles",
    ),

    # ============================================================
    # EDGE CASES (5 questions)
    # Ambiguous, out-of-scope, or adversarial queries
    # ============================================================
    GoldenQuestion(
        id="EC-001",
        question="What is the stock price of Apple?",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Out of scope — not in GitLab handbook",
        quick_select="out_of_scope",
    ),
    GoldenQuestion(
        id="EC-002",
        question="Who is the CEO of Microsoft?",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Out of scope — not in GitLab handbook",
    ),
    GoldenQuestion(
        id="EC-003",
        question="asdfghjkl",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Nonsense query",
    ),
    GoldenQuestion(
        id="EC-004",
        question="Tell me everything",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Overly broad — should ask for clarification or return limited results",
    ),
    GoldenQuestion(
        id="EC-005",
        question="What happened in 1999?",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Too vague, out of scope",
    ),
]


def get_golden_set() -> list[GoldenQuestion]:
    """Get the full golden evaluation set."""
    return GOLDEN_SET


def get_quick_select() -> list[GoldenQuestion]:
    """Get the quick select set: 3 questions (1 easy, 1 tricky, 1 out-of-scope).

    Used by --quick mode to run a fast eval: ~3 queries per role.
    """
    return [q for q in GOLDEN_SET if q.quick_select]


def get_golden_set_by_category(category: QuestionCategory) -> list[GoldenQuestion]:
    """Get golden set filtered by category."""
    return [q for q in GOLDEN_SET if q.category == category]


def get_golden_set_summary() -> dict:
    """Get summary statistics of the golden set."""
    summary = {
        "total": len(GOLDEN_SET),
        "by_category": {},
        "by_difficulty": {},
        "should_refuse": sum(1 for q in GOLDEN_SET if q.should_refuse),
    }

    for cat in QuestionCategory:
        summary["by_category"][cat.value] = len(
            [q for q in GOLDEN_SET if q.category == cat]
        )

    for diff in ["easy", "medium", "hard"]:
        summary["by_difficulty"][diff] = len(
            [q for q in GOLDEN_SET if q.difficulty == diff]
        )

    return summary
