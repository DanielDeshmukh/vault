from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from app.auth.jwt import get_current_user
from app.db.models import User

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    account_id: Optional[str]
    department: Optional[str]
    access_level: int


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(current_user: User = Depends(get_current_user)):
    # Phase 2: Implement document listing
    return []


@router.post("/ingest", response_model=DocumentResponse)
async def ingest_document(
    file: UploadFile = File(...),
    source: str = "csv",
    current_user: User = Depends(get_current_user)
):
    # Phase 2: Implement document ingestion
    return DocumentResponse(
        id="placeholder",
        title=file.filename or "Untitled",
        source=source,
        account_id=None,
        department=None,
        access_level=0
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    # Phase 2: Implement document retrieval
    return DocumentResponse(
        id=document_id,
        title="Placeholder",
        source="csv",
        account_id=None,
        department=None,
        access_level=0
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    # Phase 2: Implement document deletion
    return {"status": "deleted"}
