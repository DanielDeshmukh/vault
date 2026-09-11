import pytest
import asyncio
from typing import AsyncGenerator

from app.db.sessions import async_session
from app.db.models import User, Role, UserRole
from app.auth.jwt import get_password_hash


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Create a database session for testing."""
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        email="test@vault.com",
        hashed_password=get_password_hash("testpassword"),
        full_name="Test User",
        department="support",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()
    
    # Create and assign role
    role = Role(
        name="Support Agent",
        description="Support team member",
        access_level=1,
    )
    db_session.add(role)
    await db_session.flush()
    
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(user_role)
    
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest.fixture
async def admin_user(db_session) -> User:
    """Create an admin user."""
    user = User(
        email="admin@vault.com",
        hashed_password=get_password_hash("adminpassword"),
        full_name="Admin User",
        department="engineering",
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user
