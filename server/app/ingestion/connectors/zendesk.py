import httpx
from typing import AsyncIterator
from datetime import datetime

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType


class ZendeskConnector(BaseConnector):
    """Connect to Zendesk API to fetch tickets and comments."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.ZENDESK
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Fetch tickets from Zendesk.
        
        Config:
            subdomain: Zendesk subdomain
            email: Agent email
            api_token: API token
            org_id: Optional org ID to filter by
        """
        subdomain = config.get("subdomain")
        email = config.get("email")
        api_token = config.get("api_token")
        org_id = config.get("org_id")
        
        if not all([subdomain, email, api_token]):
            raise ValueError("Missing required Zendesk config: subdomain, email, api_token")
        
        base_url = f"https://{subdomain}.zendesk.com/api/v2"
        auth = (f"{email}/token", api_token)
        
        async with httpx.AsyncClient() as client:
            # Fetch tickets
            url = f"{base_url}/search.json"
            params = {"query": "type:ticket"}
            if org_id:
                params["query"] += f" organization_id:{org_id}"
            
            while url:
                response = await client.get(url, auth=auth, params=params)
                response.raise_for_status()
                data = response.json()
                
                for ticket in data.get("results", []):
                    # Create raw document from ticket
                    content = self._format_ticket(ticket)
                    
                    yield RawDocument(
                        source=SourceType.ZENDESK,
                        source_id=str(ticket["id"]),
                        title=ticket.get("subject", f"Ticket #{ticket['id']}"),
                        content=content,
                        metadata={
                            "account_id": str(ticket.get("organization_id", "unknown")),
                            "department": "support",
                            "status": ticket.get("status"),
                            "priority": ticket.get("priority"),
                            "tags": ticket.get("tags", []),
                        },
                        created_at=datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00")) if ticket.get("created_at") else None,
                        author=ticket.get("requester_id"),
                    )
                    
                    # Fetch comments for this ticket
                    async for comment in self._fetch_comments(client, base_url, auth, ticket["id"]):
                        yield comment
                
                # Pagination
                url = data.get("next_page")
                params = None  # Params are included in next_page URL
    
    async def _fetch_comments(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple,
        ticket_id: int
    ) -> AsyncIterator[RawDocument]:
        """Fetch comments for a ticket."""
        url = f"{base_url}/tickets/{ticket_id}/comments.json"
        
        response = await client.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        for comment in data.get("comments", []):
            yield RawDocument(
                source=SourceType.ZENDESK,
                source_id=f"comment-{comment['id']}",
                title=f"Comment on ticket #{ticket_id}",
                content=comment.get("body", ""),
                metadata={
                    "ticket_id": str(ticket_id),
                    "account_id": "unknown",  # Will be enriched
                    "department": "support",
                    "public": comment.get("public", True),
                },
                created_at=datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00")) if comment.get("created_at") else None,
                author=str(comment.get("author_id")),
            )
    
    def _format_ticket(self, ticket: dict) -> str:
        """Format ticket into readable content."""
        parts = [
            f"Subject: {ticket.get('subject', 'No subject')}",
            f"Status: {ticket.get('status')}",
            f"Priority: {ticket.get('priority')}",
            f"Description:\n{ticket.get('description', 'No description')}",
        ]
        
        if ticket.get("tags"):
            parts.append(f"Tags: {', '.join(ticket['tags'])}")
        
        return "\n\n".join(parts)
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from Zendesk document."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", config.get("org_id", "unknown")),
            department=doc.metadata.get("department", "support"),
            access_level=1,  # Internal by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=doc.metadata.get("tags", []),
        )
    
    async def test_connection(self, config: dict) -> bool:
        """Test Zendesk connection."""
        try:
            subdomain = config.get("subdomain")
            email = config.get("email")
            api_token = config.get("api_token")
            
            if not all([subdomain, email, api_token]):
                return False
            
            base_url = f"https://{subdomain}.zendesk.com/api/v2"
            auth = (f"{email}/token", api_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/users/me.json", auth=auth)
                return response.status_code == 200
                
        except Exception:
            return False
