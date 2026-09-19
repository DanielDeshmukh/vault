import asyncio
from sqlalchemy import select

from app.db.sessions import async_session
from app.db.models import User, Role
from app.auth.jwt import get_password_hash


ROLE_LEVELS = {
    "Public": 0,
    "Internal": 1,
    "Confidential": 2,
    "Restricted": 3,
    "Admin": 99,
}

USERS = [
    {
        "email": "public.role.test@vault.local",
        "password": "PublicPass@123",
        "full_name": "Public Role Test",
        "department": "general",
        "is_admin": False,
        "is_approved": True,
    },
    {
        "email": "internal.role.test@vault.local",
        "password": "InternalPass@123",
        "full_name": "Internal Role Test",
        "department": "general",
        "is_admin": False,
        "is_approved": True,
    },
    {
        "email": "confidential.role.test@vault.local",
        "password": "ConfidentialPass@123",
        "full_name": "Confidential Role Test",
        "department": "general",
        "is_admin": False,
        "is_approved": True,
    },
    {
        "email": "restricted.role.test@vault.local",
        "password": "RestrictedPass@123",
        "full_name": "Restricted Role Test",
        "department": "general",
        "is_admin": False,
        "is_approved": True,
    },
    {
        "email": "admin.role.test@vault.local",
        "password": "AdminPass@123",
        "full_name": "Admin Role Test",
        "department": "general",
        "is_admin": True,
        "is_approved": True,
    },
]


async def ensure_roles() -> None:
    async with async_session() as db:
        for name, level in ROLE_LEVELS.items():
            existing = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            if existing is None:
                db.add(Role(name=name, description=f"{name} access tier", access_level=level))
        await db.commit()


async def ensure_users() -> None:
    async with async_session() as db:
        for user_data in USERS:
            user = (await db.execute(select(User).where(User.email == user_data["email"]))).scalar_one_or_none()
            if user is None:
                user = User(
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    full_name=user_data["full_name"],
                    department=user_data["department"],
                    is_admin=user_data["is_admin"],
                    is_approved=user_data["is_approved"],
                )
                db.add(user)
                print(f"CREATED {user_data['email']} / {user_data['password']}")
            else:
                user.hashed_password = get_password_hash(user_data["password"])
                user.full_name = user_data["full_name"]
                user.department = user_data["department"]
                user.is_admin = user_data["is_admin"]
                user.is_approved = user_data["is_approved"]
                print(f"UPDATED {user_data['email']} / {user_data['password']}")
        await db.commit()


async def main() -> None:
    await ensure_roles()
    await ensure_users()
    print("\nTest users are ready. Assign each one a role in the admin UI or via the assign-role endpoint.")
    for user_data in USERS:
        print(f"- {user_data['email']} | {user_data['password']} | {user_data['full_name']}")


if __name__ == "__main__":
    asyncio.run(main())
