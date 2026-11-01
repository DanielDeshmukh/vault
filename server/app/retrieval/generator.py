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

# Rule-7 focus detection: countries/entities the corpus does not speak for.
_FOCUS_COUNTRIES = frozenset(
    {
        "australia", "brazil", "canada", "china", "dubai", "france", "germany",
        "india", "ireland", "italy", "japan", "mexico", "netherlands", "nigeria",
        "singapore", "south africa", "spain", "sweden", "switzerland",
        "united arab emirates", "united kingdom", "united states", "usa",
        "european union",
    }
)
_STOP_CAPS = frozenset(
    {
        "the", "what", "how", "why", "when", "where", "who", "which", "is",
        "are", "do", "does", "did", "can", "could", "may", "might", "should",
        "would", "will", "shall", "must", "please", "our", "we", "you",
        "your", "this", "that", "these", "those", "there", "here", "answer",
        "question", "according", "per",
    }
)


class CitationGenerator:

    SYSTEM_PROMPT = """You are Vault, an enterprise knowledge assistant. Answer using ONLY the provided sources.

Rules:
1. Cite every claim with [document_id]. Multiple claims from same source = multiple citations.
2. Synthesize across sources. Never say sources lack info when sources are provided.
3. Be concise but thorough. Cover all key points from each relevant source.
4. Never fabricate. If sources conflict, note it and cite each side.
5. Use precise HR, legal, and policy terminology from the sources. For example, when a user asks about "time off after a kid is born," use terms like "parental leave," "maternity leave," "paternity leave," "bonding leave," and "FMLA" as they appear in the sources. When a user asks about "working from home," use terms like "remote work," "telework," "telecommute," and "flexible work arrangements" as they appear in the sources.
6. Map colloquial user questions to the formal policy terminology used in the documents.
7. EXCEPTION to rule 2: if the question names a country, city, or entity that appears in NO source above, do not answer about it as if the sources covered it. State briefly what the provided sources DO cover, then invite a question on that scope.

Format: Direct answer first, then supporting details with citations."""

    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def _focus_terms(self, query: str) -> list[str]:
        """Country/entity terms the question is about (rule-7 candidates)."""
        found: dict[str, str] = {}
        low = query.lower()
        for country in _FOCUS_COUNTRIES:
            if re.search(rf"(?<!\w){re.escape(country)}(?!\w)", low):
                found[country.lower()] = country
        for quoted in re.findall(r'"([^"]{2,60})"', query):
            found[quoted.lower()] = quoted
        for m in re.finditer(r"[A-Za-z][A-Za-z0-9&.'-]*", query):
            word = m.group(0)
            before = query[: m.start()].rstrip()
            sentence_start = not before or before[-1] in ".?!"
            if (
                not sentence_start
                and word[0].isupper()
                and len(word) >= 3
                and word.lower() not in _STOP_CAPS
            ):
                found.setdefault(word.lower(), word)
        return list(found.values())

    def _build_messages(self, query: str, results: list[SearchResult], conversation_context: str | None = None) -> list[dict]:
        context = self._build_context(results)
        context_block = (
            "CONVERSATION CONTEXT (use this only for resolving references such as "
            f'"each" or "that policy"; it is not source evidence):\n{conversation_context}\n\n'
            if conversation_context
            else ""
        )
        guard = ""
        focus = self._focus_terms(query)
        if focus and context:
            uncovered = [t for t in focus if t.lower() not in context.lower()]
            if uncovered:
                listed = ", ".join(uncovered)
                guard = (
                    f"\n\nUNMENTIONED FOCUS: {listed} -- none of the sources above "
                    f"mention it. Per system rule 7, do NOT answer about {listed} as "
                    "if the sources covered it. State briefly what the provided "
                    "sources DO cover, then invite a question on that scope."
                )
        user_message = f"""Sources ({len(results)}):
{context}

{context_block}Question: {query}{guard}

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
                        # The preview modal hydrates text_md by chunk id from
                        # Postgres, so every citation carries its handle.
                        "chunk_id": result.id,
                        "title": result.metadata.get("source_title", "Untitled"),
                        "source": result.metadata.get("department", "unknown"),
                        "score": result.score
                    })
                    break
        return citations
