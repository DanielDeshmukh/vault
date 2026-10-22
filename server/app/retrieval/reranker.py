import asyncio

import cohere

from app.config import settings
from app.retrieval.search import SearchResult


class CohereReranker:
    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_MODEL
        # Set by rerank_safe: True when Cohere failed and score order was used.
        self.used_fallback = False

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        if not results:
            return []

        documents = [r.content[:1500] for r in results]

        response = await asyncio.to_thread(
            self.client.rerank,
            query=query,
            documents=documents,
            top_n=min(top_k, len(results)),
            model=self.model,
        )

        reranked = []
        for result in response.results:
            original_index = result.index
            original = results[original_index]
            # The relevance score IS the ranking signal, so it replaces the
            # vector score on the result: the no-answer threshold (plan
            # decision locked at CP3) compares the top result's score, and a
            # stale cosine similarity there would gate on the wrong scale.
            original.score = float(getattr(result, "relevance_score", 0.0) or 0.0)
            reranked.append(original)

        return reranked

    async def rerank_safe(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        try:
            reranked = await self.rerank(query, results, top_k)
        except Exception:
            self.used_fallback = True
            return results[:top_k]
        self.used_fallback = False
        return reranked
