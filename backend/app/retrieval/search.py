from typing import Optional
from dataclasses import dataclass

from app.db.pinecone import pinecone_client
from app.db.sessions import async_session
from app.auth.permissions import get_user_max_access_level, get_user_allowed_account_ids
from app.db.models import User
from app.retrieval.permission_filter import PermissionFilter


@dataclass
class SearchResult:
    """A single search result."""
    id: str
    content: str
    score: float
    metadata: dict


class HybridSearch:
    """
    Hybrid search combining vector similarity and keyword matching.
    
    Uses Pinecone for vector search and applies permission filters
    at the query level (pre-retrieval filtering).
    """
    
    def __init__(self):
        self.pinecone = pinecone_client
    
    async def search(
        self,
        query: str,
        user: User,
        top_k: int = 10,
        use_reranker: bool = True
    ) -> list[SearchResult]:
        """
        Execute a hybrid search with permission filtering.
        
        Args:
            query: The search query
            user: The authenticated user
            top_k: Number of results to return
            use_reranker: Whether to apply Cohere reranking
            
        Returns:
            List of SearchResult objects
        """
        # Get permission filter
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(user)
        
        # Generate query embedding
        embedding = await self._get_embedding(query)
        
        # Execute vector search with permission filter
        results = await self.pinecone.query_vectors(
            vector=embedding,
            top_k=top_k * 2,  # Get more results for reranking
            filter=filter_dict,
            include_metadata=True
        )
        
        # Convert to SearchResult objects
        search_results = []
        for match in results:
            search_results.append(SearchResult(
                id=match.get("id", ""),
                content=match.get("metadata", {}).get("content", ""),
                score=match.get("score", 0.0),
                metadata=match.get("metadata", {})
            ))
        
        # Apply reranking if enabled
        if use_reranker and len(search_results) > 0:
            from app.retrieval.reranker import CohereReranker
            reranker = CohereReranker()
            search_results = await reranker.rerank(query, search_results, top_k)
        
        return search_results[:top_k]
    
    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text using Groq."""
        from groq import Groq
        from app.config import settings
        
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text
        )
        
        return response.data[0].embedding
