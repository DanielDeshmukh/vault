import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRegistration:
    """Test user registration flow."""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful registration."""
        response = await client.post("/api/auth/register", json={
            "email": "newuser@vault.com",
            "password": "securepassword123",
            "full_name": "New User",
            "department": "support",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == "newuser@vault.com"
        assert data["full_name"] == "New User"
        assert "hashed_password" not in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Test registration with duplicate email fails."""
        # Register first user
        await client.post("/api/auth/register", json={
            "email": "duplicate@vault.com",
            "password": "password123",
            "full_name": "First User",
            "department": "support",
        })
        
        # Try to register with same email
        response = await client.post("/api/auth/register", json={
            "email": "duplicate@vault.com",
            "password": "password456",
            "full_name": "Second User",
            "department": "engineering",
        })
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post("/api/auth/register", json={
            "email": "notanemail",
            "password": "password123",
            "full_name": "User",
            "department": "support",
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password fails."""
        response = await client.post("/api/auth/register", json={
            "email": "user@vault.com",
            "password": "123",
            "full_name": "User",
            "department": "support",
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields fails."""
        response = await client.post("/api/auth/register", json={
            "email": "user@vault.com",
        })
        
        assert response.status_code == 422


class TestLogin:
    """Test user login flow."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        # Register user first
        await client.post("/api/auth/register", json={
            "email": "loginuser@vault.com",
            "password": "securepassword123",
            "full_name": "Login User",
            "department": "support",
        })
        
        # Login
        response = await client.post("/api/auth/login", json={
            "email": "loginuser@vault.com",
            "password": "securepassword123",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password fails."""
        # Register user first
        await client.post("/api/auth/register", json={
            "email": "wrongpw@vault.com",
            "password": "securepassword123",
            "full_name": "User",
            "department": "support",
        })
        
        # Login with wrong password
        response = await client.post("/api/auth/login", json={
            "email": "wrongpw@vault.com",
            "password": "wrongpassword",
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post("/api/auth/login", json={
            "email": "nonexistent@vault.com",
            "password": "password123",
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_returns_valid_token(self, client: AsyncClient):
        """Test that login returns a valid JWT token."""
        from app.auth.jwt import decode_access_token
        
        # Register user
        await client.post("/api/auth/register", json={
            "email": "tokenuser@vault.com",
            "password": "securepassword123",
            "full_name": "Token User",
            "department": "support",
        })
        
        # Login
        login_response = await client.post("/api/auth/login", json={
            "email": "tokenuser@vault.com",
            "password": "securepassword123",
        })
        
        token = login_response.json()["access_token"]
        
        # Decode and verify token
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "tokenuser@vault.com"


class TestProtectedEndpoints:
    """Test protected endpoints require authentication."""
    
    @pytest.mark.asyncio
    async def test_query_without_token(self, client: AsyncClient):
        """Test query endpoint without token returns 401."""
        response = await client.post("/api/query", json={
            "query": "test query",
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_query_with_invalid_token(self, client: AsyncClient):
        """Test query endpoint with invalid token returns 401."""
        response = await client.post("/api/query", json={
            "query": "test query",
        }, headers={
            "Authorization": "Bearer invalidtoken123"
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_query_with_valid_token(self, client: AsyncClient):
        """Test query endpoint with valid token."""
        # Register and login
        await client.post("/api/auth/register", json={
            "email": "queryuser@vault.com",
            "password": "securepassword123",
            "full_name": "Query User",
            "department": "support",
        })
        
        login_response = await client.post("/api/auth/login", json={
            "email": "queryuser@vault.com",
            "password": "securepassword123",
        })
        
        token = login_response.json()["access_token"]
        
        # Make query (may fail due to missing services, but should not be 401)
        response = await client.post("/api/query", json={
            "query": "test query",
        }, headers={
            "Authorization": f"Bearer {token}"
        })
        
        # Should not be 401 (might be 500 due to missing services)
        assert response.status_code != 401


class TestMeEndpoint:
    """Test /me endpoint."""
    
    @pytest.mark.asyncio
    async def test_me_without_token(self, client: AsyncClient):
        """Test /me without token returns 401."""
        response = await client.get("/api/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_me_with_valid_token(self, client: AsyncClient):
        """Test /me with valid token returns user info."""
        # Register user
        await client.post("/api/auth/register", json={
            "email": "meuser@vault.com",
            "password": "securepassword123",
            "full_name": "Me User",
            "department": "support",
        })
        
        # Login
        login_response = await client.post("/api/auth/login", json={
            "email": "meuser@vault.com",
            "password": "securepassword123",
        })
        
        token = login_response.json()["access_token"]
        
        # Get me
        response = await client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "meuser@vault.com"
        assert data["full_name"] == "Me User"
