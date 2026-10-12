import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt

from app.config import settings
from app.db.sessions import async_session
from app.main import app

# Emails created during this test run, cleaned up at session teardown.
_created_emails: list[str] = []


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def unique_email(prefix: str) -> str:
    """Unique per-run email so tests are repeatable against a live database."""
    email = f"{prefix}_{uuid.uuid4().hex[:10]}@vaulttest.local"
    _created_emails.append(email)
    return email


async def approve_user(email: str) -> None:
    """Flip is_approved=True for a registered user (admin approval gate)."""
    from sqlalchemy import update

    from app.db.models import User

    async with async_session() as db:
        await db.execute(update(User).where(User.email == email).values(is_approved=True))
        await db.commit()


@pytest.fixture(scope="session", autouse=True)
async def cleanup_created_users():
    """Delete users created by these tests after the session finishes."""
    yield
    if not _created_emails:
        return
    from sqlalchemy import delete

    from app.db.models import User

    async with async_session() as db:
        await db.execute(delete(User).where(User.email.in_(_created_emails)))
        await db.commit()


class TestRegistration:
    """Test user registration flow."""

    async def test_register_success(self, client: AsyncClient):
        """Test successful registration returns 201 + token + user, without leaking the hash."""
        email = unique_email("newuser")
        response = await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "New User",
            "department": "support",
        })

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["is_approved"] is False  # must be approved by an admin
        assert "hashed_password" not in response.text

    async def test_register_duplicate_email(self, client: AsyncClient):
        """Test registration with duplicate email fails."""
        email = unique_email("duplicate")
        first = await client.post("/api/auth/register", json={
            "email": email,
            "password": "password12345",
            "full_name": "First User",
            "department": "support",
        })
        assert first.status_code == 201

        response = await client.post("/api/auth/register", json={
            "email": email,
            "password": "password67890",
            "full_name": "Second User",
            "department": "engineering",
        })

        assert response.status_code == 400

    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails validation."""
        response = await client.post("/api/auth/register", json={
            "email": "notanemail",
            "password": "password123",
            "full_name": "User",
            "department": "support",
        })

        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password fails validation."""
        response = await client.post("/api/auth/register", json={
            "email": unique_email("shortpw"),
            "password": "123",
            "full_name": "User",
            "department": "support",
        })

        assert response.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields fails."""
        response = await client.post("/api/auth/register", json={
            "email": unique_email("missing"),
        })

        assert response.status_code == 422


class TestLogin:
    """Test user login flow."""

    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        email = unique_email("loginuser")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "Login User",
            "department": "support",
        })

        response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123",
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password fails."""
        email = unique_email("wrongpw")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "User",
            "department": "support",
        })

        response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "wrongpassword",
        })

        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post("/api/auth/login", json={
            "email": f"nonexistent_{uuid.uuid4().hex[:10]}@vaulttest.local",
            "password": "password123",
        })

        assert response.status_code == 401

    async def test_login_returns_valid_token(self, client: AsyncClient):
        """Test that login returns a JWT that decodes with the user's identity claims."""
        email = unique_email("tokenuser")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "Token User",
            "department": "support",
        })

        login_response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123",
        })

        token = login_response.json()["access_token"]

        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert decoded["email"] == email
        assert decoded["sub"]  # user id claim

    async def test_login_rejects_invalid_email_input(self, client: AsyncClient):
        """Login endpoint validates email format before touching the database."""
        response = await client.post("/api/auth/login", json={
            "email": "not-an-email",
            "password": "password123",
        })

        assert response.status_code == 422


class TestProtectedEndpoints:
    """Test protected endpoints require authentication."""

    async def test_query_without_token(self, client: AsyncClient):
        """Test query endpoint without token returns 401."""
        response = await client.post("/api/query", json={
            "question": "test query",
        })

        assert response.status_code == 401

    async def test_query_with_invalid_token(self, client: AsyncClient):
        """Test query endpoint with invalid token returns 401."""
        response = await client.post("/api/query", json={
            "question": "test query",
        }, headers={
            "Authorization": "Bearer invalidtoken123"
        })

        assert response.status_code == 401

    async def test_query_with_unapproved_token_is_forbidden(self, client: AsyncClient):
        """A cryptographically valid token is still rejected (403) until an admin approves the account."""
        email = unique_email("queryuser")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "Query User",
            "department": "support",
        })

        login_response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123",
        })
        token = login_response.json()["access_token"]

        response = await client.post("/api/query", json={
            "question": "test query",
        }, headers={
            "Authorization": f"Bearer {token}"
        })

        # JWT is accepted (not 401) but the approval gate returns 403
        assert response.status_code == 403
        assert "approval" in response.json()["detail"].lower()


class TestApprovalGate:
    """Unapproved users are blocked everywhere until an admin approves them."""

    async def test_me_blocked_then_allowed_after_approval(self, client: AsyncClient):
        email = unique_email("approval")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "Approval User",
            "department": "support",
        })

        login_response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123",
        })
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Blocked before approval
        before = await client.get("/api/auth/me", headers=headers)
        assert before.status_code == 403

        # Admin approves
        await approve_user(email)

        # Same token now works
        after = await client.get("/api/auth/me", headers=headers)
        assert after.status_code == 200
        data = after.json()
        assert data["email"] == email
        assert data["full_name"] == "Approval User"
        assert data["is_approved"] is True


class TestMeEndpoint:
    """Test /me endpoint."""

    async def test_me_without_token(self, client: AsyncClient):
        """Test /me without token returns 401."""
        response = await client.get("/api/auth/me")

        assert response.status_code == 401

    async def test_me_with_valid_token(self, client: AsyncClient):
        """Test /me with valid token returns user info after approval."""
        email = unique_email("meuser")
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "securepassword123",
            "full_name": "Me User",
            "department": "support",
        })

        login_response = await client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123",
        })
        token = login_response.json()["access_token"]

        await approve_user(email)

        response = await client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["full_name"] == "Me User"

    async def test_me_with_tampered_token(self, client: AsyncClient):
        """A token signed with the wrong key is rejected with 401."""
        import time

        bad_token = jwt.encode(
            {"sub": "someone", "email": "someone@vault.com", "exp": int(time.time()) + 300},
            "wrong-secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        response = await client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {bad_token}"
        })

        assert response.status_code == 401
