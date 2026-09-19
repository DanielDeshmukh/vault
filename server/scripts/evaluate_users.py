"""
Vault Multi-User Golden-50 Evaluation
Tests all 50 questions across every user role.
Iterates users, logs in, runs queries, checks permission filtering.

Usage:
  cd server
  python -m scripts.evaluate_users          # run all
  python -m scripts.evaluate_users 0 10     # start at 0, run 10 questions per user
"""
import json
import time
import httpx
import sys
from dataclasses import dataclass, field, asdict

BASE = "https://vault-rbac-rag.vercel.app"

# All users with their passwords
USERS = [
    {"email": "admin@vaultdemo.com",               "password": "demo1234",           "role": "Admin",        "access_level": 99, "is_admin": True},
    {"email": "hr@vaultdemo.com",                  "password": "demo1234",           "role": "Confidential", "access_level": 2,  "is_admin": False},
    {"email": "confidential.role.test@vault.local","password": "ConfidentialPass@123","role": "Confidential","access_level": 2,  "is_admin": False},
    {"email": "engineer@vaultdemo.com",            "password": "demo1234",           "role": "Internal",     "access_level": 1,  "is_admin": False},
    {"email": "internal.role.test@vault.local",    "password": "InternalPass@123",   "role": "Internal",     "access_level": 1,  "is_admin": False},
    {"email": "restricted.role.test@vault.local",  "password": "RestrictedPass@123", "role": "Restricted",    "access_level": 3,  "is_admin": False},
    {"email": "public.role.test@vault.local",      "password": "PublicPass@123",     "role": "Public",        "access_level": 0,  "is_admin": False},
    {"email": "deshmukhdaniel2005@gmail.com",      "password": "Daniel#2005",       "role": "Public",        "access_level": 0,  "is_admin": False},
    {"email": "intern@vaultdemo.com",              "password": "demo1234",           "role": "Public",        "access_level": 0,  "is_admin": False},
]

