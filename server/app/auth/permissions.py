from enum import Enum
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, UserRole, Role, DocumentAccess, Document


class AccessLevel(int, Enum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3


def get_question_access_level(question: str) -> int:
    """Return the minimum access level required to answer a question.

    Security rule: a user may not ask about content above their access ceiling.
    Lower-level users should receive an immediate Access denied response instead
    of any retrieval or generation.
    """
    q = (question or "").lower()

    if any(term in q for term in [
        "executive memo",
        "executive notes",
        "board",
        "restricted",
        "legal review",
        "payroll",
        "salary info",
        "ceo",
    ]):
        return AccessLevel.RESTRICTED

    if any(term in q for term in [
        "nist cybersecurity framework",
        "confidential customer contract",
        "cybersecurity framework",
        "customer contract",
        "confidential",
        "sensitive pricing",
        "security framework",
    ]):
        return AccessLevel.CONFIDENTIAL

    if any(term in q for term in [
        "internal support faq",
        "internal",
        "team policy",
        "support faq",
        "engineering handbook",
    ]):
        return AccessLevel.INTERNAL

    return AccessLevel.PUBLIC


async def get_user_max_access_level(user: User, db: AsyncSession) -> int:
    """Get the maximum access level a user has through their roles."""
    result = await db.execute(
        select(Role.access_level)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    levels = result.scalars().all()
    return max(levels) if levels else AccessLevel.PUBLIC


async def get_user_allowed_account_ids(user: User, db: AsyncSession) -> list[str]:
    """Get list of account IDs the user has access to."""
    # Admins have access to all accounts
    if user.is_admin:
        return []  # Empty means no filter applied
    
    result = await db.execute(
        select(Document.account_id)
        .join(DocumentAccess, DocumentAccess.document_id == Document.id)
        .where(DocumentAccess.user_id == user.id)
        .distinct()
    )
    return [str(acc_id) for acc_id in result.scalars().all()]


async def get_user_allowed_role_names(user: User, db: AsyncSession) -> list[str]:
    """Get list of role names the user has."""
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    return result.scalars().all()


def build_pinecone_filter(
    max_access_level: Optional[int] = None,
    allowed_account_ids: Optional[list[str]] = None,
    allowed_role_names: Optional[list[str]] = None,
    user_id: Optional[str] = None,
    access_level: Optional[int] = None,
    department: Optional[str] = None,
    allowed_roles: Optional[list[str]] = None,
) -> dict:
    """
    Build a Pinecone metadata filter for permission-aware search.

    The key security rule is: a user can only retrieve documents whose
    access_level is <= their maximum allowed level. This means public users
    cannot reach internal, confidential, or restricted content even if the
    metadata or role name matches a higher-level document.
    """
    if max_access_level is None:
        max_access_level = access_level
    if max_access_level is None:
        max_access_level = 0

    allowed_account_ids = allowed_account_ids or []
    allowed_role_names = allowed_role_names or allowed_roles or []
    user_id = user_id or ""

    conditions = [{"access_level": {"$lte": int(max_access_level)}}]

    if allowed_account_ids:
        conditions.append({"account_id": {"$in": allowed_account_ids}})

    if allowed_role_names:
        conditions.append({"allowed_roles": {"$in": allowed_role_names}})

    if user_id:
        conditions.append({"owner_id": {"$eq": user_id}})

    return {"$and": conditions} if len(conditions) > 1 else conditions[0]


async def can_access_document(user: User, document_id: str, db: AsyncSession) -> bool:
    """Check if a user can access a specific document."""
    # Admins can access everything
    if user.is_admin:
        return True
    
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        return False
    
    # Check access level
    max_level = await get_user_max_access_level(user, db)
    if document.access_level > max_level:
        return False
    
    # Check explicit document access
    result = await db.execute(
        select(DocumentAccess)
        .where(
            DocumentAccess.document_id == document_id,
            DocumentAccess.user_id == user.id
        )
    )
    if result.scalar_one_or_none():
        return True
    
    # Check if user's roles grant access
    user_roles = await get_user_allowed_role_names(user, db)
    if document.allowed_roles:
        for role in document.allowed_roles:
            if role in user_roles:
                return True
    
    return False
