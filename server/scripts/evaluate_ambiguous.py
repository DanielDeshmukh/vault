"""
Vault Ambiguous Questions Evaluation
Natural, real-world questions that test retrieval quality.

Usage:
  cd server
  Set env vars: VAULT_DEMO_PASSWORD, VAULT_DANIEL_PASSWORD
  python -m scripts.evaluate_ambiguous
"""
import json
import time
import httpx
import sys
import os
from dataclasses import dataclass, field, asdict

BASE = os.environ.get("VAULT_API_URL", "https://vault-rbac-rag.vercel.app")
DEMO_PASS = os.environ.get("VAULT_DEMO_PASSWORD", "")
DANIEL_PASS = os.environ.get("VAULT_DANIEL_PASSWORD", "")

USERS = [
    {"email": "admin@vaultdemo.com",               "password": DEMO_PASS,   "role": "Admin",        "access_level": 99, "is_admin": True},
    {"email": "hr@vaultdemo.com",                  "password": DEMO_PASS,   "role": "Confidential", "access_level": 2,  "is_admin": False},
    {"email": "confidential.role.test@vault.local","password": "ConfidentialPass@123", "role": "Confidential", "access_level": 2, "is_admin": False},
    {"email": "engineer@vaultdemo.com",            "password": DEMO_PASS,   "role": "Internal",     "access_level": 1,  "is_admin": False},
    {"email": "internal.role.test@vault.local",    "password": "InternalPass@123",     "role": "Internal",     "access_level": 1, "is_admin": False},
    {"email": "restricted.role.test@vault.local",  "password": "RestrictedPass@123",   "role": "Restricted",   "access_level": 3, "is_admin": False},
    {"email": "public.role.test@vault.local",      "password": "PublicPass@123",       "role": "Public",       "access_level": 0, "is_admin": False},
    {"email": "deshmukhdaniel2005@gmail.com",      "password": DANIEL_PASS, "role": "Public",       "access_level": 0,  "is_admin": False},
    {"email": "intern@vaultdemo.com",              "password": DEMO_PASS,   "role": "Public",       "access_level": 0,  "is_admin": False},
]

AMBIGUOUS_QUESTIONS = [
    # Natural phrasing - no keyword hints
    {"q": "Can I take time off after my kid is born?", "expect_keywords": ["parental", "maternity", "paternity", "birth", "adoption"], "category": "leave"},
    {"q": "What happens if I get hurt at work?", "expect_keywords": ["report", "incident", "accident", "injury", "procedure"], "category": "safety"},
    {"q": "Am I allowed to work from home?", "expect_keywords": ["telework", "telecommute", "eligible", "requirements", "agreement"], "category": "remote_work"},
    {"q": "Can I bring my gun to the office?", "expect_keywords": ["weapons", "firearms", "prohibited", "campus", "possession"], "category": "safety"},
    {"q": "How do I quit my job here?", "expect_keywords": ["resignation", "voluntary", "notice", "two weeks", "exit"], "category": "onboarding"},
]


@dataclass
class UserResult:
    email: str
    role: str
    access_level: int
    queries_attempted: int = 0
    queries_success: int = 0
    queries_error: int = 0
    avg_keyword_recall: float = 0.0
    avg_citations: float = 0.0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    errors: list = field(default_factory=list)
    details: list = field(default_factory=list)


def login(email, password, retries=3):
    for attempt in range(retries):
        try:
            r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                raise


