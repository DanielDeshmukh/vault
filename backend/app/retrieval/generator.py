from groq import Groq
from typing import Optional
from dataclasses import dataclass

from app.config import settings
from app.retrieval.search import SearchResult


@dataclass
class GeneratedAnswer:
    """A generated answer with citations."""
    answer: str
    citations: list[dict]


class CitationGenerator:
    """
    Generate cited answers using Groq LLM.
    
    Uses Llama 3 70B for fast, high-quality generation with
    inline citations to source documents.
    """
    
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
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
    
    async def generate(
        self,
        query: str,
        results: list[SearchResult]
    ) -> GeneratedAnswer:
        """
        Generate a cited answer from search results.
        
        Args:
            query: The user's question
            results: Search results to use as context
            
        Returns:
            GeneratedAnswer with citations
        """
        # Build context from search results
        context = self._build_context(results)
        
        # Create user message
        user_message = f"""Sources:
{context}

Question: {query}

Answer using ONLY the provided sources. Cite sources with [document_id] inline."""
        
        # Generate response
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,  # Low temp for factual accuracy
            max_tokens=2048,
            stop=["\n\n\n"]  # Stop at section breaks
        )
        
        answer_text = response.choices[0].message.content
        
        # Extract citations from the answer
        citations = self._extract_citations(answer_text, results)
        
        return GeneratedAnswer(
            answer=answer_text,
            citations=citations
        )
    
    def _build_context(self, results: list[SearchResult]) -> str:
        """Build context string from search results."""
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
    
    def _extract_citations(
        self,
        answer: str,
        results: list[SearchResult]
    ) -> list[dict]:
        """Extract citations from the answer text."""
        import re
        
        # Find all [doc_id] patterns
        citation_pattern = r'\[([^\]]+)\]'
        matches = re.findall(citation_pattern, answer)
        
        # Map citations to result metadata
        citations = []
        seen = set()
        
        for match in matches:
            if match in seen:
                continue
            seen.add(match)
            
            # Find matching result
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
