import asyncio
import asyncpg
import os

DB_URL = os.environ.get("DATABASE_URL", "")

async def main():
    if not DB_URL:
        print("ERROR: Set DATABASE_URL environment variable")
        return
    conn = await asyncpg.connect(DB_URL)

    result = await conn.execute(
        "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE email = 'admin.role.test@vault.local')"
    )
    print(f"Deleted user_roles for second admin: {result}")

    result = await conn.execute(
        "DELETE FROM users WHERE email = 'admin.role.test@vault.local'"
    )
    print(f"Deleted second admin user: {result}")

    sarah = await conn.fetchrow("SELECT id FROM users WHERE email = 'admin@vaultdemo.com'")
    admin_role = await conn.fetchrow("SELECT id FROM roles WHERE name = 'Admin'")

    if not sarah:
        print("ERROR: Sarah user not found")
        await conn.close()
        return
    if not admin_role:
        print("ERROR: Admin role not found")
        await conn.close()
        return

    result = await conn.execute(
        "DELETE FROM user_roles WHERE user_id = $1", sarah["id"]
    )
    print(f"Removed old roles for Sarah: {result}")

    result = await conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        sarah["id"], admin_role["id"]
    )
    print(f"Assigned Admin role to Sarah: {result}")

    result = await conn.execute(
        "UPDATE users SET is_admin = true WHERE email = 'admin@vaultdemo.com'"
    )
    print(f"Set is_admin=true for Sarah: {result}")

    users = await conn.fetch("""
        SELECT u.email, u.full_name, u.is_admin, u.is_approved, r.name as role_name, r.access_level
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY u.email
    """)
    print("\n=== FINAL USERS ===")
    for u in users:
        print(f"  {u['email']} | admin={u['is_admin']} | role={u['role_name']} level={u['access_level']} | {u['full_name']}")

    await conn.close()

asyncio.run(main())
