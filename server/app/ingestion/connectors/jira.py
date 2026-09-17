import httpx
from typing import AsyncIterator
from datetime import datetime

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType


class JiraConnector(BaseConnector):
    """Connect to Jira API to fetch issues and comments."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.JIRA
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Fetch issues from Jira.
        
        Config:
            base_url: Jira instance URL (e.g., https://company.atlassian.net)
            email: User email
            api_token: API token
            project_key: Optional project key to filter by
        """
        base_url = config.get("base_url")
        email = config.get("email")
        api_token = config.get("api_token")
        project_key = config.get("project_key")
        
        if not all([base_url, email, api_token]):
            raise ValueError("Missing required Jira config: base_url, email, api_token")
        
        auth = (email, api_token)
        
        async with httpx.AsyncClient() as client:
            # Build JQL query
            jql = ""
            if project_key:
                jql = f"project = {project_key}"
            
            # Fetch issues
            url = f"{base_url}/rest/api/3/search"
            params = {
                "jql": jql,
                "maxResults": 100,
                "fields": "summary,description,status,priority,issuetype,created,updated,assignee,reporter,labels,components"
            }
            
            while True:
                response = await client.get(url, auth=auth, params=params)
                response.raise_for_status()
                data = response.json()
                
                for issue in data.get("issues", []):
                    # Create raw document from issue
                    content = self._format_issue(issue)
                    
                    fields = issue.get("fields", {})
                    
                    yield RawDocument(
                        source=SourceType.JIRA,
                        source_id=issue["key"],
                        title=fields.get("summary", issue["key"]),
                        content=content,
                        metadata={
                            "account_id": project_key or issue["key"].split("-")[0],
                            "department": "engineering",
                            "status": fields.get("status", {}).get("name"),
                            "priority": fields.get("priority", {}).get("name"),
                            "issue_type": fields.get("issuetype", {}).get("name"),
                            "labels": fields.get("labels", []),
                        },
                        created_at=datetime.fromisoformat(fields["created"].replace("Z", "+00:00")) if fields.get("created") else None,
                        author=fields.get("reporter", {}).get("emailAddress"),
                    )
                    
                    # Fetch comments for this issue
                    async for comment in self._fetch_comments(client, base_url, auth, issue["key"]):
                        yield comment
                
                # Check for more pages
                if data.get("startAt", 0) + data.get("maxResults", 0) >= data.get("total", 0):
                    break
                
                params["startAt"] = data.get("startAt", 0) + data.get("maxResults", 0)
    
    async def _fetch_comments(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple,
        issue_key: str
    ) -> AsyncIterator[RawDocument]:
        """Fetch comments for an issue."""
        url = f"{base_url}/rest/api/3/issue/{issue_key}/comment"
        
        response = await client.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        for comment in data.get("comments", []):
            # Extract text from Atlassian Document Format
            body = self._extract_adf_text(comment.get("body", {}))
            
            yield RawDocument(
                source=SourceType.JIRA,
                source_id=f"comment-{comment['id']}",
                title=f"Comment on {issue_key}",
                content=body,
                metadata={
                    "issue_key": issue_key,
                    "account_id": issue_key.split("-")[0],
                    "department": "engineering",
                },
                created_at=datetime.fromisoformat(comment["created"].replace("Z", "+00:00")) if comment.get("created") else None,
                author=comment.get("author", {}).get("emailAddress"),
            )
    
    def _format_issue(self, issue: dict) -> str:
        """Format issue into readable content."""
        fields = issue.get("fields", {})
        
        parts = [
            f"Issue: {issue['key']}",
            f"Summary: {fields.get('summary', 'No summary')}",
            f"Type: {fields.get('issuetype', {}).get('name', 'Unknown')}",
            f"Status: {fields.get('status', {}).get('name', 'Unknown')}",
            f"Priority: {fields.get('priority', {}).get('name', 'Unknown')}",
        ]
        
        # Extract description (ADF format)
        description = self._extract_adf_text(fields.get("description", {}))
        if description:
            parts.append(f"Description:\n{description}")
        
        if fields.get("labels"):
            parts.append(f"Labels: {', '.join(fields['labels'])}")
        
        if fields.get("components"):
            components = [c.get("name") for c in fields["components"]]
            parts.append(f"Components: {', '.join(components)}")
        
        return "\n\n".join(parts)
    
    def _extract_adf_text(self, adf: dict) -> str:
        """Extract text from Atlassian Document Format."""
        if not adf:
            return ""
        
        if adf.get("type") == "text":
            return adf.get("text", "")
        
        if adf.get("type") == "paragraph":
            return self._extract_adf_text(adf.get("content", [{}])[0] if adf.get("content") else {})
        
        if adf.get("type") in ["doc", "bulletList", "orderedList", "listItem"]:
            texts = []
            for item in adf.get("content", []):
                texts.append(self._extract_adf_text(item))
            return "\n".join(texts)
        
        if adf.get("type") == "heading":
            level = adf.get("attrs", {}).get("level", 1)
            text = self._extract_adf_text(adf.get("content", [{}])[0] if adf.get("content") else {})
            return f"{'#' * level} {text}"
        
        return ""
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from Jira document."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", config.get("project_key", "unknown")),
            department=doc.metadata.get("department", "engineering"),
            access_level=1,  # Internal by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=doc.metadata.get("labels", []),
        )
    
    async def test_connection(self, config: dict) -> bool:
        """Test Jira connection."""
        try:
            base_url = config.get("base_url")
            email = config.get("email")
            api_token = config.get("api_token")
            
            if not all([base_url, email, api_token]):
                return False
            
            auth = (email, api_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/rest/api/3/myself",
                    auth=auth
                )
                return response.status_code == 200
                
        except Exception:
            return False
