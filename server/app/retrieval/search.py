from typing import Optional
from dataclasses import dataclass

from app.db.pinecone import pinecone_client
from app.db.sessions import async_session
from app.auth.permissions import get_user_max_access_level, get_user_allowed_account_ids
from app.db.models import User
from app.retrieval.permission_filter import PermissionFilter


@dataclass
class SearchResult:
    id: str
    content: str
    score: float
    metadata: dict


QUERY_EXPANSIONS = {
    "fmla": "family medical leave act",
    "nist": "national institute of standards and technology cybersecurity framework",
    "byod": "bring your own device personal equipment",
    "eap": "employee assistance program counseling support",
    "eeo": "equal employment opportunity discrimination",
    "ppe": "personal protective equipment safety",
    "osha": "occupational safety health administration",
    "ada": "american disabilities act reasonable accommodation",
}


def expand_query(query: str) -> list[str]:
    q_lower = query.lower()
    expansions = []
    for acronym, expansion in QUERY_EXPANSIONS.items():
        if acronym in q_lower:
            expansions.append(query + " " + expansion)
            break
    return [query] + expansions[:1]


class HybridSearch:

    def __init__(self):
        self.pinecone = pinecone_client

    async def search(
        self,
        query: str,
        user: User,
        top_k: int = 8,
        use_reranker: bool = True
    ) -> list[SearchResult]:
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(user)

        query_variants = expand_query(query)

        # Batch all embeddings into one call
        all_embeddings = await self._get_embeddings(query_variants)

        # Run all Pinecone queries in parallel-ish (sequential but fast)
        all_candidates: dict[str, SearchResult] = {}
        for variant, embedding in zip(query_variants, all_embeddings):
            results = await self.pinecone.query_vectors(
                vector=embedding,
                top_k=top_k * 2,
                filter=filter_dict,
                include_metadata=True
            )
            for match in results:
                rid = match.get("id", "")
                if rid and rid not in all_candidates:
                    all_candidates[rid] = SearchResult(
                        id=rid,
                        content=match.get("metadata", {}).get("content", ""),
                        score=match.get("score", 0.0),
                        metadata=match.get("metadata", {})
                    )

        search_results = list(all_candidates.values())
        search_results.sort(key=lambda r: r.score, reverse=True)
        search_results = search_results[:top_k * 2]

        if use_reranker and len(search_results) > 0:
            from app.retrieval.reranker import CohereReranker
            reranker = CohereReranker()
            search_results = await reranker.rerank_safe(query, search_results, top_k)

        return search_results[:top_k]

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Batch embed all query variants in a single Cohere call."""
        import cohere
        from app.config import settings
        client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        response = client.embed(
            texts=texts,
            model=settings.COHERE_EMBED_MODEL,
            input_type="search_query",
        )
        return response.embeddings.float

    async def _get_embedding(self, text: str) -> list[float]:
        embeddings = await self._get_embeddings([text])
        return embeddings[0]
