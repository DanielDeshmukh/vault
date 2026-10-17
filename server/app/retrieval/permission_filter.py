
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import document_role_names, get_user_allowed_role_names
from app.db.models import Document, User

# Matches no legitimate corpus role. Used as the filter value for a user who
# holds zero roles so the vector store returns nothing instead of everything.
DENY_ALL_ROLE = "__vault_deny_all__"


class PermissionFilter:
    """
    Builds Pinecone metadata filters for permission-aware search.

    CRITICAL: This filter is applied at the vector store level,
    BEFORE the language model sees any content. Unauthorized chunks
    are never loaded into memory or sent to the model.

    Enforcement is by role, not by clearance tier. Every chunk carries an
    explicit ``allowed_roles`` list; a chunk is retrievable only when it
    intersects the roles held by the authenticated user. Tiers remain in the
    schema for legacy UI gating but are never used to gate retrieval, because
    a single ladder cannot express that legal and finance share a tier while
    needing to stay mutually invisible.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_filter(self, user: User) -> dict | None:
        """
        Build a Pinecone filter from the user's role names.

        Returns ``None`` only for admins (unfiltered). Everyone else gets a
        mandatory ``allowed_roles`` constraint; a user with no roles is given
        a sentinel that cannot match any stored chunk, so access is denied by
        default rather than by accident.
        """
        if user.is_admin:
            return None

        roles = await get_user_allowed_role_names(user, self.db)
        # Corpus ACL entries are lowercase; a legacy tier role such as
        # "Internal" would otherwise never match and silently deny.
        roles = [r.lower() for r in roles]
        if not roles:
            return {"allowed_roles": {"$in": [DENY_ALL_ROLE]}}

        return {"allowed_roles": {"$in": list(roles)}}

    async def can_access_document(self, user: User, document_id: str) -> bool:
        """Check if a user can access a specific document by role."""
        if user.is_admin:
            return True

        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if not document:
            return False

        allowed = document_role_names(document)
        if not allowed:
            return False  # deny by default

        user_roles = {r.lower() for r in await get_user_allowed_role_names(user, self.db)}
        return bool(allowed & user_roles)
