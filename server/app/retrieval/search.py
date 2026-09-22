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
    "quit": "resignation resign terminate resignation letter notice",
    "fired": "termination terminated terminated for cause",
    "hurt": "injury workplace injury workers compensation accident",
    "gun": "firearms weapons prohibited prohibited items",
    "home": "remote work telecommute telework flexible work arrangement",
    "time off": "leave vacation PTO personal days sick leave",
    "born": "parental leave maternity paternity birth adoption newborn",
    "kid": "parental leave maternity paternity family",
    "pregnant": "pregnancy maternity parental leave",
    "pay": "compensation salary wages paycheck",
    "raise": "promotion pay increase merit increase",
    "harassment": "sexual harassment hostile work environment bullying",
    "discrimination": "discrimination equal opportunity protected class",
    "safety": "workplace safety OSHA injury prevention hazard",
    "training": "onboarding orientation training program",
    "benefits": "health insurance dental vision 401k retirement",
    "overtime": "overtime hours time and a half",
    "break": "meal break rest break lunch period",
    "dress": "dress code professional appearance attire",
    "social media": "social media policy internet usage personal device",
    "travel": "travel policy reimbursement mileage expense",
}


def expand_query(query: str) -> list[str]:
    q_lower = query.lower()
    expansions = []
    for keyword, expansion in QUERY_EXPANSIONS.items():
        if keyword in q_lower:
            expansions.append(query + " " + expansion)
    # Generate keyword-focused variant by stripping filler words
    STOP_WORDS = {
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "them", "the", "a", "an", "is", "am", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "about", "between", "through", "during", "before", "after",
        "and", "but", "or", "not", "no", "if", "then", "else", "when",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "than", "too", "very", "just", "also",
        "now", "here", "there", "up", "out", "so", "only", "own", "same",
    }
    words = [w for w in q_lower.split() if w.isalnum() and w not in STOP_WORDS]
    if words:
        keyword_query = " ".join(words)
        expansions.append(keyword_query)
    if expansions:
        return [query] + expansions[:3]
    return [query]


class HybridSearch:

    def __init__(self):
        self.pinecone = pinecone_client

    async def search(
        self,
        query: str,
        user: User,
        top_k: int = 12,
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
