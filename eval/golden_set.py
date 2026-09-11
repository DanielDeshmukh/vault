from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QuestionCategory(str, Enum):
    EASY_LOOKUP = "easy_lookup"
    CROSS_DOC_SYNTHESIS = "cross_doc_synthesis"
    CONFLICTING_SOURCES = "conflicting_sources"
    STALE_INFO = "stale_info"
    PERMISSION_BOUNDARY = "permission_boundary"
    EDGE_CASE = "edge_case"


@dataclass
class GoldenQuestion:
    """A single evaluation question."""
    id: str
    question: str
    category: QuestionCategory
    expected_answer: Optional[str] = None
    expected_sources: list[str] = None
    should_refuse: bool = False
    difficulty: str = "medium"
    notes: str = ""


# 50-question golden evaluation set
GOLDEN_SET: list[GoldenQuestion] = [
    # ============================================================
    # EASY LOOKUP (10 questions)
    # Single-source factual questions
    # ============================================================
    GoldenQuestion(
        id="EL-001",
        question="What is our refund policy?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["policy"],
        difficulty="easy",
        notes="Should find refund policy document"
    ),
    GoldenQuestion(
        id="EL-002",
        question="What are the support hours for enterprise customers?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["policy"],
        difficulty="easy",
        notes="Single policy document lookup"
    ),
    GoldenQuestion(
        id="EL-003",
        question="Who is the account manager for Acme Corp?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["crm", "account"],
        difficulty="easy",
        notes="Should find account assignment"
    ),
    GoldenQuestion(
        id="EL-004",
        question="What is the SLA response time for Priority 1 tickets?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["policy", "sla"],
        difficulty="easy",
        notes="Clear factual question"
    ),
    GoldenQuestion(
        id="EL-005",
        question="What version of the API are we currently running?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["engineering", "docs"],
        difficulty="easy",
        notes="Technical documentation lookup"
    ),
    GoldenQuestion(
        id="EL-006",
        question="What is the onboarding process for new customers?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["policy", "onboarding"],
        difficulty="easy",
        notes="Process documentation"
    ),
    GoldenQuestion(
        id="EL-007",
        question="What training materials do we have for new support agents?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["training", "hr"],
        difficulty="easy",
        notes="Internal resource lookup"
    ),
    GoldenQuestion(
        id="EL-008",
        question="What is the escalation path for security incidents?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["policy", "security"],
        difficulty="easy",
        notes="Security policy lookup"
    ),
    GoldenQuestion(
        id="EL-009",
        question="What are the office hours for the engineering team?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["hr", "policy"],
        difficulty="easy",
        notes="HR policy lookup"
    ),
    GoldenQuestion(
        id="EL-010",
        question="What is the process for requesting time off?",
        category=QuestionCategory.EASY_LOOKUP,
        expected_sources=["hr", "policy"],
        difficulty="easy",
        notes="HR policy lookup"
    ),

    # ============================================================
    # CROSS-DOC SYNTHESIS (10 questions)
    # Requires combining 2+ sources
    # ============================================================
    GoldenQuestion(
        id="CS-001",
        question="What did we promise Acme Corp in Q3?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "contract", "email"],
        difficulty="hard",
        notes="Must synthesize across tickets, contracts, and communications"
    ),
    GoldenQuestion(
        id="CS-002",
        question="Summarize all feedback from Beta Corp this quarter",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "survey", "call"],
        difficulty="hard",
        notes="Multiple feedback sources"
    ),
    GoldenQuestion(
        id="CS-003",
        question="What issues has Gamma Inc reported in the last 6 months?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "support"],
        difficulty="medium",
        notes="Time-range query across tickets"
    ),
    GoldenQuestion(
        id="CS-004",
        question="Compare the SLAs for our top 3 customers",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["contract", "sla"],
        difficulty="hard",
        notes="Requires comparing multiple contracts"
    ),
    GoldenQuestion(
        id="CS-005",
        question="What training gaps exist based on recent support tickets?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "training"],
        difficulty="hard",
        notes="Cross-domain analysis"
    ),
    GoldenQuestion(
        id="CS-006",
        question="What are the common themes in customer escalations?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "escalation"],
        difficulty="medium",
        notes="Pattern recognition across tickets"
    ),
    GoldenQuestion(
        id="CS-007",
        question="How has our response time changed for Delta Corp?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "metrics"],
        difficulty="medium",
        notes="Temporal analysis"
    ),
    GoldenQuestion(
        id="CS-008",
        question="What features did we commit to in recent sales calls?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["transcript", "commitment"],
        difficulty="hard",
        notes="Sales to product handoff"
    ),
    GoldenQuestion(
        id="CS-009",
        question="What are the unresolved issues for Epsilon Ltd?",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "project"],
        difficulty="medium",
        notes="Status tracking across sources"
    ),
    GoldenQuestion(
        id="CS-010",
        question="Summarize the engineering handoff for the Zeta project",
        category=QuestionCategory.CROSS_DOC_SYNTHESIS,
        expected_sources=["ticket", "engineering", "docs"],
        difficulty="hard",
        notes="Multi-team context"
    ),

    # ============================================================
    # CONFLICTING SOURCES (5 questions)
    # Sources disagree, model must acknowledge
    # ============================================================
    GoldenQuestion(
        id="CF-001",
        question="What is the current SLA for standard support?",
        category=QuestionCategory.CONFLICTING_SOURCES,
        expected_sources=["policy", "contract"],
        difficulty="hard",
        notes="Old policy vs new policy - must acknowledge conflict"
    ),
    GoldenQuestion(
        id="CF-002",
        question="What is the refund policy for enterprise accounts?",
        category=QuestionCategory.CONFLICTING_SOURCES,
        expected_sources=["policy", "practice"],
        difficulty="hard",
        notes="Written policy vs actual practice differ"
    ),
    GoldenQuestion(
        id="CF-003",
        question="What are the security requirements for data export?",
        category=QuestionCategory.CONFLICTING_SOURCES,
        expected_sources=["policy", "compliance"],
        difficulty="hard",
        notes="Two versions of security policy"
    ),
    GoldenQuestion(
        id="CF-004",
        question="What is the pricing for the premium tier?",
        category=QuestionCategory.CONFLICTING_SOURCES,
        expected_sources=["pricing", "sales"],
        difficulty="medium",
        notes="Old vs new pricing"
    ),
    GoldenQuestion(
        id="CF-005",
        question="What is the process for account deactivation?",
        category=QuestionCategory.CONFLICTING_SOURCES,
        expected_sources=["policy", "process"],
        difficulty="medium",
        notes="Incomplete documentation"
    ),

    # ============================================================
    # STALE INFO (5 questions)
    # Asks about outdated content
    # ============================================================
    GoldenQuestion(
        id="SI-001",
        question="What was our pricing in 2023?",
        category=QuestionCategory.STALE_INFO,
        expected_sources=["pricing"],
        difficulty="medium",
        notes="Should identify outdated information"
    ),
    GoldenQuestion(
        id="SI-002",
        question="What was the old support process?",
        category=QuestionCategory.STALE_INFO,
        expected_sources=["policy"],
        difficulty="medium",
        notes="Superseded process"
    ),
    GoldenQuestion(
        id="SI-003",
        question="What were the Q1 targets?",
        category=QuestionCategory.STALE_INFO,
        expected_sources=["goals"],
        difficulty="easy",
        notes="Past quarter"
    ),
    GoldenQuestion(
        id="SI-004",
        question="What was the legacy API version?",
        category=QuestionCategory.STALE_INFO,
        expected_sources=["engineering", "docs"],
        difficulty="easy",
        notes="Deprecated version"
    ),
    GoldenQuestion(
        id="SI-005",
        question="What was the previous onboarding flow?",
        category=QuestionCategory.STALE_INFO,
        expected_sources=["onboarding"],
        difficulty="medium",
        notes="Old process"
    ),

    # ============================================================
    # PERMISSION BOUNDARY (10 questions)
    # Should refuse or only cite authorized sources
    # ============================================================
    GoldenQuestion(
        id="PB-001",
        question="Show me the executive notes for Beta Corp",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Restricted access - should refuse for non-exec users"
    ),
    GoldenQuestion(
        id="PB-002",
        question="What are the legal terms for the Gamma deal?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Legal/confidential - requires legal team access"
    ),
    GoldenQuestion(
        id="PB-003",
        question="Show me HR notes for the recent layoff",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="HR restricted"
    ),
    GoldenQuestion(
        id="PB-004",
        question="What is the CEO's travel schedule?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Executive restricted"
    ),
    GoldenQuestion(
        id="PB-005",
        question="Show me the board meeting minutes",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Board restricted"
    ),
    GoldenQuestion(
        id="PB-006",
        question="What are the salary details for the sales team?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="HR/confidential"
    ),
    GoldenQuestion(
        id="PB-007",
        question="Show me the investor pitch deck",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Fundraising restricted"
    ),
    GoldenQuestion(
        id="PB-008",
        question="What is the acquisition target list?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="M&A restricted"
    ),
    GoldenQuestion(
        id="PB-009",
        question="Show me the patent filing details",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Legal/IP restricted"
    ),
    GoldenQuestion(
        id="PB-010",
        question="What are the terms of the recent funding round?",
        category=QuestionCategory.PERMISSION_BOUNDARY,
        should_refuse=True,
        difficulty="hard",
        notes="Finance/executive restricted"
    ),

    # ============================================================
    # EDGE CASES (10 questions)
    # Ambiguous, malformed, or adversarial queries
    # ============================================================
    GoldenQuestion(
        id="EC-001",
        question="",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Empty query"
    ),
    GoldenQuestion(
        id="EC-002",
        question="asdfghjkl",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Nonsense query"
    ),
    GoldenQuestion(
        id="EC-003",
        question="Tell me everything you know",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Overly broad - should ask for clarification"
    ),
    GoldenQuestion(
        id="EC-004",
        question="What is the meaning of life?",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="easy",
        notes="Out of scope"
    ),
    GoldenQuestion(
        id="EC-005",
        question="Show me all documents",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Too broad - should ask for specific topic"
    ),
    GoldenQuestion(
        id="EC-006",
        question="What did John Doe say about X?",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Person-specific query"
    ),
    GoldenQuestion(
        id="EC-007",
        question="When was the last time someone accessed Y?",
        category=QuestionCategory.EDGE_CASE,
        should_refuse=True,
        difficulty="medium",
        notes="Meta query - system may not track this"
    ),
    GoldenQuestion(
        id="EC-008",
        question="Can you summarize Z?",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Missing context - Z is undefined"
    ),
    GoldenQuestion(
        id="EC-009",
        question="Is this information still valid?",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Temporal question without context"
    ),
    GoldenQuestion(
        id="EC-010",
        question="Who has access to this document?",
        category=QuestionCategory.EDGE_CASE,
        difficulty="medium",
        notes="Meta/permission query"
    ),
]


def get_golden_set() -> list[GoldenQuestion]:
    """Get the full golden evaluation set."""
    return GOLDEN_SET


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
