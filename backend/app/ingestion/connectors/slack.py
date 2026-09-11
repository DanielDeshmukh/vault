import json
import os
from typing import AsyncIterator
from datetime import datetime

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType


class SlackConnector(BaseConnector):
    """Parse Slack channel exports."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.SLACK
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Parse Slack export.
        
        Config:
            export_path: Path to Slack export directory
            workspace_id: Slack workspace ID
            channels: Optional list of channel names to include
        """
        export_path = config.get("export_path")
        workspace_id = config.get("workspace_id")
        channels_filter = config.get("channels")
        
        if not export_path:
            raise ValueError("Missing required Slack config: export_path")
        
        if not os.path.exists(export_path):
            raise ValueError(f"Export path does not exist: {export_path}")
        
        # Iterate through channel directories
        for channel_name in os.listdir(export_path):
            channel_path = os.path.join(export_path, channel_name)
            
            if not os.path.isdir(channel_path):
                continue
            
            # Filter channels if specified
            if channels_filter and channel_name not in channels_filter:
                continue
            
            # Process each day's messages
            for date_file in sorted(os.listdir(channel_path)):
                if not date_file.endswith(".json"):
                    continue
                
                date_path = os.path.join(channel_path, date_file)
                
                with open(date_path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                
                for message in messages:
                    # Skip bot messages and system messages
                    if message.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                        continue
                    
                    # Format message content
                    content = self._format_message(message, channel_name)
                    
                    if not content.strip():
                        continue
                    
                    # Parse timestamp
                    ts = float(message.get("ts", 0))
                    created_at = datetime.fromtimestamp(ts) if ts else None
                    
                    yield RawDocument(
                        source=SourceType.SLACK,
                        source_id=message.get("ts", f"{channel_name}-{date_file}"),
                        title=f"#{channel_name} - {message.get('text', '')[:50]}",
                        content=content,
                        metadata={
                            "account_id": workspace_id or "unknown",
                            "department": self._infer_department(channel_name),
                            "channel": channel_name,
                            "thread_ts": message.get("thread_ts"),
                            "reactions": [r["name"] for r in message.get("reactions", [])],
                        },
                        created_at=created_at,
                        author=message.get("user"),
                    )
    
    def _format_message(self, message: dict, channel_name: str) -> str:
        """Format a Slack message into readable content."""
        parts = []
        
        # Add channel context
        parts.append(f"Channel: #{channel_name}")
        
        # Add thread context if available
        if message.get("thread_ts") and message.get("reply_count", 0) > 0:
            parts.append(f"Thread with {message['reply_count']} replies")
        
        # Add message text
        text = message.get("text", "")
        if text:
            # Clean up Slack formatting
            text = text.replace("<@", "@").replace(">", "")
            parts.append(text)
        
        # Add file annotations
        if message.get("files"):
            file_names = [f.get("name", "file") for f in message["files"]]
            parts.append(f"Files: {', '.join(file_names)}")
        
        return "\n".join(parts)
    
    def _infer_department(self, channel_name: str) -> str:
        """Infer department from channel name."""
        channel_lower = channel_name.lower()
        
        if any(kw in channel_lower for kw in ["support", "help", "ticket"]):
            return "support"
        elif any(kw in channel_lower for kw in ["sales", "deal", "pipeline"]):
            return "sales"
        elif any(kw in channel_lower for kw in ["eng", "dev", "code", "tech"]):
            return "engineering"
        elif any(kw in channel_lower for kw in ["hr", "people", "team"]):
            return "hr"
        elif any(kw in channel_lower for kw in ["general", "random", "social"]):
            return "general"
        
        return "general"
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from Slack document."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", config.get("workspace_id", "unknown")),
            department=doc.metadata.get("department", "general"),
            access_level=1,  # Internal by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=doc.metadata.get("reactions", []),
        )
