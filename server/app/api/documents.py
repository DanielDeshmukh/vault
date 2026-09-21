from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_user
from app.db.models import User, UserRole, Role, Document, DocumentChunk
from app.db.sessions import get_db

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    account_id: Optional[str] = None
    department: Optional[str] = None
    access_level: int
    owner_id: Optional[str] = None
    created_at: Optional[str] = None
    content: Optional[str] = None
    can_access: bool = True

    class Config:
        from_attributes = True


ACCESS_LEVEL_MAP = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}

async def user_access_level(user: User, db: AsyncSession) -> int:
    if user.is_admin:
        return 3
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    role_names = [r[0].lower() for r in result.all()]
    if role_names:
        return max(ACCESS_LEVEL_MAP.get(r, 0) for r in role_names)
    return 0


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_level = await user_access_level(current_user, db)
    result = await db.execute(
        select(Document)
        .where(Document.access_level <= user_level)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=str(d.id),
            title=d.title,
            source=d.source,
            account_id=d.account_id,
            department=d.department,
            access_level=d.access_level,
            owner_id=str(d.owner_id) if d.owner_id else None,
            created_at=d.created_at.isoformat() if d.created_at else None,
            can_access=True,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user_level = await user_access_level(current_user, db)
    if user_level < doc.access_level:
        raise HTTPException(status_code=403, detail="Insufficient access level for this document")

    return DocumentResponse(
        id=str(doc.id),
        title=doc.title,
        source=doc.source,
        account_id=doc.account_id,
        department=doc.department,
        access_level=doc.access_level,
        owner_id=str(doc.owner_id) if doc.owner_id else None,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        content=doc.content,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete documents")

    # Delete chunks first
    chunks_result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    for chunk in chunks_result.scalars().all():
        await db.delete(chunk)

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "id": document_id}
