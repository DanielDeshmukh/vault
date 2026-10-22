
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, literal, literal_column, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.auth.jwt import get_current_user
from app.auth.permissions import document_role_names, get_user_allowed_role_names
from app.db.models import Document, DocumentChunk, DocumentChunkV2, User
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


class ChunkPreview(BaseModel):
    """One chunk hydrated for the preview modal.

    ``text_md`` is always present: the frontend renderer never receives
    ``text_embed`` (embedding text is not display text, plan section A) and
    never fetches chunk bodies from the vector store.
    """

    chunk_id: str
    doc_id: str
    title: str
    heading_path: list[str] = Field(default_factory=list)
    department: str | None = None
    classification: str | None = None
    source_type: str | None = None
    source_path: str | None = None
    block_type: str | None = None
    chunk_version: int = 2
    text_md: str


async def user_role_names(user: User, db: AsyncSession) -> list[str] | None:
    """Role names granting document access, lowercased to match the ACL.

    Returns ``None`` for admins (no restriction) and an empty list for a user
    holding no roles, so callers can express deny-by-default.
    """
    if user.is_admin:
        return None
    roles = await get_user_allowed_role_names(user, db)
    return [r.lower() for r in roles]


def acl_grants(roles: list[str] | None, allowed: set[str]) -> bool:
    """Shared ACL decision for chunk/document hydration.

    ``roles is None`` means admin (allow). Otherwise: deny-by-default -- a
    caller with no roles, an empty/malformed ACL, or no intersection is a
    denial, never a widening. Both sides are lowercased here so a legacy
    tier role such as "Internal" cannot silently deny against a lowercase
    corpus ACL, regardless of what the caller passed. Kept as a pure
    function so the endpoint's security decision is unit-testable without a
    database.
    """
    if roles is None:
        return True
    user_roles = {str(r).lower() for r in roles}
    acl = {str(r).lower() for r in allowed}
    return bool(user_roles) and bool(user_roles & acl)


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


@router.get("/chunk/{chunk_id}", response_model=ChunkPreview)
async def get_chunk_preview(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hydrate one chunk's display markdown for the preview UI.

    Postgres is the source of truth for ``text_md`` (plan decision locked at
    CP3: the renderer never reads chunk text from Pinecone metadata). The
    role ACL is re-applied here on purpose: a chunk id is a bearer handle, so
    a chunk that the retrieval filter would have excluded must not become
    readable by id-guessing -- the same check runs again at this boundary.

    ``chunk_id`` lives in the URL path and contains ``#``; clients must
    percent-encode it (``encodeURIComponent``), which Starlette decodes back.
    """
    # v2 (corpus rebuild) first, then v1 ids from the live index.
    row = (
        await db.execute(
            select(DocumentChunkV2).where(DocumentChunkV2.chunk_id == chunk_id)
        )
    ).scalar_one_or_none()
    if row is not None:
        roles = await user_role_names(current_user, db)
        raw = row.allowed_roles
        allowed = {str(r).lower() for r in raw} if isinstance(raw, list) else set()
        if not acl_grants(roles, allowed):
            raise HTTPException(
                status_code=403, detail="Not authorized to view this chunk"
            )
        return ChunkPreview(
            chunk_id=row.chunk_id,
            doc_id=row.doc_id,
            title=row.doc_title,
            heading_path=[str(h) for h in row.heading_path]
            if isinstance(row.heading_path, list)
            else [],
            department=row.department,
            classification=row.classification,
            source_type=row.source_type,
            source_path=row.source_path,
            block_type=row.block_type,
            chunk_version=row.chunk_version,
            text_md=row.text_md,
        )

    joined = (
        await db.execute(
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.pinecone_id == chunk_id)
        )
    ).first()
    if joined is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    chunk, doc = joined

    roles = await user_role_names(current_user, db)
    if not acl_grants(roles, document_role_names(doc)):
        raise HTTPException(
            status_code=403, detail="Not authorized to view this chunk"
        )

    return ChunkPreview(
        chunk_id=chunk_id,
        doc_id=doc.doc_id or str(doc.id),
        title=doc.title,
        heading_path=[],
        department=doc.department,
        classification=doc.classification,
        source_type=doc.source,
        source_path=doc.source_file or doc.source,
        block_type=None,
        chunk_version=1,
        text_md=chunk.content,
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
