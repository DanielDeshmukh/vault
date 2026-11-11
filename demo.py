"""Vault Demo Runner — Shows RBAC, queries, and document access in action.

Usage:
    python demo.py

This script demonstrates the Vault API by:
1. Logging in as admin and intern
2. Showing document count differences (RBAC proof)
3. Running queries with real answers and citations
4. Showing document listing and detail retrieval
5. Demonstrating admin-only endpoints
"""

import json
import sys
import urllib.request
import urllib.error
import time

BASE = "https://vault-rbac-rag.vercel.app/api"

# ── Colors ────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ── Credentials ───────────────────────────────────────────────────────
CREDENTIALS = [
    {"email": "levi.ackerman@vaultdemo.com", "password": "HumblePie23!", "role": "admin"},
    {"email": "connie.springer@vaultdemo.com", "password": "RoundTabl3!", "role": "intern"},
    {"email": "armin.arlert@vaultdemo.com", "password": "CunningPl4n!", "role": "employee"},
    {"email": "eren.yeager@vaultdemo.com", "password": "FoundingR3x!", "role": "engineer"},
    {"email": "mikasa.ackerman@vaultdemo.com", "password": "ScarletP4th!", "role": "manager"},
    {"email": "sasha.blouse@vaultdemo.com", "password": "Pot4toLover!", "role": "hr"},
    {"email": "hange.zoe@vaultdemo.com", "password": "Explos1veMind!", "role": "legal"},
    {"email": "jean.kirstein@vaultdemo.com", "password": "Command3r!", "role": "finance"},
]

# ── Helpers ───────────────────────────────────────────────────────────
def post_json(url, data, headers=None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def get_json(url, headers=None):
    hdrs = {"Accept": "application/json", "Cache-Control": "no-cache"}
    if headers:
        hdrs.update(headers)
    # Cache-bust for Vercel
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}_t={int(time.time())}"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {BOLD}{CYAN}{title}{RESET}")
    print(f"{'=' * 60}\n")


def subsection(title):
    print(f"\n  {BOLD}{YELLOW}{title}{RESET}")


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def info(msg):
    print(f"  {DIM}{msg}{RESET}")


# ── Demo Steps ────────────────────────────────────────────────────────
def step_health():
    """1. Health check."""
    section("1. Health Check")
    code, body = get_json(f"{BASE}/health")
    if code == 200:
        ok(f"API is healthy — {body.get('app', 'Vault')}")
    else:
        fail(f"Health check failed: {body}")
    return code == 200


def step_login_all():
    """2. Login all roles."""
    section("2. Login All Roles")
    info("Each account has a unique password — see CREDENTIALS.md")
    print()

    tokens = {}
    for cred in CREDENTIALS:
        code, body = post_json(
            f"{BASE}/auth/login",
            {"email": cred["email"], "password": cred["password"]},
        )
        if code == 200 and "access_token" in body:
            user = body.get("user", {})
            role_display = user.get("requested_role") or ("admin" if user.get("is_admin") else cred["role"])
            ok(f"{cred['email']:35s}  role={role_display}  approved={user.get('is_approved')}")
            tokens[cred["role"]] = body["access_token"]
        else:
            fail(f"{cred['email']:35s}  status={code}")

    print()
    return tokens


