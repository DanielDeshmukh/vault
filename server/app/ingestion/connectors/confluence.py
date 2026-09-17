import httpx
from typing import AsyncIterator
from datetime import datetime

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType


class ConfluenceConnector(BaseConnector):
    """Connect to Confluence API to fetch pages."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.CONFLUENCE
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Fetch pages from Confluence.
        
        Config:
            base_url: Confluence instance URL
            email: User email
            api_token: API token
            space_key: Optional space key to filter by
        """
        base_url = config.get("base_url")
        email = config.get("email")
        api_token = config.get("api_token")
        space_key = config.get("space_key")
        
        if not all([base_url, email, api_token]):
            raise ValueError("Missing required Confluence config: base_url, email, api_token")
        
        auth = (email, api_token)
        
        async with httpx.AsyncClient() as client:
            # Fetch pages
            url = f"{base_url}/wiki/rest/api/content"
            params = {
                "limit": 100,
                "expand": "body.storage,version,space"
            }
            
            if space_key:
                params["spaceKey"] = space_key
            
            while True:
                response = await client.get(url, auth=auth, params=params)
                response.raise_for_status()
                data = response.json()
                
                for page in data.get("results", []):
                    # Extract content from storage format
                    body = page.get("body", {}).get("storage", {}).get("value", "")
                    
                    # Parse HTML content
                    content = self._format_page(page, body)
                    
                    # Get space info
                    space = page.get("space", {})
                    
                    yield RawDocument(
                        source=SourceType.CONFLUENCE,
                        source_id=page["id"],
                        title=page.get("title", "Untitled"),
                        content=content,
                        metadata={
                            "account_id": space.get("key", "unknown"),
                            "department": self._infer_department(space.get("name", "")),
                            "space_key": space.get("key"),
                            "space_name": space.get("name"),
                            "version": page.get("version", {}).get("number"),
                        },
                        created_at=datetime.fromisoformat(page["createdAt"].replace("Z", "+00:00")) if page.get("createdAt") else None,
                        author=page.get("version", {}).get("author", {}).get("email"),
                    )
                
                # Check for more pages
                if data.get("size", 0) < data.get("limit", 100):
                    break
                
                # Get next page
                links = data.get("_links", {})
                next_link = links.get("next")
                
                if next_link:
                    url = f"{base_url}/wiki{next_link}" if next_link.startswith("/") else next_link
                    params = {}
                else:
                    break
    
    def _format_page(self, page: dict, body: str) -> str:
        """Format a Confluence page into readable content."""
        parts = [
            f"Title: {page.get('title', 'Untitled')}",
            f"Space: {page.get('space', {}).get('name', 'Unknown')}",
        ]
        
        # Add version info
        version = page.get("version", {})
        if version:
            parts.append(f"Version: {version.get('number', 'Unknown')}")
            parts.append(f"Last updated: {version.get('when', 'Unknown')}")
        
        # Add body content (HTML)
        if body:
            # Simple HTML to text conversion
            import re
            # Remove HTML tags but preserve text
            text = re.sub(r'<[^>]+>', ' ', body)
            text = re.sub(r'\s+', ' ', text).strip()
            parts.append(f"Content:\n{text}")
        
        return "\n\n".join(parts)
    
    def _infer_department(self, space_name: str) -> str:
        """Infer department from space name."""
        space_lower = space_name.lower()
        
        if any(kw in space_lower for kw in ["support", "help", "customer"]):
            return "support"
        elif any(kw in space_lower for kw in ["sales", "marketing", "growth"]):
            return "sales"
        elif any(kw in space_lower for kw in ["engineering", "tech", "dev", "product"]):
            return "engineering"
        elif any(kw in space_lower for kw in ["hr", "people", "culture"]):
            return "hr"
        elif any(kw in space_lower for kw in ["legal", "compliance", "policy"]):
            return "legal"
        
        return "general"
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from Confluence document."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", config.get("space_key", "unknown")),
            department=doc.metadata.get("department", "general"),
            access_level=1,  # Internal by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=[],
        )
    
    async def test_connection(self, config: dict) -> bool:
        """Test Confluence connection."""
        try:
            base_url = config.get("base_url")
            email = config.get("email")
            api_token = config.get("api_token")
            
            if not all([base_url, email, api_token]):
                return False
            
            auth = (email, api_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/wiki/rest/api/user/current",
                    auth=auth
                )
                return response.status_code == 200
                
        except Exception:
            return False
