from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.sessions import get_db
from app.db.models import User, Role, UserRole
from app.auth.jwt import get_current_user

router = APIRouter()


class UserRoleUpdate(BaseModel):
    role_name: str


class UserApprovalUpdate(BaseModel):
    is_approved: bool


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    department: str
    designation: Optional[str] = None
    is_admin: bool
    is_approved: bool
    roles: list[str] = []

    class Config:
        from_attributes = True


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    response = []
    for u in users:
        roles_result = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == u.id)
        )
        role_names = [r[0] for r in roles_result.fetchall()]
        response.append(AdminUserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            department=u.department,
            designation=u.designation,
            is_admin=u.is_admin,
            is_approved=u.is_approved,
            roles=role_names,
        ))
    return response


@router.put("/users/{user_id}/approve")
async def approve_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot modify admin user")

    user.is_approved = True
    await db.commit()
    return {"status": "approved", "user_id": user_id}


@router.put("/users/{user_id}/reject")
async def reject_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot modify admin user")

    user.is_approved = False
    await db.commit()
    return {"status": "rejected", "user_id": user_id}


@router.put("/users/{user_id}/role")
async def assign_role(
    user_id: str,
    update: UserRoleUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot modify admin role")

    # Find the role
    role_result = await db.execute(select(Role).where(Role.name == update.role_name))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{update.role_name}' not found")

    # Remove existing roles
    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    for ur in existing.scalars().all():
        await db.delete(ur)

    # Assign new role
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    user.is_approved = True

    await db.commit()
    return {"status": "role_assigned", "user_id": user_id, "role": update.role_name}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    # Remove roles first
    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    for ur in existing.scalars().all():
        await db.delete(ur)

    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "user_id": user_id}


@router.get("/roles")
async def list_roles(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).order_by(Role.access_level))
    return [{"name": r.name, "access_level": r.access_level, "description": r.description} for r in result.scalars().all()]
