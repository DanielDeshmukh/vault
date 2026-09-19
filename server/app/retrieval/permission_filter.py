from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, DocumentAccess, Document
from app.auth.permissions import get_user_max_access_level, get_user_allowed_account_ids


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
        Build a Pinecone filter based on the user's maximum access level.

        Security rule: a user may only retrieve documents whose access level is
        at or below their effective permission ceiling.
        """
        if user.is_admin:
            return None

        max_level = await get_user_max_access_level(user, self.db)

        return {"access_level": {"$lte": int(max_level)}}

    async def can_access_document(self, user: User, document_id: str) -> bool:
        """Check if a user can access a specific document."""
        if user.is_admin:
            return True

        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return False

        max_level = await get_user_max_access_level(user, self.db)
        if document.access_level > max_level:
            return False

        result = await self.db.execute(
            select(DocumentAccess)
            .where(
                DocumentAccess.document_id == document_id,
                DocumentAccess.user_id == user.id
            )
        )
        if result.scalar_one_or_none():
            return True

        return False
