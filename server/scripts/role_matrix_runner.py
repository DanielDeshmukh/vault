import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app.auth.jwt import get_password_hash
from app.db.models import Role, User, UserRole
from app.db.sessions import async_session
from eval.golden_set import GOLDEN_SET
from app.auth.permissions import get_question_access_level

BASE_URL = "http://localhost:8000/api"
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
        "role": "Public",
    },
    {
        "email": "internal.role.test@vault.local",
        "password": "InternalPass@123",
        "role": "Internal",
    },
    {
        "email": "confidential.role.test@vault.local",
        "password": "ConfidentialPass@123",
        "role": "Confidential",
    },
    {
        "email": "restricted.role.test@vault.local",
        "password": "RestrictedPass@123",
        "role": "Restricted",
    },
    {
        "email": "admin.role.test@vault.local",
        "password": "AdminPass@123",
        "role": "Admin",
    },
]


async def ensure_roles() -> None:
    async with async_session() as db:
        for name, level in ROLE_LEVELS.items():
            role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            if role is None:
                db.add(Role(name=name, description=f"{name} access tier", access_level=level))
        await db.commit()


async def assign_roles() -> None:
    async with async_session() as db:
        role_map = {}
        for name in ROLE_LEVELS:
            role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            role_map[name] = role

        for user_info in USERS:
            user = (await db.execute(select(User).where(User.email == user_info["email"]))).scalar_one_or_none()
            if user is None:
                user = User(
                    email=user_info["email"],
                    hashed_password=get_password_hash(user_info["password"]),
                    full_name=user_info["role"] + " Role Test",
                    department="general",
                    is_admin=(user_info["role"] == "Admin"),
                    is_approved=True,
                )
                db.add(user)
                await db.flush()

            existing_roles = (await db.execute(select(UserRole).where(UserRole.user_id == user.id))).scalars().all()
            for assignment in existing_roles:
                await db.delete(assignment)

            role = role_map[user_info["role"]]
            db.add(UserRole(user_id=user.id, role_id=role.id))

        await db.commit()


async def verify_db_roles() -> list[dict[str, Any]]:
    async with async_session() as db:
        listing: list[dict[str, Any]] = []
        for user_info in USERS:
            user = (await db.execute(select(User).where(User.email == user_info["email"]))).scalar_one_or_none()
            if user is None:
                listing.append({"email": user_info["email"], "roles": []})
                continue
            roles = [
                row[0]
                for row in (await db.execute(
                    select(Role.name)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id)
                )).all()
            ]
            listing.append({"email": user_info["email"], "roles": roles})
        return listing


async def login_user(email: str, password: str) -> str:
    response = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {response.status_code} {response.text[:400]}")
    payload = response.json()
    return payload["access_token"]


def get_expected_decision(role_name: str, question: str) -> str:
    required = get_question_access_level(question)
    max_level = ROLE_LEVELS[role_name]
    return "allow" if required <= max_level else "refuse"


async def run_matrix() -> None:
    await ensure_roles()
    await assign_roles()

    db_roles = await verify_db_roles()
    print("DATABASE ROLES")
    for item in db_roles:
        print(f"- {item['email']} -> {item['roles']}")
    print()

    for user_info in USERS:
        token = await login_user(user_info["email"], user_info["password"])
        print(f"ROLE: {user_info['role']} | USER: {user_info['email']}")
        results = []
        for question in GOLDEN_SET:
            response = httpx.post(
                f"{BASE_URL}/query",
                json={"question": question.question},
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            expected = get_expected_decision(user_info["role"], question.question)
            answer_text = ""
            if response.status_code == 200:
                body = response.json()
                answer_text = body.get("answer", "")
            elif response.status_code == 403:
                body = response.json()
                answer_text = body.get("detail", body.get("answer", "Access denied"))
            else:
                answer_text = f"HTTP {response.status_code}: {response.text[:200]}"

            decision = "refuse" if "access denied" in answer_text.lower() or "denied" in answer_text.lower() else "allow"
            results.append({
                "id": question.id,
                "question": question.question,
                "expected": expected,
                "actual": decision,
                "status": "PASS" if expected == decision else "FAIL",
                "answer": answer_text[:200],
            })

        passed = sum(1 for row in results if row["status"] == "PASS")
        print(f"  SUMMARY: {passed}/{len(results)} passed")
        for row in results[:5]:
            print(f"    - {row['id']} | {row['expected']} | {row['actual']} | {row['status']} | {row['answer']}")
        if passed != len(results):
            print("  FAILED QUESTIONS:")
            for row in results:
                if row["status"] == "FAIL":
                    print(f"    - {row['id']} | Q: {row['question']} | expected={row['expected']} | actual={row['actual']}")
        print()


async def main() -> None:
    await run_matrix()


if __name__ == "__main__":
    asyncio.run(main())
