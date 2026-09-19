import asyncio
import asyncpg
import os

async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: Set DATABASE_URL")
        return
    conn = await asyncpg.connect(db_url)

    rows = await conn.fetch("""
        SELECT title, access_level, account_id, department
        FROM documents
        ORDER BY access_level DESC, title
    """)

    print(f"{'Level':>5} | {'Department':<20} | {'Title'}")
    print("-" * 90)
    for r in rows:
        print(f"  {r['access_level']}   | {(r['department'] or ''):<20} | {r['title'][:55]}")

    # Count by level
    counts = await conn.fetch("""
        SELECT access_level, COUNT(*) as cnt
        FROM documents
        GROUP BY access_level
        ORDER BY access_level
    """)
    print("\n--- Documents by access level ---")
    for c in counts:
        print(f"  Level {c['access_level']}: {c['cnt']} documents")

    await conn.close()

asyncio.run(main())
