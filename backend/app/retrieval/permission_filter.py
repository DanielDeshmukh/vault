from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, UserRole, Role, DocumentAccess, Document
from app.auth.permissions import get_user_max_access_level, get_user_allowed_account_ids, get_user_allowed_role_names


class PermissionFilter:
    """
    Builds Pinecone metadata filters for permission-aware search.
    
    CRITICAL: This filter is applied at the vector store level,
    BEFORE the language model sees any content. Unauthorized chunks
    are never loaded into memory or sent to the model.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def build_filter(self, user: User) -> Optional[dict]:
        """
        Build a Pinecone filter based on user's permissions.
        
        Args:
            user: The authenticated user
            
        Returns:
            Pinecone filter dict, or None if user has full access
        """
        # Admins get no filter (access to everything)
        if user.is_admin:
            return None
        
        # Get user's permission scope
        max_level = await get_user_max_access_level(user, self.db)
        allowed_accounts = await get_user_allowed_account_ids(user, self.db)
        allowed_roles = await get_user_allowed_role_names(user, self.db)
        
        # Build filter conditions
        conditions = []
        
        # 1. Access level filter - user can only see documents at or below their max level
        conditions.append({
            "access_level": {"$lte": max_level}
        })
        
        # 2. Account filter - if user has specific account access
        if allowed_accounts:
            conditions.append({
                "$or": [
                    {"account_id": {"$in": allowed_accounts}},
                    {"account_id": {"$eq": "internal"}}  # Always include internal docs
                ]
            })
        
        # 3. Role filter - if user has specific roles
        if allowed_roles:
            conditions.append({
                "$or": [
                    {"allowed_roles": {"$in": allowed_roles}},
                    {"allowed_roles": {"$eq": []}}  # Empty = accessible to all with level
                ]
            })
        
        # 4. Owner filter - user can always access their own documents
        conditions.append({
            "$or": [
                {"owner_id": {"$eq": str(user.id)}},
                {"owner_id": {"$eq": None}},
                {"owner_id": {"$eq": ""}}
            ]
        })
        
        # Combine all conditions
        if len(conditions) == 1:
            return conditions[0]
        
        return {"$and": conditions}
    
    async def can_access_document(self, user: User, document_id: str) -> bool:
        """Check if a user can access a specific document."""
        # Admins can access everything
        if user.is_admin:
            return True
        
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            return False
        
        # Check access level
        max_level = await get_user_max_access_level(user, self.db)
        if document.access_level > max_level:
            return False
        
        # Check explicit document access
        result = await self.db.execute(
            select(DocumentAccess)
            .where(
                DocumentAccess.document_id == document_id,
                DocumentAccess.user_id == user.id
            )
        )
        if result.scalar_one_or_none():
            return True
        
        # Check if user's roles grant access
        user_roles = await get_user_allowed_role_names(user, self.db)
        if document.allowed_roles:
            for role in document.allowed_roles:
                if role in user_roles:
                    return True
        
        return False
