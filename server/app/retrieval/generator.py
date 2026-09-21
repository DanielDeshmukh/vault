import asyncio
import cohere
import re
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from app.config import settings
from app.retrieval.search import SearchResult


@dataclass
class GeneratedAnswer:
    answer: str
    citations: list[dict]


MAX_CONTEXT_SOURCES = 6
MAX_SOURCE_CHARS = 1000


class CitationGenerator:

    SYSTEM_PROMPT = """You are Vault, an enterprise knowledge assistant. Answer using ONLY the provided sources.

Rules:
1. Cite every claim with [document_id]. Multiple claims from same source = multiple citations.
2. Synthesize across sources. Never say sources lack info when sources are provided.
3. Be concise but thorough. Cover all key points from each relevant source.
4. Never fabricate. If sources conflict, note it and cite each side.

Format: Direct answer first, then supporting details with citations."""

    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def _build_messages(self, query: str, results: list[SearchResult], conversation_context: Optional[str] = None) -> list[dict]:
        context = self._build_context(results)
        context_block = f"Previous conversation context:\n{conversation_context}\n\n" if conversation_context else ""
        user_message = f"""Sources ({len(results)}):
{context}

{context_block}Question: {query}

Answer comprehensively using ALL sources above. Cite each with [document_id]."""
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    async def generate(
        self,
        query: str,
        results: list[SearchResult],
        conversation_context: Optional[str] = None,
    ) -> GeneratedAnswer:
        messages = self._build_messages(query, results, conversation_context)
        response = await asyncio.to_thread(
            self.client.chat,
            model=settings.COHERE_CHAT_MODEL,
            messages=messages,
        )
        answer_text = response.message.content[0].text
        citations = self._extract_citations(answer_text, results)
        return GeneratedAnswer(answer=answer_text, citations=citations)

    async def generate_stream(
        self,
        query: str,
        results: list[SearchResult],
        conversation_context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        messages = self._build_messages(query, results, conversation_context)
        for event in self.client.chat_stream(
            model=settings.COHERE_CHAT_MODEL,
            messages=messages,
        ):
            if hasattr(event, "type") and event.type == "content-delta":
                try:
                    text = event.delta.message.content.text
                    if text:
                        yield text
                except (AttributeError, TypeError):
                    pass

    def _build_context(self, results: list[SearchResult]) -> str:
        context_parts = []
        for result in results[:MAX_CONTEXT_SOURCES]:
            doc_id = result.metadata.get("document_id", result.id)
            source = result.metadata.get("source", "unknown")
            title = result.metadata.get("title", "Untitled")
            content = result.content[:MAX_SOURCE_CHARS]
            context_parts.append(
                f"[{doc_id}] {title} ({source})\n{content}"
            )
        return "\n---\n".join(context_parts)

    def extract_citations(self, answer: str, results: list[SearchResult]) -> list[dict]:
        return self._extract_citations(answer, results)

    def _extract_citations(self, answer: str, results: list[SearchResult]) -> list[dict]:
        matches = re.findall(r'\[([^\]]+)\]', answer)
        citations = []
        seen = set()
        for match in matches:
            if match in seen:
                continue
            seen.add(match)
            for result in results:
                doc_id = result.metadata.get("document_id", "")
                if doc_id == match or result.id == match:
                    citations.append({
                        "document_id": doc_id or result.id,
                        "title": result.metadata.get("title", "Untitled"),
                        "source": result.metadata.get("source", "unknown"),
                        "score": result.score
                    })
                    break
        return citations
