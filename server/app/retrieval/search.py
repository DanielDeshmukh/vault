import asyncio
from dataclasses import dataclass
from typing import Optional

from app.db.pinecone import pinecone_client
from app.db.sessions import async_session
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
        query_variants = expand_query(query)

        # Run permission filter + embeddings in parallel
        filter_task = asyncio.create_task(self._get_filter(user))
        embeddings_task = asyncio.create_task(self._get_embeddings(query_variants))

        filter_dict, all_embeddings = await asyncio.gather(filter_task, embeddings_task)

        # Run all Pinecone queries in parallel
        query_tasks = [
            self.pinecone.query_vectors(
                vector=embedding,
                top_k=top_k * 2,
                filter=filter_dict,
                include_metadata=True
            )
            for embedding in all_embeddings
        ]
        all_results = await asyncio.gather(*query_tasks)

        # Deduplicate results
        all_candidates: dict[str, SearchResult] = {}
        for matches in all_results:
            for match in matches:
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

    async def _get_filter(self, user: User) -> Optional[dict]:
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            return await perm_filter.build_filter(user)

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Batch embed all query variants in a single Cohere call."""
        import cohere
        from app.config import settings
        client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
        response = await asyncio.to_thread(
            client.embed,
            texts=texts,
            model=settings.COHERE_EMBED_MODEL,
            input_type="search_query",
        )
        return response.embeddings.float

    async def _get_embedding(self, text: str) -> list[float]:
        embeddings = await self._get_embeddings([text])
        return embeddings[0]
