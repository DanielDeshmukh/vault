"""API-based evaluator that queries the live Vault API.

Does NOT import Pinecone, Cohere, or any internal app modules — it treats the
live deployment as a black box, sending queries via HTTP and evaluating the
responses. This means running the eval does not exhaust production Pinecone
egress beyond normal query traffic.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from eval.golden_set_gitlab import GoldenQuestion, QuestionCategory, get_golden_set


# Demo credentials — each role has a unique password
DEMO_CREDENTIALS = {
    "admin": ("levi.ackerman@vaultdemo.com", "HumblePie23!"),
    "intern": ("connie.springer@vaultdemo.com", "RoundTabl3!"),
    "employee": ("armin.arlert@vaultdemo.com", "CunningPl4n!"),
    "engineer": ("eren.yeager@vaultdemo.com", "FoundingR3x!"),
    "manager": ("mikasa.ackerman@vaultdemo.com", "ScarletP4th!"),
    "hr": ("sasha.blouse@vaultdemo.com", "Pot4toLover!"),
    "legal": ("hange.zoe@vaultdemo.com", "Explos1veMind!"),
    "finance": ("jean.kirstein@vaultdemo.com", "Command3r!"),
}


@dataclass
class QueryResult:
    """Result of a single query evaluation."""
    question_id: str
    question: str
    category: str
    role: str
    answer: str
    citations: list[dict]
    latency_ms: float
    timestamp: str
    success: bool
    error: Optional[str] = None
    relevance_score: float = 0.0
    has_citations: bool = False
    citation_count: int = 0
    refused: bool = False


REFUSAL_PHRASES = [
    "couldn't find anything relevant",
    "no relevant documents",
    "no information found",
    "i don't have access",
    "i cannot",
    "not able to",
]


def _did_refuse(answer: str) -> bool:
    """Check if the answer is a refusal/no-answer response."""
    lower = answer.lower()
    return any(phrase in lower for phrase in REFUSAL_PHRASES)


def _calculate_relevance(answer: str, expected_keywords: list[str]) -> float:
    """Calculate relevance based on expected keyword coverage.

    Returns 0.0–1.0: fraction of expected keywords found in the answer.
    """
    if not expected_keywords:
        return 1.0  # No keywords to check
    if not answer or len(answer.strip()) < 10:
        return 0.0
    lower = answer.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in lower)
    return matches / len(expected_keywords)


class APIEvaluator:
    """Evaluates the Vault system by querying the live API."""

    def __init__(self, base_url: str = "https://vault-rbac-rag.vercel.app"):
        self.base_url = base_url.rstrip("/")
        self.tokens: dict[str, str] = {}

    async def login_all_roles(self) -> None:
        """Login as all demo roles and cache tokens."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []
            for role, (email, password) in DEMO_CREDENTIALS.items():
                tasks.append(self._login(client, role, email, password))
            results = await asyncio.gather(*tasks)
            for role, token in results:
                if token:
                    self.tokens[role] = token

    async def _login(
        self, client: httpx.AsyncClient, role: str, email: str, password: str
    ) -> tuple[str, Optional[str]]:
        try:
            resp = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password},
            )
            if resp.status_code == 200:
                return (role, resp.json()["access_token"])
        except Exception as e:
            print(f"  ⚠ Failed to login as {role}: {e}")
        return (role, None)

    async def query(
        self, client: httpx.AsyncClient, token: str, question: str
    ) -> tuple[str, list[dict], float]:
        """Query the API and return (answer, citations, latency_ms)."""
        start = time.monotonic()
        resp = await client.post(
            f"{self.base_url}/api/query",
            json={"question": question},
            headers={"Authorization": f"Bearer {token}"},
        )
        latency_ms = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            citations = data.get("citations", [])
            return (answer, citations, latency_ms)
        else:
            return ("", [], latency_ms)

    async def evaluate_question(
        self, client: httpx.AsyncClient, question: GoldenQuestion, role: str
    ) -> QueryResult:
        """Evaluate a single question for a single role."""
        token = self.tokens.get(role)
        if not token:
            return QueryResult(
                question_id=question.id,
                question=question.question,
                category=question.category.value,
                role=role,
                answer="",
                citations=[],
                latency_ms=0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error=f"No token for role {role}",
            )

        try:
            answer, citations, latency_ms = await self.query(
                client, token, question.question
            )

            refused = _did_refuse(answer)
            relevance = _calculate_relevance(answer, question.expected_keywords)

            return QueryResult(
                question_id=question.id,
                question=question.question,
                category=question.category.value,
                role=role,
                answer=answer,
                citations=citations,
                latency_ms=latency_ms,
                timestamp=datetime.now().isoformat(),
                success=True,
                relevance_score=relevance,
                has_citations=len(citations) > 0,
                citation_count=len(citations),
                refused=refused,
            )
        except Exception as e:
            return QueryResult(
                question_id=question.id,
                question=question.question,
                category=question.category.value,
                role=role,
                answer="",
                citations=[],
                latency_ms=0,
                timestamp=datetime.now().isoformat(),
                success=False,
                error=str(e),
            )

    async def run_evaluation(
        self,
        roles: Optional[list[str]] = None,
        questions: Optional[list[GoldenQuestion]] = None,
        categories: Optional[list[QuestionCategory]] = None,
        max_concurrent: int = 3,
    ) -> list[QueryResult]:
        """Run evaluation across roles and questions.

        Args:
            roles: Roles to evaluate (defaults to all demo roles).
            questions: Specific questions to evaluate. If None, uses full golden set.
            categories: Categories to filter by (only used if questions is None).
            max_concurrent: Max concurrent API calls.
        """
        if roles is None:
            roles = list(DEMO_CREDENTIALS.keys())
        if questions is None:
            questions = get_golden_set()
        if categories:
            questions = [q for q in questions if q.category in categories]

        total = len(roles) * len(questions)
        counter = {"done": 0}
        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[QueryResult] = []

        async def eval_one(q: GoldenQuestion, role: str) -> QueryResult:
            async with semaphore:
                result = await self.evaluate_question(None, q, role)  # type: ignore
                counter["done"] += 1
                if counter["done"] % 10 == 0 or counter["done"] == total:
                    print(f"  Progress: {counter['done']}/{total} queries completed", flush=True)
                return result

        # Use a single shared client for all queries
        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = []
            for role in roles:
                for q in questions:
                    async def wrapped(q=q, role=role):
                        async with semaphore:
                            counter["done"] += 1
                            result = await self.evaluate_question(client, q, role)
                            if counter["done"] % 10 == 0 or counter["done"] == total:
                                print(f"  Progress: {counter['done']}/{total} queries completed", flush=True)
                            return result
                    tasks.append(wrapped())
            results = await asyncio.gather(*tasks)

        return list(results)


