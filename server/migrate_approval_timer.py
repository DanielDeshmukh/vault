import asyncio
import asyncpg
from app.config import settings


async def migrate():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approval_screen_started_at TIMESTAMP"
        )
        print("Column approval_screen_started_at added to users table.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