def run_query(token, question, retries=2):
    for attempt in range(retries + 1):
        try:
            r = httpx.post(
                f"{BASE}/api/query",
                json={"question": question},
                headers={"Authorization": f"Bearer {token}"},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            if attempt < retries:
                time.sleep(3)
            else:
                raise


def score_answer(answer, expect_keywords):
    answer_lower = answer.lower()
    hits = sum(1 for kw in expect_keywords if kw.lower() in answer_lower)
    return hits, len(expect_keywords)


def main():
    questions = AMBIGUOUS_QUESTIONS

    print("=" * 80)
    print("  VAULT AMBIGUOUS QUESTIONS EVALUATION")
    print(f"  Users: {len(USERS)} | Questions: {len(questions)}")
    print("=" * 80)

    all_user_results = []

    for user in USERS:
        email = user["email"]
        role = user["role"]
        level = user["access_level"]
        print(f"\n{'='*80}")
        print(f"  USER: {email}  |  Role: {role}  |  Access Level: {level}")
        print(f"{'='*80}")

        ur = UserResult(email=email, role=role, access_level=level)

        try:
            token = login(email, user["password"])
            print(f"  Login: OK")
        except Exception as e:
            ur.errors.append(f"Login failed: {e}")
            print(f"  Login: FAILED - {e}")
            all_user_results.append(ur)
            continue

        successes = []

        for i, item in enumerate(questions):
            q = item["q"]
            cat = item["category"]
            expect = item["expect_keywords"]
            print(f"\n  [{i+1}/{len(questions)}] {cat.upper():15s} | {q}", flush=True)

            start = time.time()
            try:
                resp = run_query(token, q)
                elapsed = (time.time() - start) * 1000
                hits, total = score_answer(resp["answer"], expect)
                num_cites = len(resp.get("citations", []))
                avg_score = (
                    sum(c["score"] for c in resp.get("citations", [])) / num_cites
                    if num_cites > 0 else 0
                )
                kw_ratio = hits / total if total else 0

                successes.append({
                    "keyword_ratio": kw_ratio,
                    "num_citations": num_cites,
                    "avg_score": avg_score,
                    "latency_ms": elapsed,
                })
                ur.queries_success += 1
                ur.details.append({
                    "q": q, "category": cat, "keyword_ratio": kw_ratio,
                    "num_citations": num_cites, "avg_score": avg_score, "latency_ms": elapsed,
                    "answer_preview": resp["answer"][:200],
                })
                print(
                    f"           citations={num_cites}  avg_score={avg_score:.2f}  "
                    f"keywords={hits}/{total} ({kw_ratio:.0%})  latency={elapsed:.0f}ms"
                )
                print(f"           answer: {resp['answer'][:150]}...")

            except Exception as e:
                elapsed = (time.time() - start) * 1000
                ur.queries_error += 1
                ur.errors.append(f"Q{i+1}: {str(e)[:100]}")
                print(f"           ERROR: {e}")

            ur.queries_attempted += 1
            time.sleep(1)

        if successes:
            ur.avg_keyword_recall = sum(s["keyword_ratio"] for s in successes) / len(successes)
            ur.avg_citations = sum(s["num_citations"] for s in successes) / len(successes)
            ur.avg_score = sum(s["avg_score"] for s in successes) / len(successes)
            ur.avg_latency_ms = sum(s["latency_ms"] for s in successes) / len(successes)

        all_user_results.append(ur)

    # Summary
    print("\n\n" + "=" * 100)
    print("  AMBIGUOUS QUESTIONS SUMMARY")
    print("=" * 100)
    print(f"\n{'Email':<40} {'Role':<14} {'Lvl':>4} {'OK':>4} {'Err':>4} {'KW Recall':>10} {'Cites':>7} {'Score':>7} {'Latency':>9}")
    print("-" * 100)

    for ur in all_user_results:
        print(
            f"{ur.email:<40} {ur.role:<14} {ur.access_level:>4} "
            f"{ur.queries_success:>4} {ur.queries_error:>4} "
            f"{ur.avg_keyword_recall:>9.0%} {ur.avg_citations:>7.1f} "
            f"{ur.avg_score:>7.3f} {ur.avg_latency_ms:>8.0f}ms"
        )

    with open("eval_results_ambiguous.json", "w") as f:
        json.dump([asdict(ur) for ur in all_user_results], f, indent=2)
    print(f"\nResults saved to eval_results_ambiguous.json")


if __name__ == "__main__":
    main()