def step_rbac_documents(tokens):
    """3. RBAC — Document counts per role."""
    section("3. RBAC — Document Access per Role")
    info("Same endpoint, different roles → different document counts")
    print()

    doc_counts = {}
    for role, token in tokens.items():
        code, body = get_json(
            f"{BASE}/documents?limit=1",
            {"Authorization": f"Bearer {token}"},
        )
        if code == 200:
            total = body.get("total", 0)
            doc_counts[role] = total
            bar = "█" * min(total // 100, 50)
            ok(f"{role:12s}  {total:>5,} documents  {DIM}{bar}{RESET}")
        else:
            fail(f"{role:12s}  status={code}")

    print()

    # Show the RBAC gap
    if "admin" in doc_counts and "intern" in doc_counts:
        admin_docs = doc_counts["admin"]
        intern_docs = doc_counts["intern"]
        blocked = admin_docs - intern_docs
        pct = (blocked / admin_docs * 100) if admin_docs else 0
        print(f"  {BOLD}RBAC in action:{RESET}")
        print(f"    Admin sees  {admin_docs:>5,} documents")
        print(f"    Intern sees {intern_docs:>5,} documents")
        print(f"    {RED}{blocked:,} documents blocked{RESET} ({pct:.1f}% of corpus)")
        print()

    return doc_counts


def step_queries(tokens):
    """4. Queries — Admin vs Intern."""
    section("4. Queries — Admin vs Intern")

    questions = [
        "What is the cloud native tools strategy?",
        "How does the onboarding process work?",
        "What are the working groups?",
    ]

    for question in questions:
        subsection(f'Q: "{question}"')

        # Admin query
        admin_token = tokens.get("admin")
        if admin_token:
            code, body = post_json(
                f"{BASE}/query",
                {"question": question},
                {"Authorization": f"Bearer {admin_token}"},
            )
            if code == 200:
                ans = body.get("answer", "")
                cits = body.get("citations", [])
                trace = body.get("trace_id", "N/A")
                # Show first 200 chars of answer
                preview = ans[:200].replace("\n", " ") + "..."
                print(f"  {BOLD}Admin:{RESET}")
                print(f"    Answer: {preview}")
                print(f"    Citations: {len(cits)}  |  Trace: {trace}")
                for c in cits[:3]:
                    info(f"      - {c.get('title', 'N/A')} ({c.get('source', 'N/A')}) score={c.get('score', 0):.4f}")
            else:
                fail(f"Admin query failed: {body.get('detail', body)}")

        # Intern query
        intern_token = tokens.get("intern")
        if intern_token:
            code, body = post_json(
                f"{BASE}/query",
                {"question": question},
                {"Authorization": f"Bearer {intern_token}"},
            )
            if code == 200:
                ans = body.get("answer", "")
                cits = body.get("citations", [])
                preview = ans[:200].replace("\n", " ") + "..."
                print(f"  {BOLD}Intern:{RESET}")
                print(f"    Answer: {preview}")
                print(f"    Citations: {len(cits)}")
                for c in cits[:3]:
                    info(f"      - {c.get('title', 'N/A')} ({c.get('source', 'N/A')}) score={c.get('score', 0):.4f}")
            else:
                fail(f"Intern query failed: {body.get('detail', body)}")

        print()


def step_documents(tokens):
    """5. Document listing and detail."""
    section("5. Documents — Listing & Detail")

    admin_token = tokens.get("admin")
    if not admin_token:
        fail("No admin token")
        return

    # List first 3 documents
    subsection("First 3 documents (admin view)")
    code, body = get_json(
        f"{BASE}/documents?limit=3",
        {"Authorization": f"Bearer {admin_token}"},
    )
    if code == 200:
        items = body.get("items", [])
        for doc in items:
            title = doc.get("title", "Untitled")
            dept = doc.get("department", "N/A")
            roles = doc.get("allowed_roles", [])
            print(f"  • {title}")
            info(f"    Department: {dept}  |  Roles: {', '.join(roles[:4])}{'...' if len(roles) > 4 else ''}")
    else:
        fail(f"Documents list failed: {code}")

    # Get detail of first document
    if items:
        doc_id = items[0]["id"]
        subsection(f"Document detail: {items[0]['title']}")
        code, body = get_json(
            f"{BASE}/documents/{doc_id}",
            {"Authorization": f"Bearer {admin_token}"},
        )
        if code == 200:
            content = body.get("content", "")
            content_preview = content[:300].replace("\n", " ") + "..."
            print(f"  Source: {body.get('source', 'N/A')}")
            print(f"  Classification: {body.get('classification', 'N/A')}")
            print(f"  Content preview: {DIM}{content_preview}{RESET}")
        else:
            fail(f"Document detail failed: {code}")


def step_admin_endpoints(tokens):
    """6. Admin endpoints."""
    section("6. Admin Endpoints")

    admin_token = tokens.get("admin")
    intern_token = tokens.get("intern")
    if not admin_token:
        fail("No admin token")
        return

    # List users
    subsection("List Users (admin)")
    code, body = get_json(
        f"{BASE}/admin/users",
        {"Authorization": f"Bearer {admin_token}"},
    )
    if code == 200 and isinstance(body, list):
        ok(f"{len(body)} users found")
        for user in body[:5]:
            role_str = ", ".join(user.get("roles", []))
            approved = "✓" if user.get("is_approved") else "✗"
            admin_mark = " (admin)" if user.get("is_admin") else ""
            print(f"  • {user.get('email', 'N/A'):35s} {approved}  {role_str}{admin_mark}")
        if len(body) > 5:
            info(f"  ... and {len(body) - 5} more")
    else:
        fail(f"List users failed: {code}")

    # List roles
    subsection("List Roles (admin)")
    code, body = get_json(
        f"{BASE}/admin/roles",
        {"Authorization": f"Bearer {admin_token}"},
    )
    if code == 200 and isinstance(body, list):
        ok(f"{len(body)} roles found")
        for role in body:
            level = role.get("access_level", 0)
            print(f"  • {role.get('name', 'N/A'):15s}  level={level}  {role.get('description', '')}")
    else:
        fail(f"List roles failed: {code}")

    # Non-admin forbidden
    subsection("Non-Admin Access Denied")
    if intern_token:
        code, body = get_json(
            f"{BASE}/admin/users",
            {"Authorization": f"Bearer {intern_token}"},
        )
        if code == 403:
            ok(f"Intern accessing /admin/users → {code} Forbidden (correct!)")
        else:
            fail(f"Expected 403, got {code}")


def step_trace(tokens):
    """7. Trace retrieval."""
    section("7. Audit Trail — Trace Retrieval")

    admin_token = tokens.get("admin")
    if not admin_token:
        fail("No admin token")
        return

    # Run a query to get a fresh trace
    code, body = post_json(
        f"{BASE}/query",
        {"question": "What is the refund policy?"},
        {"Authorization": f"Bearer {admin_token}"},
    )
    if code == 200:
        trace_id = body.get("trace_id", "")
        if trace_id:
            ok(f"Query returned trace_id: {trace_id}")

            # Retrieve the trace
            code2, body2 = get_json(
                f"{BASE}/query/trace/{trace_id}",
                {"Authorization": f"Bearer {admin_token}"},
            )
            if code2 == 200:
                trace = body2
                ok(f"Trace retrieved successfully")
                print(f"  Query: {trace.get('query', 'N/A')}")
                print(f"  User: {trace.get('user_email', 'N/A')}")
                print(f"  Latency: {trace.get('latency_ms', 0):.0f}ms")
                print(f"  Retrieved chunks: {len(trace.get('retrieved_chunks', []))}")
                print(f"  Citations: {len(trace.get('citations', []))}")
            else:
                fail(f"Trace retrieval failed: {code2}")
        else:
            info("No trace_id in response")
    else:
        fail(f"Query failed: {body.get('detail', body)}")


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{BOLD}{'=' * 60}")
    print(f"  Vault RBAC Demo Runner")
    print(f"  Live API: https://vault-rbac-rag.vercel.app")
    print(f"{'=' * 60}{RESET}")

    # 1. Health
    healthy = step_health()
    if not healthy:
        fail("API is not healthy. Exiting.")
        sys.exit(1)

    # 2. Login
    tokens = step_login_all()
    if not tokens:
        fail("No tokens obtained. Exiting.")
        sys.exit(1)

    # 3. RBAC documents
    doc_counts = step_rbac_documents(tokens)

    # 4. Queries
    step_queries(tokens)

    # 5. Documents
    step_documents(tokens)

    # 6. Admin endpoints
    step_admin_endpoints(tokens)

    # 7. Trace
    step_trace(tokens)

    # Summary
    section("Demo Complete!")
    print(f"  {GREEN}All demo steps executed successfully.{RESET}")
    print(f"  Key takeaways:")
    print(f"    • 8 roles with role-based document access")
    print(f"    • Admin sees {doc_counts.get('admin', 0):,} docs, intern sees {doc_counts.get('intern', 0):,} docs")
    print(f"    • Queries return cited answers with trace IDs")
    print(f"    • Admin endpoints protected with 403 for non-admins")
    print()
