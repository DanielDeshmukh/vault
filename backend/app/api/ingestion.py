from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from app.auth.jwt import get_current_user
from app.db.models import User
from app.db.sessions import get_db
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.connectors.base import RawDocument, SourceType

router = APIRouter()


class IngestionResponse(BaseModel):
    documents_processed: int
    chunks_created: int
    errors: list[str]


class DirectIngestRequest(BaseModel):
    title: str
    content: str
    source: str = "text"
    account_id: str = "unknown"
    department: str = "general"
    access_level: int = 0


@router.post("/", response_model=IngestionResponse)
async def ingest_document(
    file: UploadFile = File(...),
    source: str = Form("csv"),
    account_id: str = Form("unknown"),
    department: str = Form("general"),
    access_level: int = Form(0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Ingest a document from file upload."""
    # Read file content
    content = await file.read()
    
    # Determine source type
    source_type_map = {
        "csv": SourceType.CSV,
        "pdf": SourceType.POLICY,
        "docx": SourceType.POLICY,
        "txt": SourceType.POLICY,
    }
    source_type = source_type_map.get(source, SourceType.POLICY)
    
    # Create raw document
    raw_doc = RawDocument(
        source=source_type,
        source_id=f"upload-{file.filename}",
        title=file.filename or "Untitled",
        content=content.decode("utf-8") if isinstance(content, bytes) else content,
        metadata={
            "account_id": account_id,
            "department": department,
            "access_level": access_level,
        }
    )
    
    # Run ingestion pipeline
    pipeline = IngestionPipeline()
    result = await pipeline.ingest_single_document(
        raw_doc=raw_doc,
        db=db,
        user_id=str(current_user.id),
        config={"account_id": account_id, "department": department}
    )
    
    return IngestionResponse(
        documents_processed=result.documents_processed,
        chunks_created=result.chunks_created,
        errors=result.errors
    )


@router.post("/direct", response_model=IngestionResponse)
async def ingest_direct(
    request: DirectIngestRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Ingest content directly without file upload."""
    # Create raw document
    source_type_map = {
        "csv": SourceType.CSV,
        "pdf": SourceType.POLICY,
        "docx": SourceType.POLICY,
        "txt": SourceType.POLICY,
        "text": SourceType.POLICY,
        "transcript": SourceType.TRANSCRIPT,
        "policy": SourceType.POLICY,
    }
    source_type = source_type_map.get(request.source, SourceType.POLICY)
    
    raw_doc = RawDocument(
        source=source_type,
        source_id=f"direct-{hash(request.content)}",
        title=request.title,
        content=request.content,
        metadata={
            "account_id": request.account_id,
            "department": request.department,
            "access_level": request.access_level,
        }
    )
    
    # Run ingestion pipeline
    pipeline = IngestionPipeline()
    result = await pipeline.ingest_single_document(
        raw_doc=raw_doc,
        db=db,
        user_id=str(current_user.id),
        config={
            "account_id": request.account_id,
            "department": request.department,
        }
    )
    
    return IngestionResponse(
        documents_processed=result.documents_processed,
        chunks_created=result.chunks_created,
        errors=result.errors
    )


@router.post("/test-connector")
async def test_connector(
    source: str,
    config: dict,
    current_user: User = Depends(get_current_user)
):
    """Test a source connector connection."""
    from app.ingestion.connectors import (
        ZendeskConnector, JiraConnector, SlackConnector, ConfluenceConnector
    )
    
    connector_map = {
        "zendesk": ZendeskConnector,
        "jira": JiraConnector,
        "slack": SlackConnector,
        "confluence": ConfluenceConnector,
    }
    
    connector_class = connector_map.get(source)
    if not connector_class:
        return {"success": False, "error": f"Unknown source: {source}"}
    
    connector = connector_class()
    success = await connector.test_connection(config)
    
    return {"success": success, "source": source}
