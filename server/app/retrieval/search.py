from typing import Optional
from dataclasses import dataclass, field

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


# Query expansion: synonyms and acronym expansions for common HR/enterprise terms
QUERY_EXPANSIONS = {
    "fmla": "family medical leave act",
    "nist": "national institute of standards and technology cybersecurity framework",
    "byod": "bring your own device personal equipment",
    "eap": "employee assistance program counseling support",
    "eeo": "equal employment opportunity discrimination",
    "hr": "human resources personnel",
    "it": "information technology computer",
    "ppe": "personal protective equipment safety",
    "osha": "occupational safety health administration",
    "ada": "american disabilities act reasonable accommodation",
}


def expand_query(query: str) -> list[str]:
    """
    Generate expanded query variants to cast a wider retrieval net.
    Returns the original query plus up to 2 expanded variants.
    """
    q_lower = query.lower()
    expansions = []

    # Check for acronym matches
    for acronym, expansion in QUERY_EXPANSIONS.items():
        if acronym in q_lower:
            expansions.append(query + " " + expansion)
            break

    # Topic-focused expansions based on keyword detection
    topic_hints = {
        "leave": ["time off absence absence"],
        "vacation": ["paid time off annual leave pto"],
        "sick": ["illness medical absence health"],
        "bereavement": ["death family funeral grief"],
        "military": ["active duty reserve national guard uniformed"],
        "parental": ["maternity paternity birth adoption family"],
        "donated": ["shared leave voluntary program transfer"],
        "harassment": ["sexual discrimination hostile unwelcome conduct"],
        "grievance": ["complaint dispute resolution process"],
        "dress": ["appearance clothing professional attire uniform"],
        "overtime": ["extra hours beyond forty compensatory"],
        "pay": ["compensation salary wage direct deposit"],
        "holiday": ["observed paid federal calendar"],
        "safety": ["injury prevention workplace hazard"],
        "cybersecurity": ["password computer internet network security breach"],
        "weapon": ["firearms gun prohibited campus"],
        "evacuation": ["fire emergency drill assembly exit"],
        "email": ["internet acceptable use computer technology"],
        "social media": ["facebook twitter instagram posting online"],
        "confidential": ["private data protected information secrecy"],
        "whistleblower": ["reporting retaliation protection good faith"],
        "orientation": ["new employee onboarding training induction"],
        "probationary": ["new hire trial period evaluation"],
        "resignation": ["quit voluntary departure notice"],
        "telework": ["telecommute remote work from home"],
        "retirement": ["pension 401k plan contributions"],
        "tuition": ["education reimbursement courses learning"],
        "alcohol": ["intoxication drinking substance impairment"],
        "marijuana": ["cannabis drug substance legalized"],
        "positive": ["drug test result substance testing"],
        "inclement weather": ["storm closure delay emergency"],
    }

    for keyword, hints in topic_hints.items():
        if keyword in q_lower:
            expansions.append(query + " " + hints)
            break

    return [query] + expansions[:2]


class HybridSearch:
    """
    Hybrid search combining vector similarity and keyword matching.

    Uses Pinecone for vector search with query expansion and applies
    permission filters at the query level (pre-retrieval filtering).
    """

    def __init__(self):
        self.pinecone = pinecone_client

    async def search(
        self,
        query: str,
        user: User,
        top_k: int = 8,
        use_reranker: bool = True
    ) -> list[SearchResult]:
        """
        Execute a hybrid search with permission filtering.

        Runs multiple expanded queries against Pinecone, merges and
        deduplicates results, then reranks the combined pool.
        """
        # Get permission filter
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(user)

        # Generate expanded queries
        query_variants = expand_query(query)

        # Run all queries and collect candidates
        all_candidates: dict[str, SearchResult] = {}
        for variant in query_variants:
            embedding = await self._get_embedding(variant)
            results = await self.pinecone.query_vectors(
                vector=embedding,
                top_k=top_k * 3,
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

        # Sort by score descending, keep top candidates for reranking
        search_results.sort(key=lambda r: r.score, reverse=True)
        search_results = search_results[:top_k * 3]

        # Apply reranking if enabled
        if use_reranker and len(search_results) > 0:
            from app.retrieval.reranker import CohereReranker
            reranker = CohereReranker()
            search_results = await reranker.rerank_safe(query, search_results, top_k)

        return search_results[:top_k]

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text using Cohere."""
        import cohere
        from app.config import settings

        client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

        response = client.embed(
            texts=[text],
            model=settings.COHERE_EMBED_MODEL,
            input_type="search_query",
        )

        # Cohere v2 returns embeddings.float as a list of lists
        return response.embeddings.float[0]
