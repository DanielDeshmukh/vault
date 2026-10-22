import asyncio
import hashlib
import string
from dataclasses import dataclass

from app.db.models import User
from app.db.pinecone import pinecone_client
from app.db.sessions import async_session
from app.retrieval.permission_filter import PermissionFilter

# Phase 3 (corpus rebuild plan): fetch a wide candidate set, clean it, rerank
# everything, only then cut to top_k. Never cut before the reranker.
CANDIDATE_WIDTH = 50
MIN_CANDIDATE_CHARS = 50
MIN_CANDIDATE_WORDS = 5


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


def expand_query(query: str) -> list[str]:
    q_lower = query.lower()
    expansions = []
    for keyword, expansion in QUERY_EXPANSIONS.items():
        if keyword in q_lower:
            expansions.append(query + " " + expansion)
    # Keyword-focused variant by stripping filler words. Punctuation must not
    # drop words: "policies?" -> "policies" (the old isalnum() check dropped it).
    words = []
    for w in q_lower.split():
        token = w.strip(string.punctuation)
        if token and token not in STOP_WORDS:
            words.append(token)
    if words:
        keyword_query = " ".join(words)
        if keyword_query != q_lower:
            expansions.append(keyword_query)
    if expansions:
        return [query] + expansions[:3]
    return [query]


def content_fingerprint(result: SearchResult) -> str:
    stored = result.metadata.get("content_hash")
    if isinstance(stored, str) and stored:
        return stored
    return hashlib.sha256(result.content.encode("utf-8", errors="replace")).hexdigest()


def apply_safety_net(results: list[SearchResult]) -> list[SearchResult]:
    kept = []
    for r in results:
        if len(r.content) < MIN_CANDIDATE_CHARS:
            continue
        if len(r.content.split()) < MIN_CANDIDATE_WORDS:
            continue
        kept.append(r)
    return kept


def dedupe_by_content_hash(results: list[SearchResult]) -> list[SearchResult]:
    # Input is sorted best-first, so the first occurrence of a hash wins.
    seen: set[str] = set()
    deduped = []
    for r in results:
        fp = content_fingerprint(r)
        if fp in seen:
            continue
        seen.add(fp)
        deduped.append(r)
    return deduped


class HybridSearch:

    def __init__(self):
        self.pinecone = pinecone_client
        self.last_flow: dict = {}

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

        # Wide fetch: CANDIDATE_WIDTH matches per variant, RBAC-filtered
        # server-side inside Pinecone (build_filter -> allowed_roles $in).
        query_tasks = [
            self.pinecone.query_vectors(
                vector=embedding,
                top_k=CANDIDATE_WIDTH,
                filter=filter_dict,
                include_metadata=True
            )
            for embedding in all_embeddings
        ]
        all_results = await asyncio.gather(*query_tasks)

        # Merge across variants by id, keeping the max score for each id.
        fetched = 0
        all_candidates: dict[str, SearchResult] = {}
        for matches in all_results:
            for match in matches:
                fetched += 1
                rid = match.get("id", "")
                if not rid:
                    continue
                md = match.get("metadata", {}) or {}
                candidate = SearchResult(
                    id=rid,
                    content=md.get("text", ""),
                    score=match.get("score", 0.0),
                    metadata=md,
                )
                existing = all_candidates.get(rid)
                if existing is None or candidate.score > existing.score:
                    all_candidates[rid] = candidate

        candidates = sorted(all_candidates.values(), key=lambda r: r.score, reverse=True)
        after_safety = apply_safety_net(candidates)
        deduped = dedupe_by_content_hash(after_safety)

        # Rerank the FULL cleaned set; only afterwards cut to top_k.
        reranked = False
        rerank_fallback = False
        results = deduped
        if use_reranker and deduped:
            from app.retrieval.reranker import CohereReranker
            reranker = CohereReranker()
            results = await reranker.rerank_safe(query, deduped, top_k)
            reranked = True
            rerank_fallback = reranker.used_fallback

        final = results[:top_k]
        self.last_flow = {
            "query": query,
            "variants": len(query_variants),
            "rbac_filter": filter_dict,
            "fetched": fetched,
            "merged_by_id": len(all_candidates),
            "after_safety_net": len(after_safety),
            "after_dedupe": len(deduped),
            "reranked": reranked,
            # Fallback keeps vector scores (cosine, not relevance), so the
            # caller must know which score scale the final scores are on.
            "rerank_fallback": rerank_fallback,
            "final": len(final),
        }
        return final

    async def _get_filter(self, user: User) -> dict | None:
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            return await perm_filter.build_filter(user)

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Batch embed all query variants (cached; input_type=query).

        Delegates to app.embeddings so query vectors come from the same model
        and dimensionality as the corpus vectors in Pinecone. Mixing providers
        here silently breaks retrieval. ``input_type="query"`` matches the
        ``"passage"`` mode the corpus was indexed with (NVIDIA requirement),
        and the TTL cache absorbs repeated queries against the trial tier's
        rate limit.
        """
        from app.embeddings import embed_query_batch

        return await asyncio.to_thread(embed_query_batch, texts)

    async def _get_embedding(self, text: str) -> list[float]:
        embeddings = await self._get_embeddings([text])
        return embeddings[0]
