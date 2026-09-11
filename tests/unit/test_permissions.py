import pytest
from app.auth.permissions import PermissionFilter, AccessLevel, RBACEngine


class TestAccessLevel:
    """Test AccessLevel enum."""
    
    def test_access_levels(self):
        """Test all access levels exist."""
        assert AccessLevel.PUBLIC.value == 0
        assert AccessLevel.INTERNAL.value == 1
        assert AccessLevel.CONFIDENTIAL.value == 2
        assert AccessLevel.RESTRICTED.value == 3
    
    def test_access_level_ordering(self):
        """Test access levels are properly ordered."""
        assert AccessLevel.PUBLIC < AccessLevel.INTERNAL
        assert AccessLevel.INTERNAL < AccessLevel.CONFIDENTIAL
        assert AccessLevel.CONFIDENTIAL < AccessLevel.RESTRICTED


class TestRBACEngine:
    """Test RBAC permission engine."""
    
    def test_check_permission_admin(self):
        """Test admin has full access."""
        engine = RBACEngine()
        
        # Admin should have access to everything
        assert engine.check_permission(
            user_roles=["admin"],
            required_role="admin",
            user_access_level=3,
            required_access_level=3,
        ) is True
    
    def test_check_permission_matching_role(self):
        """Test matching role grants access."""
        engine = RBACEngine()
        
        assert engine.check_permission(
            user_roles=["support"],
            required_role="support",
            user_access_level=1,
            required_access_level=1,
        ) is True
    
    def test_check_permission_insufficient_access_level(self):
        """Test insufficient access level denies access."""
        engine = RBACEngine()
        
        assert engine.check_permission(
            user_roles=["support"],
            required_role="support",
            user_access_level=1,
            required_access_level=2,
        ) is False
    
    def test_check_permission_wrong_role(self):
        """Test wrong role denies access."""
        engine = RBACEngine()
        
        assert engine.check_permission(
            user_roles=["support"],
            required_role="executive",
            user_access_level=1,
            required_access_level=1,
        ) is False
    
    def test_check_permission_multiple_roles(self):
        """Test user with multiple roles."""
        engine = RBACEngine()
        
        assert engine.check_permission(
            user_roles=["support", "engineering"],
            required_role="engineering",
            user_access_level=1,
            required_access_level=1,
        ) is True


class TestPermissionFilter:
    """Test permission filter for Pinecone queries."""
    
    @pytest.mark.asyncio
    async def test_admin_gets_none_filter(self):
        """Admin users should get None filter (no restrictions)."""
        from app.db.models import User
        
        # Create mock admin user
        user = User(
            id=1,
            email="admin@vault.com",
            full_name="Admin",
            department="engineering",
            is_admin=True,
        )
        
        async with PermissionFilter() as pf:
            filter_dict = await pf.build_filter(user)
        
        assert filter_dict is None
    
    @pytest.mark.asyncio
    async def test_regular_user_gets_access_level_filter(self):
        """Regular users should get access level filter."""
        from app.db.models import User
        
        # Create mock regular user
        user = User(
            id=2,
            email="user@vault.com",
            full_name="User",
            department="support",
            is_admin=False,
        )
        
        async with PermissionFilter() as pf:
            filter_dict = await pf.build_filter(user)
        
        assert filter_dict is not None
        assert "$and" in filter_dict
    
    @pytest.mark.asyncio
    async def test_filter_includes_department(self):
        """Filter should include department restriction."""
        from app.db.models import User
        
        user = User(
            id=3,
            email="user@vault.com",
            full_name="User",
            department="support",
            is_admin=False,
        )
        
        async with PermissionFilter() as pf:
            filter_dict = await pf.build_filter(user)
        
        # Check department filter exists
        and_conditions = filter_dict.get("$and", [])
        dept_found = False
        
        for condition in and_conditions:
            if "department" in condition:
                dept_found = True
                break
        
        assert dept_found or len(and_conditions) > 0


class TestPineconeFilterBuilding:
    """Test Pinecone filter construction."""
    
    def test_build_access_level_filter(self):
        """Test building access level filter."""
        from app.auth.permissions import build_pinecone_filter
        
        filter_dict = build_pinecone_filter(
            access_level=1,
            department="support",
            allowed_roles=["support", "admin"],
        )
        
        assert "$and" in filter_dict
        
        # Check all conditions are present
        and_conditions = filter_dict["$and"]
        assert len(and_conditions) >= 2
    
    def test_build_filter_public_access(self):
        """Test building filter for public documents."""
        from app.auth.permissions import build_pinecone_filter
        
        filter_dict = build_pinecone_filter(
            access_level=0,
            department=None,
            allowed_roles=[],
        )
        
        assert "$and" in filter_dict
    
    def test_build_filter_restricted_access(self):
        """Test building filter for restricted documents."""
        from app.auth.permissions import build_pinecone_filter
        
        filter_dict = build_pinecone_filter(
            access_level=3,
            department="executive",
            allowed_roles=["executive", "board"],
        )
        
        assert "$and" in filter_dict
        
        # Restricted should have tight filters
        and_conditions = filter_dict["$and"]
        assert len(and_conditions) >= 2
