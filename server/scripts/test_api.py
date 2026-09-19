import httpx
import os

BASE = os.environ.get("VAULT_API_URL", "https://vault-rbac-rag.vercel.app")
DEMO_PASS = os.environ.get("VAULT_DEMO_PASSWORD", "")

# Test health
try:
    r = httpx.get(f"{BASE}/health", timeout=15)
    print(f"Health: {r.status_code} -> {r.text[:200]}")
except Exception as e:
    print(f"Health error: {e}")

# Test login
try:
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": "admin@vaultdemo.com", "password": DEMO_PASS}, timeout=30)
    print(f"Login: {r.status_code} -> {r.text[:300]}")
except Exception as e:
    print(f"Login error: {e}")
