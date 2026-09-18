"""
Vault Golden-50 Evaluation
Runs 50 test queries against the API and scores each on:
  - relevance (does the answer address the question?)
  - citation quality (are real documents cited with good scores?)
  - completeness (does it cover the key points?)
Usage: cd server && python -m scripts.evaluate
"""
import json
import time
import httpx
import sys
import os
from dataclasses import dataclass, field, asdict

BASE = "https://vault-rbac-rag.vercel.app"
EMAIL = "admin@vaultdemo.com"
PASSWORD = "demo1234"

# ---- Golden questions with expected keywords/topics ----

GOLDEN_50 = [
    # --- LEAVE POLICIES (8) ---
    {"q": "What are the paid vacation leave policies?", "expect_keywords": ["vacation", "paid", "days", "accrual", "year"], "category": "leave"},
    {"q": "How does sick leave work?", "expect_keywords": ["sick", "leave", "accrual", "days", "medical"], "category": "leave"},
    {"q": "What is the bereavement leave policy?", "expect_keywords": ["bereavement", "funeral", "family", "death", "leave"], "category": "leave"},
    {"q": "What military leave is available to employees?", "expect_keywords": ["military", "leave", "active duty", "reserve", "national guard"], "category": "leave"},
    {"q": "How does parental leave work?", "expect_keywords": ["parental", "maternity", "paternity", "birth", "adoption"], "category": "leave"},
    {"q": "What are the rules for taking personal leave?", "expect_keywords": ["personal", "leave", "time off", "request", "days"], "category": "leave"},
    {"q": "Can employees use donated leave?", "expect_keywords": ["donated", "leave", "shared", "voluntary", "program"], "category": "leave"},
    {"q": "What is the FMLA leave policy?", "expect_keywords": ["fmla", "family medical leave", "12 weeks", "serious health", "qualifying"], "category": "leave"},

    # --- DRUG-FREE / SUBSTANCE (5) ---
    {"q": "What is the drug-free workplace policy?", "expect_keywords": ["drug", "free", "workplace", "substance", "prohibited"], "category": "drugs"},
    {"q": "What happens if an employee tests positive for drugs?", "expect_keywords": ["positive", "test", "disciplinary", "termination", "suspension"], "category": "drugs"},
    {"q": "Is marijuana use allowed under company policy?", "expect_keywords": ["marijuana", "cannabis", "legal", "prohibited", "policy"], "category": "drugs"},
    {"q": "What are the alcohol policies at work?", "expect_keywords": ["alcohol", "intoxication", "consumption", "under influence", "prohibited"], "category": "drugs"},
    {"q": "Are prescription medications covered under the drug policy?", "expect_keywords": ["prescription", "medication", "over the counter", "misuse", "doctor"], "category": "drugs"},

    # --- CONDUCT / ETHICS (6) ---
    {"q": "What is the code of conduct for employees?", "expect_keywords": ["conduct", "code", "ethics", "behavior", "standards"], "category": "conduct"},
    {"q": "What constitutes workplace harassment?", "expect_keywords": ["harassment", "sexual", "discrimination", "hostile", "unwelcome"], "category": "conduct"},
    {"q": "What is the dress code policy?", "expect_keywords": ["dress", "code", "appearance", "clothing", "professional"], "category": "conduct"},
    {"q": "What are the rules about outside employment?", "expect_keywords": ["outside", "employment", "secondary", "moonlighting", "conflict"], "category": "conduct"},
    {"q": "How does the grievance procedure work?", "expect_keywords": ["grievance", "procedure", "complaint", "process", "resolution"], "category": "conduct"},
    {"q": "What is the workplace violence prevention policy?", "expect_keywords": ["violence", "prevention", "threat", "weapons", "safety"], "category": "conduct"},

    # --- BENEFITS (5) ---
    {"q": "What health insurance benefits are offered?", "expect_keywords": ["health", "insurance", "medical", "dental", "coverage"], "category": "benefits"},
    {"q": "How does the retirement plan work?", "expect_keywords": ["retirement", "pension", "401k", "plan", "contributions"], "category": "benefits"},
    {"q": "What is the employee assistance program?", "expect_keywords": ["assistance", "program", "counseling", "support", "eap"], "category": "benefits"},
    {"q": "What life insurance coverage do employees get?", "expect_keywords": ["life", "insurance", "beneficiary", "coverage", "death"], "category": "benefits"},
    {"q": "Is there tuition reimbursement available?", "expect_keywords": ["tuition", "reimbursement", "education", "training", "courses"], "category": "benefits"},

    # --- SAFETY / SECURITY (5) ---
    {"q": "What is the workplace safety policy?", "expect_keywords": ["safety", "policy", "procedure", "injury", "prevention"], "category": "safety"},
    {"q": "How should employees report safety incidents?", "expect_keywords": ["report", "incident", "accident", "injury", "procedure"], "category": "safety"},
    {"q": "What is the emergency evacuation procedure?", "expect_keywords": ["emergency", "evacuation", "fire", "assembly", "drill"], "category": "safety"},
    {"q": "Are there restrictions on weapons at work?", "expect_keywords": ["weapons", "firearms", "prohibited", "campus", "possession"], "category": "safety"},
    {"q": "What is the cybersecurity policy for employees?", "expect_keywords": ["cybersecurity", "password", "computer", "internet", "security"], "category": "safety"},

    # --- COMPENSATION (4) ---
    {"q": "How does overtime pay work?", "expect_keywords": ["overtime", "pay", "hours", "rate", "compensatory"], "category": "compensation"},
    {"q": "What are the pay periods and schedules?", "expect_keywords": ["pay", "period", "schedule", "biweekly", "direct deposit"], "category": "compensation"},
    {"q": "How is employee classification determined?", "expect_keywords": ["classification", "exempt", "non-exempt", "hourly", "salary"], "category": "compensation"},
    {"q": "What are the rules for compensatory time?", "expect_keywords": ["compensatory", "time", "comp", "earned", "hours"], "category": "compensation"},

    # --- ATTENDANCE (3) ---
    {"q": "What is the attendance and punctuality policy?", "expect_keywords": ["attendance", "punctuality", "tardy", "absent", "schedule"], "category": "attendance"},
    {"q": "What holidays are observed by the organization?", "expect_keywords": ["holiday", "observed", "paid", "calendar", "federal"], "category": "attendance"},
    {"q": "What is the inclement weather policy?", "expect_keywords": ["weather", "inclement", "closure", "delay", "emergency"], "category": "attendance"},

    # --- TECHNOLOGY / COMMUNICATION (4) ---
    {"q": "What is the email and internet use policy?", "expect_keywords": ["email", "internet", "acceptable", "use", "policy"], "category": "technology"},
    {"q": "Can employees use personal devices for work?", "expect_keywords": ["personal", "device", "byod", "phone", "laptop"], "category": "technology"},
    {"q": "What is the social media policy?", "expect_keywords": ["social", "media", "facebook", "twitter", "posting"], "category": "technology"},
    {"q": "What are the rules about confidential information?", "expect_keywords": ["confidential", "information", "data", "privacy", "protected"], "category": "technology"},

    # --- COMPLIANCE (4) ---
    {"q": "What is the NIST Cybersecurity Framework?", "expect_keywords": ["nist", "cybersecurity", "framework", "identify", "protect"], "category": "compliance"},
    {"q": "How does the organization handle data breach incidents?", "expect_keywords": ["breach", "incident", "response", "notification", "reporting"], "category": "compliance"},
    {"q": "What is the equal employment opportunity policy?", "expect_keywords": ["equal", "employment", "opportunity", "discrimination", "protected"], "category": "compliance"},
    {"q": "What are the whistleblower protections?", "expect_keywords": ["whistleblower", "protection", "retaliation", "report", "good faith"], "category": "compliance"},

    # --- ONBOARDING / SEPARATION (3) ---
    {"q": "What happens during the new employee orientation?", "expect_keywords": ["orientation", "new", "employee", "onboarding", "training"], "category": "onboarding"},
    {"q": "What is the probationary period for new hires?", "expect_keywords": ["probationary", "period", "new", "hire", "evaluation"], "category": "onboarding"},
    {"q": "What is the process for voluntary resignation?", "expect_keywords": ["resignation", "voluntary", "notice", "two weeks", "exit"], "category": "onboarding"},

    # --- REMOTE WORK (3) ---
    {"q": "What are the telework eligibility requirements?", "expect_keywords": ["telework", "telecommute", "eligible", "requirements", "agreement"], "category": "remote_work"},
    {"q": "How does remote work affect employee benefits?", "expect_keywords": ["remote", "benefits", "unchanged", "location", "telework"], "category": "remote_work"},
    {"q": "What equipment is provided for remote workers?", "expect_keywords": ["equipment", "laptop", "computer", "provided", "technology"], "category": "remote_work"},
]


