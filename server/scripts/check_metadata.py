import asyncio
import asyncpg
import json
import os

DB_URL = os.environ.get("DATABASE_URL", "")

async def main():
    if not DB_URL:
        print("ERROR: Set DATABASE_URL")
        return
    conn = await asyncpg.connect(DB_URL)

    docs = await conn.fetch("SELECT id, title, access_level, allowed_roles, account_id FROM documents ORDER BY title")
    print("=== DOCUMENTS ===")
    for d in docs:
        print(f"  level={d['access_level']} roles={d['allowed_roles']} account={d['account_id']} | {d['title'][:60]}")

    chunks = await conn.fetch("SELECT id, metadata FROM document_chunks LIMIT 2")
    print()
    print("=== CHUNK METADATA SAMPLE ===")
    for c in chunks:
        print(json.dumps(c["metadata"], indent=2)[:500])
        print("---")

    await conn.close()

asyncio.run(main())