def print_evaluation_summary(results: list[QueryResult]) -> dict:
    """Print and return aggregated evaluation summary."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    errors = sum(1 for r in results if not r.success)
    refused = sum(1 for r in results if r.refused)
    with_citations = sum(1 for r in results if r.has_citations)
    avg_latency = (
        sum(r.latency_ms for r in results if r.success) / successful
        if successful
        else 0
    )
    avg_relevance = (
        sum(r.relevance_score for r in results if r.success) / successful
        if successful
        else 0
    )

    # Per-role breakdown
    by_role: dict[str, list[QueryResult]] = {}
    for r in results:
        by_role.setdefault(r.role, []).append(r)

    # Per-category breakdown
    by_category: dict[str, list[QueryResult]] = {}
    for r in results:
        by_category.setdefault(r.category, []).append(r)

    summary = {
        "total_queries": total,
        "successful": successful,
        "errors": errors,
        "refused": refused,
        "with_citations": with_citations,
        "avg_latency_ms": avg_latency,
        "avg_relevance": avg_relevance,
        "by_role": {},
        "by_category": {},
    }

    for role, role_results in by_role.items():
        role_success = sum(1 for r in role_results if r.success)
        role_refused = sum(1 for r in role_results if r.refused)
        role_avg_rel = (
            sum(r.relevance_score for r in role_results if r.success)
            / role_success
            if role_success
            else 0
        )
        role_avg_lat = (
            sum(r.latency_ms for r in role_results if r.success)
            / role_success
            if role_success
            else 0
        )
        summary["by_role"][role] = {
            "total": len(role_results),
            "successful": role_success,
            "refused": role_refused,
            "avg_relevance": role_avg_rel,
            "avg_latency_ms": role_avg_lat,
        }

    for cat, cat_results in by_category.items():
        cat_success = sum(1 for r in cat_results if r.success)
        cat_avg_rel = (
            sum(r.relevance_score for r in cat_results if r.success)
            / cat_success
            if cat_success
            else 0
        )
        summary["by_category"][cat] = {
            "total": len(cat_results),
            "successful": cat_success,
            "avg_relevance": cat_avg_rel,
        }

    return summary