@dataclass
class EvalResult:
    q: str
    category: str
    answer: str = ""
    citations: list = field(default_factory=list)
    num_citations: int = 0
    avg_score: float = 0.0
    has_answer: bool = False
    keyword_hits: int = 0
    keyword_total: int = 0
    keyword_ratio: float = 0.0
    latency_ms: float = 0.0
    error: str = ""


def get_token(retries: int = 5):
    for attempt in range(retries):
        try:
            r = httpx.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=60)
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as e:
            print(f"  Login attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError("Failed to login after retries")


def run_query(token: str, question: str, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            r = httpx.post(
                f"{BASE}/api/query",
                json={"question": question},
                headers={"Authorization": f"Bearer {token}"},
                timeout=90,
            )
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            if attempt < retries:
                print(f"         Timeout, retrying ({attempt+1}/{retries})...", flush=True)
                time.sleep(2)
            else:
                raise


def score_answer(answer: str, expect_keywords: list[str]) -> tuple[int, int]:
    answer_lower = answer.lower()
    hits = sum(1 for kw in expect_keywords if kw.lower() in answer_lower)
    return hits, len(expect_keywords)


def evaluate():
    import sys
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("=" * 70)
    print(f"  VAULT GOLDEN-50 EVALUATION (starting from #{start_idx+1})")
    print("=" * 70)

    # Load existing results if resuming
    existing = []
    if start_idx > 0:
        try:
            with open("eval_results.json") as f:
                existing = json.load(f)
                print(f"Loaded {len(existing)} previous results")
        except FileNotFoundError:
            pass

    token = get_token()
    results = []

    for i, item in enumerate(GOLDEN_50[start_idx:], start=start_idx):
        q = item["q"]
        cat = item["category"]
        expect = item["expect_keywords"]
        print(f"\n[{i+1}/50] {cat.upper():15s} | {q}", flush=True)

        start = time.time()
        try:
            resp = run_query(token, q)
            elapsed = (time.time() - start) * 1000

            hits, total = score_answer(resp["answer"], expect)
            num_cites = len(resp.get("citations", []))
            avg_score = (
                sum(c["score"] for c in resp.get("citations", [])) / num_cites
                if num_cites > 0
                else 0
            )

            er = EvalResult(
                q=q,
                category=cat,
                answer=resp["answer"],
                citations=resp.get("citations", []),
                num_citations=num_cites,
                avg_score=avg_score,
                has_answer=bool(resp["answer"]),
                keyword_hits=hits,
                keyword_total=total,
                keyword_ratio=hits / total if total else 0,
                latency_ms=elapsed,
            )
            results.append(er)
            print(
                f"         citations={num_cites}  avg_score={avg_score:.2f}  "
                f"keywords={hits}/{total} ({er.keyword_ratio:.0%})  "
                f"latency={elapsed:.0f}ms"
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            er = EvalResult(q=q, category=cat, error=str(e), latency_ms=elapsed)
            results.append(er)
            print(f"         ERROR: {e}")

    # ---- Summary ----
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    total = len(results)
    successes = [r for r in results if not r.error]
    errors = [r for r in results if r.error]

    if successes:
        avg_keyword = sum(r.keyword_ratio for r in successes) / len(successes)
        avg_citations = sum(r.num_citations for r in successes) / len(successes)
        avg_score = sum(r.avg_score for r in successes) / len(successes)
        avg_latency = sum(r.latency_ms for r in successes) / len(successes)
    else:
        avg_keyword = avg_citations = avg_score = avg_latency = 0

    print(f"\nTotal queries:      {total}")
    print(f"Successful:         {len(successes)}")
    print(f"Errors:             {len(errors)}")
    print(f"Avg keyword recall: {avg_keyword:.1%}")
    print(f"Avg citations:      {avg_citations:.1f}")
    print(f"Avg citation score: {avg_score:.3f}")
    print(f"Avg latency:        {avg_latency:.0f}ms")

    # Per-category breakdown
    categories = {}
    for r in results:
        if r.error:
            continue
        categories.setdefault(r.category, []).append(r)

    print(f"\n{'Category':<18} {'Count':>5} {'KW Recall':>10} {'Avg Cites':>10} {'Avg Score':>10}")
    print("-" * 60)
    for cat, items in sorted(categories.items()):
        kw = sum(r.keyword_ratio for r in items) / len(items)
        cites = sum(r.num_citations for r in items) / len(items)
        score = sum(r.avg_score for r in items) / len(items)
        print(f"{cat:<18} {len(items):>5} {kw:>9.0%} {cites:>10.1f} {score:>10.3f}")

    # Worst performing
    print(f"\n--- Lowest keyword recall ---")
    ranked = sorted(successes, key=lambda r: r.keyword_ratio)
    for r in ranked[:5]:
        print(f"  {r.keyword_ratio:.0%} | {r.q}")

    print(f"\n--- Lowest citation scores ---")
    no_cite = [r for r in results if r.num_citations == 0 and not r.error]
    if no_cite:
        for r in no_cite[:5]:
            print(f"  NO CITES | {r.q}")

    # Save full results
    # Merge with existing results from previous run
    all_results_dict = {}
    for r in existing:
        all_results_dict[r["q"]] = r
    for r in results:
        d = asdict(r)
        d.pop("answer", None)
        d.pop("citations", None)
        all_results_dict[r.q] = d
    out = list(all_results_dict.values())

    with open("eval_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to eval_results.json")


if __name__ == "__main__":
    evaluate()
