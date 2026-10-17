from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.config import settings
from app.db.models import Role, User, UserRole
from app.db.sessions import get_db

# Syntax-only email format check: accepts internal domains (e.g. @vault.local)
# and performs no DNS deliverability lookups.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

router = APIRouter()


class UserCreate(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8)
    full_name: str
    department: str
    # Optional request only; never grants access. Admin assigns the real role.
    requested_role: str | None = None


class UserLogin(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    department: str
    requested_role: str | None = None
    is_admin: bool
    is_approved: bool = True
    approval_screen_started_at: str | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Roles an applicant may ask for at signup. Deliberately excludes "admin":
# that is granted by an existing admin only.
REQUESTABLE_ROLES = {"intern", "employee", "engineer", "manager", "hr", "legal", "finance"}
# Applied at signup so a pending account is readable but not privileged.
DEFAULT_PENDING_ROLE = "intern"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    requested = (user_data.requested_role or "").strip().lower() or None
    if requested is not None and requested not in REQUESTABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requested_role must be one of: " + ", ".join(sorted(REQUESTABLE_ROLES))
        )

    # Create user. Pending accounts get the default public role so they can read
    # public documents; approval and any higher role are admin decisions.
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        department=user_data.department,
        requested_role=requested,
        is_approved=False,
    )
    db.add(user)
    await db.flush()

    default_role = (
        await db.execute(select(Role).where(Role.name == DEFAULT_PENDING_ROLE))
    ).scalar_one_or_none()
    if default_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Default role '{DEFAULT_PENDING_ROLE}' is missing"
        )
    db.add(UserRole(user_id=user.id, role_id=default_role.id))
    await db.commit()
    await db.refresh(user)

    # Create token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            department=user.department,
            requested_role=user.requested_role,
            is_admin=user.is_admin,
            is_approved=user.is_approved,
            approval_screen_started_at=None,
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    if not user.is_approved:
        if user.approval_screen_started_at is None:
            user.approval_screen_started_at = datetime.utcnow()
            await db.commit()

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            department=user.department,
            requested_role=user.requested_role,
            is_admin=user.is_admin,
            is_approved=user.is_approved,
            approval_screen_started_at=user.approval_screen_started_at.isoformat() if user.approval_screen_started_at else None,
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        department=current_user.department,
        requested_role=current_user.requested_role,
        is_admin=current_user.is_admin,
        is_approved=current_user.is_approved,
        approval_screen_started_at=current_user.approval_screen_started_at.isoformat() if current_user.approval_screen_started_at else None,
    )
