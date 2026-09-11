from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval quality."""
    precision_at_5: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0  # Mean Reciprocal Rank
    ndcg: float = 0.0  # Normalized Discounted Cumulative Gain
    
    def to_dict(self) -> dict:
        return {
            "precision_at_5": self.precision_at_5,
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "ndcg": self.ndcg,
        }


@dataclass
class GenerationMetrics:
    """Metrics for generation quality."""
    faithfulness: float = 0.0  # Is answer grounded in sources?
    relevance: float = 0.0  # Does answer address the question?
    citation_accuracy: float = 0.0  # Are citations correct?
    completeness: float = 0.0  # Does answer cover all relevant info?
    
    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "citation_accuracy": self.citation_accuracy,
            "completeness": self.completeness,
        }


@dataclass
class SecurityMetrics:
    """Metrics for security compliance."""
    unauthorized_leakage_rate: float = 0.0  # Must be 0.0
    permission_boundary_accuracy: float = 0.0  # Correct refusals
    total_queries: int = 0
    total_leaks: int = 0
    total_refusals_correct: int = 0
    total_refusals_expected: int = 0
    
    def to_dict(self) -> dict:
        return {
            "unauthorized_leakage_rate": self.unauthorized_leakage_rate,
            "permission_boundary_accuracy": self.permission_boundary_accuracy,
            "total_queries": self.total_queries,
            "total_leaks": self.total_leaks,
            "total_refusals_correct": self.total_refusals_correct,
            "total_refusals_expected": self.total_refusals_expected,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result for a single question."""
    question_id: str
    question: str
    category: str
    answer: str
    citations: list[dict]
    expected_sources: list[str]
    retrieved_sources: list[str]
    should_refuse: bool
    did_refuse: bool
    retrieval_metrics: RetrievalMetrics
    generation_metrics: GenerationMetrics
    security_metrics: SecurityMetrics
    latency_ms: float
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "category": self.category,
            "answer": self.answer,
            "citations": self.citations,
            "expected_sources": self.expected_sources,
            "retrieved_sources": self.retrieved_sources,
            "should_refuse": self.should_refuse,
            "did_refuse": self.did_refuse,
            "retrieval_metrics": self.retrieval_metrics.to_dict(),
            "generation_metrics": self.generation_metrics.to_dict(),
            "security_metrics": self.security_metrics.to_dict(),
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def calculate_precision_at_5(retrieved: list[str], relevant: list[str]) -> float:
    """Calculate Precision@5."""
    if not retrieved:
        return 0.0
    
    top_5 = retrieved[:5]
    relevant_in_top_5 = sum(1 for r in top_5 if r in relevant)
    return relevant_in_top_5 / min(5, len(retrieved))


def calculate_recall_at_k(retrieved: list[str], relevant: list[str], k: int = 10) -> float:
    """Calculate Recall@k."""
    if not relevant:
        return 1.0
    
    top_k = retrieved[:k]
    relevant_retrieved = sum(1 for r in top_k if r in relevant)
    return relevant_retrieved / len(relevant)


def calculate_mrr(retrieved: list[str], relevant: list[str]) -> float:
    """Calculate Mean Reciprocal Rank."""
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def calculate_ndcg(retrieved: list[str], relevant: list[str], k: int = 10) -> float:
    """Calculate NDCG@k."""
    def dcg(retrieved: list[str], relevant: list[str], k: int) -> float:
        score = 0.0
        for i, doc in enumerate(retrieved[:k]):
            if doc in relevant:
                score += 1.0 / (i + 1).bit_length()
        return score
    
    actual_dcg = dcg(retrieved, relevant, k)
    ideal_dcg = dcg(relevant, relevant, k)
    
    if ideal_dcg == 0:
        return 0.0
    
    return actual_dcg / ideal_dcg


def calculate_faithfulness(answer: str, sources: list[str]) -> float:
    """
    Calculate faithfulness score.
    
    Simple heuristic: check if answer contains claims not supported by sources.
    In production, use an LLM-based evaluator.
    """
    if not sources:
        return 1.0  # No claims to verify
    
    # Simple check: if answer is very short, likely faithful
    if len(answer.split()) < 20:
        return 0.9
    
    # Check if answer references sources
    source_references = sum(1 for s in ["according to", "based on", "source"] if s in answer.lower())
    
    # Base score
    score = 0.7
    
    # Boost for source references
    score += min(0.2, source_references * 0.1)
    
    return min(1.0, score)


def calculate_relevance(answer: str, question: str) -> float:
    """
    Calculate relevance score.
    
    Simple heuristic: check if answer addresses the question.
    In production, use an LLM-based evaluator.
    """
    # Check if answer is empty
    if not answer or len(answer.strip()) == 0:
        return 0.0
    
    # Check for refusal patterns
    refusal_patterns = [
        "i don't have access",
        "i cannot",
        "i'm not able to",
        "i don't have information",
        "no information found",
    ]
    
    if any(pattern in answer.lower() for pattern in refusal_patterns):
        return 0.5  # Refusal is partially relevant
    
    # Simple length-based heuristic
    if len(answer.split()) < 10:
        return 0.5
    
    return 0.8  # Default good score
