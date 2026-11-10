"""Test query with a more relevant question based on the corpus (GitLab handbook)."""
import json, urllib.request, urllib.error

BASE = "https://vault-rbac-rag.vercel.app/api"

def post(url, data, hdrs=None):
    h = {"Content-Type": "application/json"}
    if hdrs:
        h.update(hdrs)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get(url, hdrs=None):
    h = {"Accept": "application/json"}
    if hdrs:
        h.update(hdrs)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# Login as admin
c, b = post(f"{BASE}/auth/login", {"email": "admin@vaultdemo.com", "password": "Vault2026!"})
tok = b["access_token"]
auth = {"Authorization": f"Bearer {tok}"}

# Try queries relevant to the GitLab handbook corpus
queries = [
    "What is the cloud native tools strategy?",
    "What are the working groups at the company?",
    "How does the onboarding process work?",
    "What is the code of conduct?",
]

for q in queries:
    print(f"\nQuery: {q}")
    c, b = post(f"{BASE}/query", {"question": q}, auth)
    if c == 200:
        ans = b.get("answer", "")
        cits = b.get("citations", [])
        print(f"  Status: {c}  |  Answer: {len(ans)} chars  |  Citations: {len(cits)}")
        if cits:
            for cit in cits[:3]:
                print(f"    - {cit.get('title', 'N/A')} (score: {cit.get('score', 'N/A')})")
        print(f"  Preview: {ans[:200]}...")
    else:
        print(f"  Error: {c}  {b}")

# Check document detail
print("\n" + "=" * 60)
print("DOCUMENT DETAIL")
print("=" * 60)
c, b = get(f"{BASE}/documents?limit=1", auth)
if c == 200 and b.get("items"):
    doc_id = b["items"][0]["id"]
    c2, b2 = get(f"{BASE}/documents/{doc_id}", auth)
    print(f"  Status: {c2}")
    if c2 == 200:
        print(f"  Title: {b2.get('title')}")
        print(f"  Content length: {len(b2.get('content', ''))}")
        print(f"  Keys: {list(b2.keys())}")
