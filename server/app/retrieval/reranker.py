import cohere
from typing import Optional

from app.config import settings
from app.retrieval.search import SearchResult


class CohereReranker:
    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_MODEL

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        if not results:
            return []

        documents = [r.content[:1500] for r in results]

        response = self.client.rerank(
            query=query,
            documents=documents,
            top_n=min(top_k, len(results)),
            model=self.model,
        )

        reranked = []
        for result in response.results:
            original_index = result.index
            reranked.append(results[original_index])

        return reranked

    async def rerank_safe(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        try:
            return await self.rerank(query, results, top_k)
        except Exception:
            return results[:top_k]