GOLDEN_50 = [
    {"q": "What are the paid vacation leave policies?", "expect_keywords": ["vacation", "paid", "days", "accrual", "year"], "category": "leave"},
    {"q": "How does sick leave work?", "expect_keywords": ["sick", "leave", "accrual", "days", "medical"], "category": "leave"},
    {"q": "What is the bereavement leave policy?", "expect_keywords": ["bereavement", "funeral", "family", "death", "leave"], "category": "leave"},
    {"q": "What military leave is available to employees?", "expect_keywords": ["military", "leave", "active duty", "reserve", "national guard"], "category": "leave"},
    {"q": "How does parental leave work?", "expect_keywords": ["parental", "maternity", "paternity", "birth", "adoption"], "category": "leave"},
    {"q": "What are the rules for taking personal leave?", "expect_keywords": ["personal", "leave", "time off", "request", "days"], "category": "leave"},
    {"q": "Can employees use donated leave?", "expect_keywords": ["donated", "leave", "shared", "voluntary", "program"], "category": "leave"},
    {"q": "What is the FMLA leave policy?", "expect_keywords": ["fmla", "family medical leave", "12 weeks", "serious health", "qualifying"], "category": "leave"},
    {"q": "What is the drug-free workplace policy?", "expect_keywords": ["drug", "free", "workplace", "substance", "prohibited"], "category": "drugs"},
    {"q": "What happens if an employee tests positive for drugs?", "expect_keywords": ["positive", "test", "disciplinary", "termination", "suspension"], "category": "drugs"},
    {"q": "Is marijuana use allowed under company policy?", "expect_keywords": ["marijuana", "cannabis", "legal", "prohibited", "policy"], "category": "drugs"},
    {"q": "What are the alcohol policies at work?", "expect_keywords": ["alcohol", "intoxication", "consumption", "under influence", "prohibited"], "category": "drugs"},
    {"q": "Are prescription medications covered under the drug policy?", "expect_keywords": ["prescription", "medication", "over the counter", "misuse", "doctor"], "category": "drugs"},
    {"q": "What is the code of conduct for employees?", "expect_keywords": ["conduct", "code", "ethics", "behavior", "standards"], "category": "conduct"},
    {"q": "What constitutes workplace harassment?", "expect_keywords": ["harassment", "sexual", "discrimination", "hostile", "unwelcome"], "category": "conduct"},
    {"q": "What is the dress code policy?", "expect_keywords": ["dress", "code", "appearance", "clothing", "professional"], "category": "conduct"},
    {"q": "What are the rules about outside employment?", "expect_keywords": ["outside", "employment", "secondary", "moonlighting", "conflict"], "category": "conduct"},
    {"q": "How does the grievance procedure work?", "expect_keywords": ["grievance", "procedure", "complaint", "process", "resolution"], "category": "conduct"},
    {"q": "What is the workplace violence prevention policy?", "expect_keywords": ["violence", "prevention", "threat", "weapons", "safety"], "category": "conduct"},
    {"q": "What health insurance benefits are offered?", "expect_keywords": ["health", "insurance", "medical", "dental", "coverage"], "category": "benefits"},
    {"q": "How does the retirement plan work?", "expect_keywords": ["retirement", "pension", "401k", "plan", "contributions"], "category": "benefits"},
    {"q": "What is the employee assistance program?", "expect_keywords": ["assistance", "program", "counseling", "support", "eap"], "category": "benefits"},
    {"q": "What life insurance coverage do employees get?", "expect_keywords": ["life", "insurance", "beneficiary", "coverage", "death"], "category": "benefits"},
    {"q": "Is there tuition reimbursement available?", "expect_keywords": ["tuition", "reimbursement", "education", "training", "courses"], "category": "benefits"},
    {"q": "What is the workplace safety policy?", "expect_keywords": ["safety", "policy", "procedure", "injury", "prevention"], "category": "safety"},
    {"q": "How should employees report safety incidents?", "expect_keywords": ["report", "incident", "accident", "injury", "procedure"], "category": "safety"},
    {"q": "What is the emergency evacuation procedure?", "expect_keywords": ["emergency", "evacuation", "fire", "assembly", "drill"], "category": "safety"},
    {"q": "Are there restrictions on weapons at work?", "expect_keywords": ["weapons", "firearms", "prohibited", "campus", "possession"], "category": "safety"},
    {"q": "What is the cybersecurity policy for employees?", "expect_keywords": ["cybersecurity", "password", "computer", "internet", "security"], "category": "safety"},
    {"q": "How does overtime pay work?", "expect_keywords": ["overtime", "pay", "hours", "rate", "compensatory"], "category": "compensation"},
    {"q": "What are the pay periods and schedules?", "expect_keywords": ["pay", "period", "schedule", "biweekly", "direct deposit"], "category": "compensation"},
    {"q": "How is employee classification determined?", "expect_keywords": ["classification", "exempt", "non-exempt", "hourly", "salary"], "category": "compensation"},
    {"q": "What are the rules for compensatory time?", "expect_keywords": ["compensatory", "time", "comp", "earned", "hours"], "category": "compensation"},
    {"q": "What is the attendance and punctuality policy?", "expect_keywords": ["attendance", "punctuality", "tardy", "absent", "schedule"], "category": "attendance"},
    {"q": "What holidays are observed by the organization?", "expect_keywords": ["holiday", "observed", "paid", "calendar", "federal"], "category": "attendance"},
    {"q": "What is the inclement weather policy?", "expect_keywords": ["weather", "inclement", "closure", "delay", "emergency"], "category": "attendance"},
    {"q": "What is the email and internet use policy?", "expect_keywords": ["email", "internet", "acceptable", "use", "policy"], "category": "technology"},
    {"q": "Can employees use personal devices for work?", "expect_keywords": ["personal", "device", "byod", "phone", "laptop"], "category": "technology"},
    {"q": "What is the social media policy?", "expect_keywords": ["social", "media", "facebook", "twitter", "posting"], "category": "technology"},
    {"q": "What are the rules about confidential information?", "expect_keywords": ["confidential", "information", "data", "privacy", "protected"], "category": "technology"},
    {"q": "What is the NIST Cybersecurity Framework?", "expect_keywords": ["nist", "cybersecurity", "framework", "identify", "protect"], "category": "compliance"},
    {"q": "How does the organization handle data breach incidents?", "expect_keywords": ["breach", "incident", "response", "notification", "reporting"], "category": "compliance"},
    {"q": "What is the equal employment opportunity policy?", "expect_keywords": ["equal", "employment", "opportunity", "discrimination", "protected"], "category": "compliance"},
    {"q": "What are the whistleblower protections?", "expect_keywords": ["whistleblower", "protection", "retaliation", "report", "good faith"], "category": "compliance"},
    {"q": "What happens during the new employee orientation?", "expect_keywords": ["orientation", "new", "employee", "onboarding", "training"], "category": "onboarding"},
    {"q": "What is the probationary period for new hires?", "expect_keywords": ["probationary", "period", "new", "hire", "evaluation"], "category": "onboarding"},
    {"q": "What is the process for voluntary resignation?", "expect_keywords": ["resignation", "voluntary", "notice", "two weeks", "exit"], "category": "onboarding"},
    {"q": "What are the telework eligibility requirements?", "expect_keywords": ["telework", "telecommute", "eligible", "requirements", "agreement"], "category": "remote_work"},
    {"q": "How does remote work affect employee benefits?", "expect_keywords": ["remote", "benefits", "unchanged", "location", "telework"], "category": "remote_work"},
    {"q": "What equipment is provided for remote workers?", "expect_keywords": ["equipment", "laptop", "computer", "provided", "technology"], "category": "remote_work"},
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
    return None


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
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    num_questions = int(sys.argv[2]) if len(sys.argv) > 2 else len(GOLDEN_50)
    questions = GOLDEN_50[start_idx:start_idx + num_questions]

    print("=" * 80)
    print("  VAULT MULTI-USER GOLDEN-50 EVALUATION")
    print(f"  Users: {len(USERS)} | Questions: {len(questions)} (#{start_idx+1} to #{start_idx+len(questions)})")
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
            idx = start_idx + i
            print(f"\n  [{idx+1}/50] {cat.upper():15s} | {q}", flush=True)

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
                    "hits": hits,
                    "total": total,
                })
                ur.queries_success += 1
                print(
                    f"           citations={num_cites}  avg_score={avg_score:.2f}  "
                    f"keywords={hits}/{total} ({kw_ratio:.0%})  latency={elapsed:.0f}ms"
                )

            except Exception as e:
                elapsed = (time.time() - start) * 1000
                ur.queries_error += 1
                ur.errors.append(f"Q{idx+1}: {str(e)[:100]}")
                print(f"           ERROR: {e}")

            ur.queries_attempted += 1
            time.sleep(1)

        if successes:
            ur.avg_keyword_recall = sum(s["keyword_ratio"] for s in successes) / len(successes)
            ur.avg_citations = sum(s["num_citations"] for s in successes) / len(successes)
            ur.avg_score = sum(s["avg_score"] for s in successes) / len(successes)
            ur.avg_latency_ms = sum(s["latency_ms"] for s in successes) / len(successes)

        all_user_results.append(ur)

    # ---- Summary Table ----
    print("\n\n" + "=" * 100)
    print("  MULTI-USER EVALUATION SUMMARY")
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

    # Per-role averages
    print(f"\n{'='*100}")
    print("  PER-ROLE AVERAGES")
    print(f"{'='*100}")
    role_groups = {}
    for ur in all_user_results:
        role_groups.setdefault(ur.role, []).append(ur)

    print(f"\n{'Role':<14} {'Users':>6} {'KW Recall':>10} {'Cites':>7} {'Score':>7}")
    print("-" * 50)
    for role, users in sorted(role_groups.items()):
        kw = sum(u.avg_keyword_recall for u in users) / len(users)
        cites = sum(u.avg_citations for u in users) / len(users)
        score = sum(u.avg_score for u in users) / len(users)
        print(f"{role:<14} {len(users):>6} {kw:>9.0%} {cites:>7.1f} {score:>7.3f}")

    # Users with errors
    error_users = [ur for ur in all_user_results if ur.errors]
    if error_users:
        print(f"\n{'='*100}")
        print("  USERS WITH ERRORS")
        print(f"{'='*100}")
        for ur in error_users:
            print(f"\n  {ur.email} ({ur.role}):")
            for err in ur.errors[:5]:
                print(f"    - {err}")

    # Save results
    out = []
    for ur in all_user_results:
        d = asdict(ur)
        out.append(d)

    with open("eval_results_users.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to eval_results_users.json")


if __name__ == "__main__":
    main()
