"""Seed the 8 corpus role names and grant them to persona users.

The corpus tags every document with allowed_roles drawn from
    intern, employee, engineer, manager, hr, legal, finance, admin
which is a disjoint set from the legacy tier roles
    Public, Internal, Confidential, Restricted, Admin

Both sets coexist: tier roles keep the old UI/evals working, corpus roles
drive retrieval. Corpus roles are stored with access_level=0 so they never
inflate a user's legacy tier ceiling.

Idempotent.

    python server/scripts/seed_corpus_roles.py
"""

import asyncio
import os

import asyncpg

CORPUS_ROLES = [
    "intern",
    "employee",
    "engineer",
    "manager",
    "hr",
    "legal",
    "finance",
    "admin",
]

# email -> corpus role names. Tier roles already on these accounts are left
# untouched; we only ever add.
GRANTS = {
    # demo personas
    "admin@vaultdemo.com": ["admin"],
    "hr@vaultdemo.com": ["hr", "manager"],
    "engineer@vaultdemo.com": ["engineer", "manager"],
    "intern@vaultdemo.com": ["intern", "employee"],
    # owner accounts
    "deshmukhdaniel2005@gmail.com": ["intern"],
    "danieldeshmukh59@gmail.com": ["employee"],
    # tier test accounts, mapped onto the nearest corpus roles so the
    # security evals still get rows back under role-based retrieval
    "public.role.test@vault.local": ["intern"],
    "internal.role.test@vault.local": ["employee"],
    "confidential.role.test@vault.local": ["engineer", "hr"],
    "restricted.role.test@vault.local": [
        "manager", "hr", "legal", "finance", "engineer",
    ],
}


async def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: Set DATABASE_URL")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        added_roles = 0
        for name in CORPUS_ROLES:
            result = await conn.execute(
                """
                INSERT INTO roles (id, name, description, access_level, created_at)
                VALUES (gen_random_uuid(), $1, $2, 0, now())
                ON CONFLICT (name) DO NOTHING
                """,
                name,
                f"Corpus role: {name}",
            )
            if result.endswith("1"):
                added_roles += 1
        print(f"corpus roles: {len(CORPUS_ROLES)} expected, {added_roles} newly inserted")

        rows = await conn.fetch("SELECT id, name FROM roles")
        id_by_name = {r["name"]: r["id"] for r in rows}
        missing = [r for r in CORPUS_ROLES if r not in id_by_name]
        if missing:
            print(f"ERROR: roles missing after insert: {missing}")
            return 1

        granted = 0
        skipped_users = []
        for email, role_names in sorted(GRANTS.items()):
            user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            if not user:
                skipped_users.append(email)
                continue
            for role_name in role_names:
                result = await conn.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES ($1, $2, now())
                    ON CONFLICT DO NOTHING
                    """,
                    user["id"],
                    id_by_name[role_name],
                )
                if result.endswith("1"):
                    granted += 1
        print(f"user_role grants: {granted} newly inserted")

        if skipped_users:
            print(f"  skipped (no such user): {', '.join(skipped_users)}")

        print("\n--- effective corpus roles per user ---")
        for row in await conn.fetch(
            """
            SELECT u.email,
                   COALESCE(string_agg(r.name, ', ' ORDER BY r.name), '(none)') AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id AND r.name = ANY($1)
            GROUP BY u.email
            ORDER BY u.email
            """,
            CORPUS_ROLES,
        ):
            print(f"  {row['email']:<40} {row['roles']}")
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
