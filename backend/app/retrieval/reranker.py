import cohere
from typing import Optional

from app.config import settings
from app.retrieval.search import SearchResult


class CohereReranker:
    """Rerank search results using Cohere's cross-encoder."""
    
    def __init__(self):
        self.client = cohere.Client(api_key=settings.COHERE_API_KEY)
        self.model = settings.COHERE_MODEL
    
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        """
        Rerank search results using Cohere.
        
        Args:
            query: The original query
            results: List of search results to rerank
            top_k: Number of results to return after reranking
            
        Returns:
            Reranked list of SearchResult objects
        """
        if not results:
            return []
        
        # Extract documents for reranking
        documents = [r.content for r in results]
        
        # Call Cohere rerank API
        response = self.client.rerank(
            query=query,
            documents=documents,
            top_n=min(top_k, len(results)),
            model=self.model,
            return_documents=False
        )
        
        # Map reranked results back to SearchResult objects
        reranked = []
        for result in response.results:
            original_index = result.index
            reranked.append(results[original_index])
        
        return reranked
