"""One-off column change: drop unused `designation`, add `requested_role`.

`designation` was echoed back by the API but never read by any logic.
`requested_role` records what an applicant asked for at signup; it is
advisory only and grants nothing until an admin assigns a real role.
"""
import asyncio

import asyncpg

from app.config import settings


async def migrate() -> None:
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        cols = {r["column_name"] for r in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users'"
        )}

        if "requested_role" not in cols:
            await conn.execute(
                "ALTER TABLE users ADD COLUMN requested_role VARCHAR(100)"
            )
            print("added users.requested_role")
        else:
            print("users.requested_role already present")

        if "designation" in cols:
            await conn.execute("ALTER TABLE users DROP COLUMN designation")
            print("dropped users.designation")
        else:
            print("users.designation already absent")

        final = [r["column_name"] for r in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' ORDER BY ordinal_position"
        )]
        print(f"users columns now: {final}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
