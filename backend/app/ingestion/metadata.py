from datetime import datetime
from typing import Optional

from app.ingestion.connectors.base import DocumentMetadata


class MetadataEnricher:
    """Enriches document metadata with additional context."""
    
    def __init__(self):
        # Department detection keywords
        self.department_keywords = {
            "support": ["ticket", "support", "help", "issue", "problem", "bug", "error"],
            "sales": ["deal", "pipeline", "lead", "prospect", "quote", "proposal"],
            "engineering": ["deploy", "code", "commit", "pull request", "sprint", "backlog"],
            "hr": ["employee", "onboarding", "hiring", "performance", "review"],
            "legal": ["contract", "compliance", "policy", "terms", "agreement"],
        }
    
    def enrich(
        self,
        base_metadata: DocumentMetadata,
        content: str
    ) -> DocumentMetadata:
        """
        Enrich metadata based on content analysis.
        
        Args:
            base_metadata: Base metadata from connector
            content: Parsed document content
            
        Returns:
            Enriched DocumentMetadata
        """
        # Detect department from content if not set
        if not base_metadata.department or base_metadata.department == "general":
            base_metadata.department = self._detect_department(content)
        
        # Detect access level from content
        if base_metadata.access_level == 0:
            base_metadata.access_level = self._detect_access_level(content)
        
        # Extract tags
        base_metadata.tags = self._extract_tags(content)
        
        return base_metadata
    
    def _detect_department(self, content: str) -> str:
        """Detect department from content keywords."""
        content_lower = content.lower()
        
        scores = {}
        for dept, keywords in self.department_keywords.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                scores[dept] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return "general"
    
    def _detect_access_level(self, content: str) -> int:
        """Detect access level from content indicators."""
        content_lower = content.lower()
        
        # Restricted keywords
        restricted_keywords = ["confidential", "restricted", "secret", "private", "internal only"]
        if any(kw in content_lower for kw in restricted_keywords):
            return 3
        
        # Confidential keywords
        confidential_keywords = ["sensitive", "proprietary", "nda", "non-disclosure"]
        if any(kw in content_lower for kw in confidential_keywords):
            return 2
        
        # Internal keywords
        internal_keywords = ["team", "department", "internal", "staff"]
        if any(kw in content_lower for kw in internal_keywords):
            return 1
        
        return 0  # Public
    
    def _extract_tags(self, content: str) -> list[str]:
        """Extract relevant tags from content."""
        tags = []
        content_lower = content.lower()
        
        # Common tag patterns
        tag_patterns = {
            "urgent": ["urgent", "asap", "immediately", "critical"],
            "follow-up": ["follow up", "follow-up", "todo", "action item"],
            "question": ["question", "ask", "wondering", "clarification"],
            "decision": ["decided", "decision", "approved", "rejected"],
            "update": ["update", "status", "progress", "completed"],
        }
        
        for tag, patterns in tag_patterns.items():
            if any(p in content_lower for p in patterns):
                tags.append(tag)
        
        return tags
