import asyncio
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from eval.golden_set import GoldenQuestion, QuestionCategory, get_golden_set
from eval.metrics import (
    RetrievalMetrics,
    GenerationMetrics,
    SecurityMetrics,
    EvaluationResult,
    calculate_precision_at_5,
    calculate_recall_at_k,
    calculate_mrr,
    calculate_ndcg,
    calculate_faithfulness,
    calculate_relevance,
)
from app.retrieval.search import HybridSearch
from app.retrieval.generator import CitationGenerator
from app.db.models import User
from app.db.sessions import async_session


@dataclass
class EvalConfig:
    """Evaluation configuration."""
    top_k: int = 10
    use_reranker: bool = True
    max_concurrent: int = 5


class Evaluator:
    """Automated evaluation pipeline."""
    
    def __init__(self, config: Optional[EvalConfig] = None):
        self.config = config or EvalConfig()
        self.search = HybridSearch()
        self.generator = CitationGenerator()
    
    async def run_full_evaluation(
        self,
        user: User,
        golden_set: Optional[list[GoldenQuestion]] = None
    ) -> dict:
        """
        Run full evaluation on the golden set.
        
        Args:
            user: User to run evaluation as
            golden_set: Optional custom golden set (defaults to standard set)
            
        Returns:
            Complete evaluation results
        """
        if golden_set is None:
            golden_set = get_golden_set()
        
        results = []
        
        # Run evaluations concurrently (with limit)
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def eval_with_semaphore(q: GoldenQuestion):
            async with semaphore:
                return await self.evaluate_question(user, q)
        
        tasks = [eval_with_semaphore(q) for q in golden_set]
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        return self._aggregate_results(results)
    
    async def evaluate_question(
        self,
        user: User,
        question: GoldenQuestion
    ) -> EvaluationResult:
        """
        Evaluate a single question.
        
        Returns:
            EvaluationResult with all metrics
        """
        start_time = datetime.utcnow()
        
        try:
            # Execute search
            search_results = await self.search.search(
                query=question.question,
                user=user,
                top_k=self.config.top_k,
                use_reranker=self.config.use_reranker
            )
            
            # Extract sources from search results
            retrieved_sources = [
                r.metadata.get("source", "unknown") for r in search_results
            ]
            
            # Generate answer
            if search_results:
                generated = await self.generator.generate(
                    query=question.question,
                    results=search_results
                )
                answer = generated.answer
                citations = generated.citations
            else:
                answer = "No relevant documents found."
                citations = []
            
            # Check if model refused (for permission boundary questions)
            did_refuse = self._check_refusal(answer)
            
            # Calculate metrics
            retrieval_metrics = self._calculate_retrieval_metrics(
                retrieved_sources,
                question.expected_sources or []
            )
            
            generation_metrics = self._calculate_generation_metrics(
                answer,
                question.question,
                citations,
                question.expected_sources or []
            )
            
            security_metrics = self._calculate_security_metrics(
                question.should_refuse,
                did_refuse
            )
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return EvaluationResult(
                question_id=question.id,
                question=question.question,
                category=question.category.value,
                answer=answer,
                citations=citations,
                expected_sources=question.expected_sources or [],
                retrieved_sources=retrieved_sources,
                should_refuse=question.should_refuse,
                did_refuse=did_refuse,
                retrieval_metrics=retrieval_metrics,
                generation_metrics=generation_metrics,
                security_metrics=security_metrics,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return EvaluationResult(
                question_id=question.id,
                question=question.question,
                category=question.category.value,
                answer="",
                citations=[],
                expected_sources=question.expected_sources or [],
                retrieved_sources=[],
                should_refuse=question.should_refuse,
                did_refuse=False,
                retrieval_metrics=RetrievalMetrics(),
                generation_metrics=GenerationMetrics(),
                security_metrics=SecurityMetrics(),
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def _check_refusal(self, answer: str) -> bool:
        """Check if the answer is a refusal."""
        refusal_patterns = [
            "i don't have access",
            "i cannot",
            "i'm not able to",
            "i don't have information",
            "no information found",
            "i cannot provide",
            "i'm sorry, but i",
            "i don't have permission",
            "unauthorized",
            "access denied",
        ]
        
        answer_lower = answer.lower()
        return any(pattern in answer_lower for pattern in refusal_patterns)
    
    def _calculate_retrieval_metrics(
        self,
        retrieved: list[str],
        relevant: list[str]
    ) -> RetrievalMetrics:
        """Calculate retrieval metrics."""
        return RetrievalMetrics(
            precision_at_5=calculate_precision_at_5(retrieved, relevant),
            recall_at_k=calculate_recall_at_k(retrieved, relevant, self.config.top_k),
            mrr=calculate_mrr(retrieved, relevant),
            ndcg=calculate_ndcg(retrieved, relevant, self.config.top_k),
        )
    
    def _calculate_generation_metrics(
        self,
        answer: str,
        question: str,
        citations: list[dict],
        expected_sources: list[str]
    ) -> GenerationMetrics:
        """Calculate generation metrics."""
        return GenerationMetrics(
            faithfulness=calculate_faithfulness(answer, [c.get("content", "") for c in citations]),
            relevance=calculate_relevance(answer, question),
            citation_accuracy=self._calculate_citation_accuracy(citations, expected_sources),
            completeness=self._calculate_completeness(answer, expected_sources),
        )
    
    def _calculate_citation_accuracy(
        self,
        citations: list[dict],
        expected_sources: list[str]
    ) -> float:
        """Calculate citation accuracy."""
        if not expected_sources:
            return 1.0
        
        if not citations:
            return 0.0
        
        cited_sources = [c.get("source", "") for c in citations]
        correct = sum(1 for s in cited_sources if s in expected_sources)
        
        return correct / len(cited_sources) if cited_sources else 0.0
    
    def _calculate_completeness(
        self,
        answer: str,
        expected_sources: list[str]
    ) -> float:
        """Calculate answer completeness."""
        if not expected_sources:
            return 1.0
        
        # Simple heuristic: check if answer mentions expected concepts
        mentioned = sum(1 for s in expected_sources if s.lower() in answer.lower())
        
        return mentioned / len(expected_sources) if expected_sources else 0.5
    
    def _calculate_security_metrics(
        self,
        should_refuse: bool,
        did_refuse: bool
    ) -> SecurityMetrics:
        """Calculate security metrics for a single question."""
        metrics = SecurityMetrics()
        
        if should_refuse:
            metrics.total_refusals_expected = 1
            if did_refuse:
                metrics.total_refusals_correct = 1
                metrics.permission_boundary_accuracy = 1.0
            else:
                metrics.permission_boundary_accuracy = 0.0
        else:
            metrics.permission_boundary_accuracy = 1.0  # Correct to answer
        
        return metrics
    
    def _aggregate_results(self, results: list[EvaluationResult]) -> dict:
        """Aggregate evaluation results into summary."""
        if not results:
            return {"error": "No results"}
        
        # Count successes and errors
        successes = [r for r in results if r.error is None]
        errors = [r for r in results if r.error is not None]
        
        # Aggregate retrieval metrics
        avg_precision = sum(r.retrieval_metrics.precision_at_5 for r in successes) / len(successes) if successes else 0
        avg_recall = sum(r.retrieval_metrics.recall_at_k for r in successes) / len(successes) if successes else 0
        avg_mrr = sum(r.retrieval_metrics.mrr for r in successes) / len(successes) if successes else 0
        
        # Aggregate generation metrics
        avg_faithfulness = sum(r.generation_metrics.faithfulness for r in successes) / len(successes) if successes else 0
        avg_relevance = sum(r.generation_metrics.relevance for r in successes) / len(successes) if successes else 0
        avg_citation_accuracy = sum(r.generation_metrics.citation_accuracy for r in successes) / len(successes) if successes else 0
        
        # Security metrics
        total_leaks = sum(r.security_metrics.total_leaks for r in successes)
        total_refusals_correct = sum(r.security_metrics.total_refusals_correct for r in successes)
        total_refusals_expected = sum(r.security_metrics.total_refusals_expected for r in successes)
        
        # Latency
        avg_latency = sum(r.latency_ms for r in results) / len(results)
        
        # By category
        by_category = {}
        for cat in QuestionCategory:
            cat_results = [r for r in results if r.category == cat.value]
            if cat_results:
                by_category[cat.value] = {
                    "count": len(cat_results),
                    "avg_relevance": sum(r.generation_metrics.relevance for r in cat_results) / len(cat_results),
                    "avg_faithfulness": sum(r.generation_metrics.faithfulness for r in cat_results) / len(cat_results),
                }
        
        return {
            "summary": {
                "total_questions": len(results),
                "successful": len(successes),
                "errors": len(errors),
                "avg_latency_ms": avg_latency,
            },
            "retrieval": {
                "precision_at_5": avg_precision,
                "recall_at_k": avg_recall,
                "mrr": avg_mrr,
            },
            "generation": {
                "faithfulness": avg_faithfulness,
                "relevance": avg_relevance,
                "citation_accuracy": avg_citation_accuracy,
            },
            "security": {
                "unauthorized_leakage_rate": total_leaks / len(successes) if successes else 0,
                "permission_boundary_accuracy": total_refusals_correct / total_refusals_expected if total_refusals_expected > 0 else 1.0,
                "total_leaks": total_leaks,
                "total_refusals_correct": total_refusals_correct,
                "total_refusals_expected": total_refusals_expected,
            },
            "by_category": by_category,
            "details": [r.to_dict() for r in results],
        }
