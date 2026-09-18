import cohere
from typing import Optional, AsyncGenerator
from dataclasses import dataclass

from app.config import settings
from app.retrieval.search import SearchResult


@dataclass
class GeneratedAnswer:
    answer: str
    citations: list[dict]


class CitationGenerator:

    SYSTEM_PROMPT = """You are Vault, an enterprise knowledge assistant. Answer the user's question using ONLY the provided sources.

RULES:
1. For each claim, cite the source document ID in [brackets]
2. If multiple sources support a claim, cite all relevant sources
3. If the sources don't contain enough information to say so clearly
4. If the question requires information you don't have access to, acknowledge that
5. Never fabricate citations or information not in the sources
6. Be concise and professional
7. If sources conflict, acknowledge the conflict

Format your response with clear, cited statements. Each major claim should have at least one citation."""

    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def _build_messages(self, query: str, results: list[SearchResult]) -> list[dict]:
        context = self._build_context(results)
        user_message = f"""Sources:
{context}

Question: {query}

Answer using ONLY the provided sources. Cite sources with [document_id] inline."""
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

    async def generate(
        self,
        query: str,
        results: list[SearchResult]
    ) -> GeneratedAnswer:
        messages = self._build_messages(query, results)
        response = self.client.chat(
            model=settings.COHERE_CHAT_MODEL,
            messages=messages,
        )
        answer_text = response.message.content[0].text
        citations = self._extract_citations(answer_text, results)
        return GeneratedAnswer(answer=answer_text, citations=citations)

    async def generate_stream(
        self,
        query: str,
        results: list[SearchResult]
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as they are generated. Citations extracted at end."""
        messages = self._build_messages(query, results)
        for event in self.client.chat_stream(
            model=settings.COHERE_CHAT_MODEL,
            messages=messages,
        ):
            if event.event_type == "content-delta":
                yield event.delta.message.content.text

    def _build_context(self, results: list[SearchResult]) -> str:
        context_parts = []
        for i, result in enumerate(results):
            doc_id = result.metadata.get("document_id", f"doc_{i}")
            source = result.metadata.get("source", "unknown")
            title = result.metadata.get("title", "Untitled")
            context_parts.append(
                f"[{doc_id}] Source: {source} | Title: {title}\n"
                f"Content: {result.content}\n"
            )
        return "\n---\n".join(context_parts)

    def extract_citations(self, answer: str, results: list[SearchResult]) -> list[dict]:
        import re
        citation_pattern = r'\[([^\]]+)\]'
        matches = re.findall(citation_pattern, answer)
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

    def _extract_citations(self, answer: str, results: list[SearchResult]) -> list[dict]:
        return self.extract_citations(answer, results)
