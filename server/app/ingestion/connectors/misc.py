import csv
import io
from typing import AsyncIterator
from datetime import datetime

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType


class TranscriptConnector(BaseConnector):
    """Parse call/meeting transcripts."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.TRANSCRIPT
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Parse transcript content.
        
        Config:
            content: Transcript text content
            title: Transcript title
            customer_id: Customer/account ID
            department: Department (support/sales)
            timestamp: Transcript timestamp
        """
        content = config.get("content", "")
        title = config.get("title", "Transcript")
        customer_id = config.get("customer_id", "unknown")
        department = config.get("department", "support")
        timestamp_str = config.get("timestamp")
        
        if not content:
            raise ValueError("Missing required transcript config: content")
        
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                pass
        
        yield RawDocument(
            source=SourceType.TRANSCRIPT,
            source_id=f"transcript-{hash(content)}",
            title=title,
            content=content,
            metadata={
                "account_id": customer_id,
                "department": department,
            },
            created_at=timestamp,
        )
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from transcript."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", "unknown"),
            department=doc.metadata.get("department", "support"),
            access_level=2,  # Confidential by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=[],
        )


class PolicyConnector(BaseConnector):
    """Parse policy documents."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.POLICY
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Parse policy content.
        
        Config:
            content: Policy text content
            title: Policy title
            department: Department
            access_level: Access level (0-3)
        """
        content = config.get("content", "")
        title = config.get("title", "Policy Document")
        department = config.get("department", "general")
        access_level = config.get("access_level", 1)
        
        if not content:
            raise ValueError("Missing required policy config: content")
        
        yield RawDocument(
            source=SourceType.POLICY,
            source_id=f"policy-{hash(content)}",
            title=title,
            content=content,
            metadata={
                "account_id": "internal",
                "department": department,
                "access_level": access_level,
            },
        )
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from policy."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id="internal",
            department=doc.metadata.get("department", "general"),
            access_level=doc.metadata.get("access_level", 1),
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=[],
        )


class CSVConnector(BaseConnector):
    """Parse CSV file uploads."""
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.CSV
    
    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Parse CSV content.
        
        Config:
            content: CSV text content
            title_column: Column name to use as title
            content_columns: List of columns to include as content
            account_id: Default account ID
            department: Department
        """
        content = config.get("content", "")
        title_column = config.get("title_column")
        content_columns = config.get("content_columns", [])
        account_id = config.get("account_id", "unknown")
        department = config.get("department", "general")
        
        if not content:
            raise ValueError("Missing required CSV config: content")
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        
        for i, row in enumerate(reader):
            # Determine title
            if title_column and title_column in row:
                title = row[title_column]
            else:
                title = f"Row {i + 1}"
            
            # Build content from specified columns or all columns
            if content_columns:
                content_parts = [f"{col}: {row.get(col, '')}" for col in content_columns if row.get(col)]
            else:
                content_parts = [f"{col}: {val}" for col, val in row.items() if val]
            
            row_content = "\n".join(content_parts)
            
            if not row_content.strip():
                continue
            
            yield RawDocument(
                source=SourceType.CSV,
                source_id=f"csv-row-{i}",
                title=title,
                content=row_content,
                metadata={
                    "account_id": account_id,
                    "department": department,
                    "row_index": i,
                },
            )
    
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """Extract metadata from CSV row."""
        return DocumentMetadata(
            source=doc.source.value,
            source_id=doc.source_id,
            account_id=doc.metadata.get("account_id", config.get("account_id", "unknown")),
            department=doc.metadata.get("department", config.get("department", "general")),
            access_level=1,  # Internal by default
            owner_id=doc.author,
            timestamp=doc.created_at,
            tags=[],
        )
