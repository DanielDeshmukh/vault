import asyncio
import httpx
import json

BASE = "https://vault-rbac-rag.vercel.app"

USERS = [
    ("public.role.test@vault.local", "PublicPass@123", "Public", 0),
    ("internal.role.test@vault.local", "InternalPass@123", "Internal", 1),
    ("confidential.role.test@vault.local", "ConfidentialPass@123", "Confidential", 2),
    ("admin@vaultdemo.com", "demo1234", "Admin", 99),
]

QUESTIONS = [
    ("What is the NIST cybersecurity framework?", "Confidential doc (level 2)"),
    ("What is the HF Foods employee handbook about?", "Internal doc (level 1)"),
    ("What is the GreenWaste employee handbook about?", "Public doc (level 0)"),
]

async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        for email, password, role, level in USERS:
            r = await client.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
            if r.status_code != 200:
                print(f"{role} (level {level}): LOGIN FAILED")
                continue
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            print(f"\n{'='*60}")
            print(f"  {role} (max access level: {level})")
            print(f"{'='*60}")

            for question, doc_type in QUESTIONS:
                r = await client.post(f"{BASE}/api/query",
                    json={"question": question},
                    headers=headers)
                data = r.json()
                answer = data.get("answer", "")
                citations = data.get("citations", [])
                titles = [c.get("title", "?")[:40] for c in citations]
                print(f"\n  Q: {question}")
                print(f"  Expected: {doc_type}")
                print(f"  Got: {len(citations)} citations - {titles}")
                print(f"  Access check: {'BLOCKED' if len(citations) == 0 and 'NIST' in question and level < 2 else 'OK'}")

asyncio.run(main())
