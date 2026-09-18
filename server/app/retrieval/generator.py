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

    SYSTEM_PROMPT = """You are Vault, an enterprise knowledge assistant. You answer questions by synthesizing information from the provided source documents.

CRITICAL RULES:
1. You MUST use ALL relevant sources provided — do not ignore any source that contains pertinent information.
2. For every factual claim, include an inline citation [document_id]. Multiple claims from the same source can cite it multiple times.
3. Synthesize across sources: combine information from different documents to give comprehensive answers.
4. When sources provide different perspectives or details on the same topic, present all of them.
5. NEVER say "the sources don't contain sufficient information" when sources ARE provided and contain relevant content.
6. If a source partially addresses the question, still use it and note what it covers.
7. Be thorough and detailed — aim for comprehensive coverage, not brevity.
8. Never fabricate information not present in the sources.
9. If sources conflict, acknowledge the differences and cite each side.

FORMAT:
- Start with a direct answer to the question
- Then provide detailed supporting information from each relevant source
- Use bullet points or numbered lists when covering multiple documents
- Each bullet/paragraph must have at least one citation"""

    def __init__(self):
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def _build_messages(self, query: str, results: list[SearchResult]) -> list[dict]:
        context = self._build_context(results)
        user_message = f"""You have access to {len(results)} source documents. Use ALL of them that are relevant.

SOURCES:
{context}

QUESTION: {query}

Provide a comprehensive answer using information from ALL relevant sources above. Cite each source with [document_id]. Do NOT say sources lack information — synthesize what IS available."""
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
        messages = self._build_messages(query, results)
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
        for i, result in enumerate(results):
            doc_id = result.metadata.get("document_id", f"doc_{i}")
            source = result.metadata.get("source", "unknown")
            title = result.metadata.get("title", "Untitled")
            keywords = result.metadata.get("keywords", "")
            kw_str = f" | Keywords: {keywords}" if keywords else ""
            context_parts.append(
                f"[{doc_id}] Source: {source} | Title: {title}{kw_str}\n"
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
