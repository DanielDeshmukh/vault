from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from sqlalchemy import bindparam, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_user
from app.auth.permissions import document_role_names, get_user_allowed_role_names
from app.db.models import User, Document, DocumentChunk
from app.db.sessions import get_db

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    account_id: Optional[str] = None
    department: Optional[str] = None
    access_level: int
    allowed_roles: list[str] = Field(default_factory=list)
    owner_id: Optional[str] = None
    created_at: Optional[str] = None
    content: Optional[str] = None
    can_access: bool = True

    class Config:
        from_attributes = True


async def user_role_names(user: User, db: AsyncSession) -> Optional[list[str]]:
    """Role names granting document access, lowercased to match the ACL.

    Returns ``None`` for admins (no restriction) and an empty list for a user
    holding no roles, so callers can express deny-by-default.
    """
    if user.is_admin:
        return None
    roles = await get_user_allowed_role_names(user, db)
    return [r.lower() for r in roles]


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await user_role_names(current_user, db)
    query = select(Document)
    if roles is None:
        pass  # admin: no ACL predicate
    elif not roles:
        return []  # no roles -> nothing is visible
    else:
        # ``?|`` on the jsonb array is overlap: the document's allowed_roles
        # must contain at least one of the caller's roles. The explicit
        # ARRAY(TEXT) binding is required -- without it SQLAlchemy infers the
        # parameter type from the left operand and Postgres rejects
        # ``jsonb ?| jsonb``.
        query = query.where(
            Document.allowed_roles.cast(JSONB).op("?|")(
                bindparam("_role_names", roles, type_=ARRAY(TEXT))
            )
        )
    result = await db.execute(query.order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=str(d.id),
            title=d.title,
            source=d.source,
            account_id=d.account_id,
            department=d.department,
            access_level=d.access_level,
            allowed_roles=sorted(document_role_names(d)),
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

    roles = await user_role_names(current_user, db)
    if roles is not None:  # admin sees everything
        allowed = document_role_names(doc)
        if not roles or not (set(roles) & allowed):
            raise HTTPException(
                status_code=403, detail="Not authorized to view this document"
            )

    return DocumentResponse(
        id=str(doc.id),
        title=doc.title,
        source=doc.source,
        account_id=doc.account_id,
        department=doc.department,
        access_level=doc.access_level,
        allowed_roles=sorted(document_role_names(doc)),
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
