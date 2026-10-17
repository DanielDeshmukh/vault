import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sessions import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    # Role the applicant asked for at signup. Advisory only — an admin must
    # still assign a real role before it grants anything.
    requested_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)  # Admin must approve
    # Timestamp when unapproved user first logged in
    approval_screen_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user")
    allowed_documents: Mapped[list["DocumentAccess"]] = relationship(
        "DocumentAccess", back_populates="user"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # 0=public, 1=internal, 2=confidential, 3=restricted
    access_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    users: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", back_populates="users")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # zendesk, jira, slack, etc.
    source_id: Mapped[str | None] = mapped_column(String(255))  # Original ID from source system
    source_file: Mapped[str | None] = mapped_column(Text)  # Path of the originating file in the corpus
    account_id: Mapped[str | None] = mapped_column(String(255), index=True)
    department: Mapped[str | None] = mapped_column(String(100), index=True)
    access_level: Mapped[int] = mapped_column(Integer, default=0, index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    doc_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Corpus identity + the authorization ACL that retrieval filters on.
    # These columns exist in the schema written by scripts/ingest_corpus.py;
    # they were previously unmapped, so document.allowed_roles raised
    # AttributeError and could never be evaluated.
    doc_id: Mapped[str | None] = mapped_column(String(255), index=True)
    classification: Mapped[str | None] = mapped_column(String(50))
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Full-text index over title + content, maintained by Postgres rather than
    # by application code. Title is weighted A and body B so ts_rank prefers a
    # document that is *about* the query over one that merely mentions it.
    # GENERATED ALWAYS AS ... STORED means the database backfills existing rows
    # and scripts/ingest_corpus.py needs no change: its INSERT lists columns
    # explicitly, so Postgres fills this one in itself.
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(content, '')), 'B')",
            persisted=True,
        ),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # GIN, not the default btree: an inverted index answers "which docs
        # contain these terms" in time proportional to the match, not to the
        # 94 MB of content that it would otherwise have to read.
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
    )

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document")
    accesses: Mapped[list["DocumentAccess"]] = relationship("DocumentAccess", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    pinecone_id: Mapped[str | None] = mapped_column(String(255))  # Reference to Pinecone
    # Added to the live schema by scripts/migrate_corpus_schema.py. Rows
    # written through the ORM before that migration leave these NULL; rows
    # written by scripts/ingest_corpus.py always fill them in.
    citation: Mapped[str | None] = mapped_column(Text)
    section_index: Mapped[int | None] = mapped_column(Integer)
    section_span_start: Mapped[int | None] = mapped_column(Integer)
    section_span_end: Mapped[int | None] = mapped_column(Integer)
    part: Mapped[int | None] = mapped_column(Integer)
    section_parts: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class DocumentAccess(Base):
    __tablename__ = "document_access"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="accesses")
    user: Mapped["User"] = relationship("User", back_populates="allowed_documents")
