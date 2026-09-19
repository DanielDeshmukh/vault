import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://neondb_owner:npg_vVxtn09FaNrY@ep-bold-lab-a53tkz2z-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

    users = await conn.fetch("SELECT id, email, full_name, is_admin, is_approved FROM users ORDER BY id")
    print("=== ALL USERS ===")
    for u in users:
        print(f"  ID={u['id']} | {u['email']} | name={u['full_name']} | admin={u['is_admin']} | approved={u['is_approved']}")

    roles = await conn.fetch("""
        SELECT u.email, u.full_name, r.name as role_name, r.access_level
        FROM user_roles ur
        JOIN users u ON u.id = ur.user_id
        JOIN roles r ON r.id = ur.role_id
        ORDER BY u.id, r.access_level
    """)
    print()
    print("=== USER ROLES ===")
    for r in roles:
        print(f"  {r['email']} | role={r['role_name']} | access_level={r['access_level']}")

    await conn.close()

asyncio.run(main())
