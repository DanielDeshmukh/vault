import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect(
        "postgresql://neondb_owner:npg_vVxtn09FaNrY@ep-bold-lab-a53tkz2z-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

    docs = await conn.fetch("SELECT id, title, access_level, allowed_roles, account_id FROM documents ORDER BY access_level, title")
    print("=== DOCUMENTS ===")
    for d in docs:
        print(f"  level={d['access_level']} | roles={d['allowed_roles']} | account={d['account_id']} | {d['title'][:60]}")

    chunks = await conn.fetch("SELECT id, metadata FROM document_chunks LIMIT 3")
    print()
    print("=== CHUNK METADATA SAMPLE ===")
    for c in chunks:
        print(f"  chunk {c['id'][:20]}... metadata={json.dumps(c['metadata'], indent=2)[:500]}")

    await conn.close()

asyncio.run(main())
