import asyncio
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import cast

import cohere
from cohere.types import (
    AssistantChatMessageV2,
    SystemChatMessageV2,
    ToolChatMessageV2,
    UserChatMessageV2,
)

from app.config import settings
from app.retrieval.search import SearchResult

# The V2 chat endpoint takes plain dicts on the wire; cast at the SDK boundary.
CohereMessage = UserChatMessageV2 | AssistantChatMessageV2 | SystemChatMessageV2 | ToolChatMessageV2


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
5. Use precise HR, legal, and policy terminology from the sources. For example, when a user asks about "time off after a kid is born," use terms like "parental leave," "maternity leave," "paternity leave," "bonding leave," and "FMLA" as they appear in the sources. When a user asks about "working from home," use terms like "remote work," "telework," "telecommute," and "flexible work arrangements" as they appear in the sources.
6. Map colloquial user questions to the formal policy terminology used in the documents.

Format: Direct answer first, then supporting details with citations."""

    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def _build_messages(self, query: str, results: list[SearchResult], conversation_context: str | None = None) -> list[dict]:
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
        conversation_context: str | None = None,
    ) -> GeneratedAnswer:
        messages = self._build_messages(query, results, conversation_context)
        response = await asyncio.to_thread(
            self.client.chat,
            model=settings.COHERE_CHAT_MODEL,
            messages=cast(list[CohereMessage], messages),
        )
        content_items = response.message.content or []
        answer_text = next(
            (item.text for item in content_items if item.type == "text"),
            "",
        )
        citations = self._extract_citations(answer_text, results)
        return GeneratedAnswer(answer=answer_text, citations=citations)

    async def generate_stream(
        self,
        query: str,
        results: list[SearchResult],
        conversation_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        messages = self._build_messages(query, results, conversation_context)
        for event in self.client.chat_stream(
            model=settings.COHERE_CHAT_MODEL,
            messages=cast(list[CohereMessage], messages),
        ):
            if hasattr(event, "type") and event.type == "content-delta":
                try:
                    delta = event.delta
                    message = delta.message if delta is not None else None
                    message_content = message.content if message is not None else None
                    text = message_content.text if message_content is not None else None
                    if text:
                        yield text
                except (AttributeError, TypeError):
                    pass

    def _build_context(self, results: list[SearchResult]) -> str:
        context_parts = []
        for result in results[:MAX_CONTEXT_SOURCES]:
            doc_id = result.metadata.get("doc_id", result.id)
            source = result.metadata.get("department", "unknown")
            title = result.metadata.get("source_title", "Untitled")
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
                doc_id = result.metadata.get("doc_id", "")
                if doc_id == match or result.id == match:
                    citations.append({
                        "document_id": doc_id or result.id,
                        "title": result.metadata.get("source_title", "Untitled"),
                        "source": result.metadata.get("department", "unknown"),
                        "score": result.score
                    })
                    break
        return citations
