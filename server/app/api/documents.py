from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from uuid import UUID
from sqlalchemy import bindparam, func, literal, literal_column, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.auth.jwt import get_current_user
from app.auth.permissions import document_role_names, get_user_allowed_role_names
from app.db.models import User, Document, DocumentChunk
from app.db.sessions import get_db

router = APIRouter()

# Columns the list response carries. Deliberately excludes ``content`` (94 MB
# across the corpus) and ``search_vector`` (rebuilt from it) -- a page of
# results should never pull either into memory.
LIST_COLUMNS = (
    Document.id,
    Document.title,
    Document.source,
    Document.account_id,
    Document.department,
    Document.access_level,
    Document.classification,
    Document.allowed_roles,
    Document.owner_id,
    Document.created_at,
)

CLASSIFICATIONS = ("internal", "restricted")


def fts_query(term: str):
    """Turn free text into a tsquery this server will actually plan.

    Two constraints drove this shape, both established against the live
    catalogue rather than assumed:

    * the config must be a SQL literal cast to ``regconfig`` and the term must
      be bound as ``TEXT``. Binding either side as ``VARCHAR`` fails overload
      resolution outright -- ``plainto_tsquery(character varying,
      character varying) does not exist``.
    * ``plainto_tsquery`` rather than ``websearch_tsquery``, which is simply
      absent from ``pg_catalog`` here. It also cannot raise a syntax error on
      whatever a user types into the search box: it ANDs the terms and stops.
    """
    return func.plainto_tsquery(
        literal_column("'english'::regconfig"), literal(term, type_=TEXT)
    )


class DocumentSummary(BaseModel):
    """One row of ``GET /api/documents``.

    Has no ``content`` field at all -- not a null one. That column is 94 MB
    across the corpus and a list row never needs it; ``GET /api/documents/{id}``
    returns the fuller ``DocumentResponse`` instead.
    """

    id: str
    title: str
    source: str
    account_id: str | None = None
    department: str | None = None
    access_level: int
    classification: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    owner_id: str | None = None
    created_at: str | None = None
    can_access: bool = True

    class Config:
        from_attributes = True


class DocumentResponse(DocumentSummary):
    content: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


async def user_role_names(user: User, db: AsyncSession) -> list[str] | None:
    """Role names granting document access, lowercased to match the ACL.

    Returns ``None`` for admins (no restriction) and an empty list for a user
    holding no roles, so callers can express deny-by-default.
    """
    if user.is_admin:
        return None
    roles = await get_user_allowed_role_names(user, db)
    return [r.lower() for r in roles]


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    classification: str | None = Query(
        None, pattern=f"^(?:{'|'.join(CLASSIFICATIONS)})$"
    ),
    q: str | None = Query(None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Page through the documents this caller is allowed to see.

    ``limit``/``offset`` exist because the corpus is 5,132 documents and 94 MB
    of content; the previous "select every row" behaviour shipped the whole
    list on every page load.

    ``q`` uses Postgres full-text search against the generated
    ``search_vector`` column (GIN-indexed) rather than ``ILIKE``, which would
    read all 94 MB per keystroke and cannot rank results. Search, classification
    and the role ACL are ANDed together, so a filter can never widen what the
    caller is allowed to see.
    """
    roles = await user_role_names(current_user, db)
    if roles is not None and not roles:
        return DocumentListResponse(items=[], total=0, limit=limit, offset=offset)

    term = (q or "").strip()

    # Built per query: the ``_role_names`` bind param is shared by the count
    # and the page statements, and one expression object must not be attached
    # to two different statements.
    def predicates() -> list:
        out: list = []
        if roles is not None:
            out.append(
                Document.allowed_roles.cast(JSONB).op("?|")(
                    bindparam("_role_names", roles, type_=ARRAY(TEXT))
                )
            )
        if classification:
            out.append(Document.classification == classification)
        if term:
            out.append(Document.search_vector.op("@@")(fts_query(term)))
        return out

    total = (
        await db.execute(
            select(func.count()).select_from(Document).where(*predicates())
        )
    ).scalar_one()

    query = (
        select(Document)
        .options(load_only(*LIST_COLUMNS))
        .where(*predicates())
    )
    if term:
        # Normalisation flag 1 divides by document length, so a match in a 2 KB
        # handbook page outranks the same word buried in a 389 KB contract.
        # Title carries weight A and body B in the vector, so a document about
        # the query beats one that merely mentions it.
        rank = func.ts_rank(Document.search_vector, fts_query(term), 1)
        query = query.order_by(
            rank.desc(), Document.created_at.desc(), Document.id.desc()
        )
    else:
        # Every row of the ingested corpus carries the same ``created_at`` (it
        # was written in one bulk pass), so ordering by it alone is a coin
        # flip: OFFSET paging over ties overlaps and skips rows. The primary
        # key is the tiebreaker that makes the sequence total.
        query = query.order_by(Document.created_at.desc(), Document.id.desc())

    result = await db.execute(query.limit(limit).offset(offset))
    docs = result.scalars().all()

    return DocumentListResponse(
        items=[
            DocumentSummary(
                id=str(d.id),
                title=d.title,
                source=d.source,
                account_id=d.account_id,
                department=d.department,
                access_level=d.access_level,
                classification=d.classification,
                allowed_roles=sorted(document_role_names(d)),
                owner_id=str(d.owner_id) if d.owner_id else None,
                created_at=d.created_at.isoformat() if d.created_at else None,
                can_access=True,
            )
            for d in docs
        ],
        total=int(total),
        limit=limit,
        offset=offset,
    )


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
        classification=doc.classification,
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
