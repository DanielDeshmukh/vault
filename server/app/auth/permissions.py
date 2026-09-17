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
    max_access_level: int,
    allowed_account_ids: list[str],
    allowed_role_names: list[str],
    user_id: str
) -> dict:
    """
    Build a Pinecone metadata filter for permission-aware search.
    
    This filter ensures only authorized documents are retrieved.
    The filter is applied at the vector store level, BEFORE the model sees any content.
    """
    conditions = []
    
    # Access level filter - user can only see documents at or below their max level
    conditions.append({
        "access_level": {"$lte": max_access_level}
    })
    
    # If user has specific account access, filter by those accounts
    if allowed_account_ids:
        conditions.append({
            "$or": [
                {"account_id": {"$in": allowed_account_ids}},
                {"account_id": {"$eq": "internal"}}  # Always include internal docs
            ]
        })
    
    # If user has specific roles, they can access documents for those roles
    if allowed_role_names:
        conditions.append({
            "$or": [
                {"allowed_roles": {"$in": allowed_role_names}},
                {"allowed_roles": {"$eq": []}}  # Empty means accessible to all with level
            ]
        })
    
    # Always allow access to user's own documents
    conditions.append({
        "$or": [
            {"owner_id": {"$eq": user_id}},
            {"owner_id": {"$eq": None}}
        ]
    })
    
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
