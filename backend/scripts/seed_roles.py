import asyncio
from app.db.sessions import async_session, engine, Base
from app.db.models import Role
from sqlalchemy import select


DEFAULT_ROLES = [
    {"name": "Public", "description": "All authenticated users", "access_level": 0},
    {"name": "Internal", "description": "Department-scoped access", "access_level": 1},
    {"name": "Confidential", "description": "Account-scoped access", "access_level": 2},
    {"name": "Restricted", "description": "Named-user only access", "access_level": 3},
]


async def seed_roles():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        for role_data in DEFAULT_ROLES:
            result = await session.execute(
                select(Role).where(Role.name == role_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                role = Role(**role_data)
                session.add(role)
                print(f"Created role: {role_data['name']}")
            else:
                print(f"Role already exists: {role_data['name']}")
        
        await session.commit()
    print("Role seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_roles())
