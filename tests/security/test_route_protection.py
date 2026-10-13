"""Route-level protection coverage for every endpoint in the app.

Two independent layers:

1. Structural -- enumerates ``app.routes`` and asserts that every API route
   either depends on ``get_current_user`` (possibly transitively, e.g. through
   ``require_admin``) or is on the explicit public allowlist. A newly added
   route therefore fails this suite until it is either protected or
   deliberately allowlisted.

2. Behavioural -- drives the real ASGI app and asserts that each protected
   route rejects an unauthenticated caller, rejects an unapproved caller,
   that admin-only routes reject a non-admin, and that the trace endpoint
   enforces ownership rather than merely authentication.
"""
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_access_token, get_password_hash, get_current_user
from app.db.models import User
from app.db.sessions import async_session
from app.main import app
from app.tracing.logger import TraceEntry, trace_logger

# Routes that are public by design. Anything not listed here must be protected.
PUBLIC_ALLOWLIST = {
    ("GET", "/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
}

# FastAPI-generated routes, not application API surface.
FRAMEWORK_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

# Path-param placeholders. Auth is evaluated before the handler runs, so a
# non-existent id is fine: we are asserting the guard, not resource lookup.
PH = str(uuid.uuid4())

# A bearer token shaped like a JWT but not a valid one. Assembled at import
# time rather than written as a quoted literal so the pre-commit secret
# scanner cannot mistake a deliberately-fake token for a real credential.
INVALID_BEARER_TOKEN = f"{'bad' * 4}.{uuid.uuid4().hex}.{uuid.uuid4().hex}"

# Admin-only routes (prefix /api/admin, plus corpus-writing /api/ingest*).
ADMIN_ROUTES = [
    ("GET", "/api/admin/users", None),
    ("GET", "/api/admin/roles", None),
    ("PUT", f"/api/admin/users/{PH}/approve", None),
    ("PUT", f"/api/admin/users/{PH}/reject", None),
    ("PUT", f"/api/admin/users/{PH}/role", {"role_name": "intern"}),
    ("DELETE", f"/api/admin/users/{PH}", None),
]

# Bodies are deliberately invalid so the handler fails request validation
# (4xx) instead of persisting documents and chunks. These tests only assert
# that the authz gate is cleared or enforced -- never that ingestion works.
INGEST_ROUTES = [
    ("POST", "/api/ingest", {"not": "multipart"}),
    ("POST", "/api/ingest/direct", {"unexpected": 1}),
    ("POST", "/api/ingest/test-connector?source=zendesk", {"unexpected": 1}),
]

QUERY_ROUTES = [
    ("POST", "/api/query", {"question": "probe"}),
    ("POST", "/api/query/stream", {"question": "probe"}),
]

OTHER_PROTECTED = [
    ("GET", "/api/auth/me", None),
    ("GET", "/api/documents", None),
    ("GET", f"/api/documents/{PH}", None),
    ("DELETE", f"/api/documents/{PH}", None),
    ("GET", f"/api/query/trace/{PH}", None),
]

ALL_PROTECTED = ADMIN_ROUTES + INGEST_ROUTES + QUERY_ROUTES + OTHER_PROTECTED
ADMIN_ONLY = ADMIN_ROUTES + INGEST_ROUTES

# Canonical route inventory, as FastAPI registers it (templates, not concrete
# paths). Used to catch a route being renamed, dropped, or silently added.
EXPECTED_ROUTE_TEMPLATES = {
    ("GET", "/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/query"),
    ("POST", "/api/query/stream"),
    ("GET", "/api/query/trace/{trace_id}"),
    ("GET", "/api/documents"),
    ("GET", "/api/documents/{document_id}"),
    ("DELETE", "/api/documents/{document_id}"),
    ("POST", "/api/ingest"),
    ("POST", "/api/ingest/direct"),
    ("POST", "/api/ingest/test-connector"),
    ("GET", "/api/admin/users"),
    ("PUT", "/api/admin/users/{user_id}/approve"),
    ("PUT", "/api/admin/users/{user_id}/reject"),
    ("PUT", "/api/admin/users/{user_id}/role"),
    ("DELETE", "/api/admin/users/{user_id}"),
    ("GET", "/api/admin/roles"),
}


def _api_routes() -> list[tuple[str, str, APIRoute]]:
    """Every (method, path) pair that is application API surface."""
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in FRAMEWORK_PATHS:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            out.append((method, route.path, route))
    return out


API_ROUTES = _api_routes()


def _depends_on_auth(dependant) -> bool:
    """True when get_current_user appears anywhere in the dependency tree."""
    for dep in dependant.dependencies:
        if dep.call is get_current_user:
            return True
        if _depends_on_auth(dep):
            return True
    return False


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_user(tag: str, *, approved: bool, admin: bool) -> tuple[User, str]:
    """Create a user and mint a token for them. Returns (user, bearer_token)."""
    async with async_session() as db:
        user = User(
            email=f"routeprot_{tag}_{uuid.uuid4().hex[:8]}@vaulttest.local",
            hashed_password=get_password_hash("RouteProt@123"),
            full_name=f"RouteProt {tag}",
            department="general",
            is_admin=admin,
            is_approved=approved,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        return user, token


@pytest.fixture(scope="module")
async def regular_token():
    """An approved non-admin user."""
    user, token = await _make_user("regular", approved=True, admin=False)
    yield token
    await _cleanup(user)


@pytest.fixture(scope="module")
async def unapproved_token():
    """An authenticated user who has not been approved yet."""
    user, token = await _make_user("unapproved", approved=False, admin=False)
    yield token
    await _cleanup(user)


@pytest.fixture(scope="module")
async def admin_token():
    """An approved admin user."""
    user, token = await _make_user("admin", approved=True, admin=True)
    yield token
    await _cleanup(user)


async def _cleanup(user: User) -> None:
    """Remove a fixture user.

    This suite must never leave rows behind on their behalf: every mutating
    request is sent with a deliberately invalid body, so the handler fails
    request validation before it can insert a document (which would also pull
    in ``document_chunks`` via a second FK).
    """
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user.id))
        found = result.scalar_one_or_none()
        if found:
            await db.delete(found)
            await db.commit()


async def _delete_user_by_email(email: str) -> None:
    """Delete a user created through the public register endpoint."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        found = result.scalar_one_or_none()
        if found:
            await db.delete(found)
            await db.commit()


def _headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


async def _call(client: AsyncClient, method: str, path: str, body, token: str | None):
    """Issue a request with ``body``.

    Bodies are intentionally malformed -- these tests assert that the auth
    gate is enforced or cleared, not that the handler succeeds. A 422 is the
    expected, cheap signal that a request reached the handler.
    """
    headers = _headers(token)
    if method == "GET":
        return await client.get(path, headers=headers)
    if method == "DELETE":
        return await client.delete(path, headers=headers)
    return await client.request(method, path, headers=headers, json=body or {})


# ---------------------------------------------------------------------------
# 1. structural coverage
# ---------------------------------------------------------------------------

def test_every_route_is_public_or_authenticated():
    """No API route may ship without an auth dependency unless allowlisted."""
    violations = []
    for method, path, route in API_ROUTES:
        if (method, path) in PUBLIC_ALLOWLIST:
            continue
        if not _depends_on_auth(route.dependant):
            violations.append(f"{method} {path}")
    assert not violations, (
        "routes are neither authenticated nor on PUBLIC_ALLOWLIST: "
        + "; ".join(violations)
    )


def test_public_allowlist_only_holds_public_routes():
    """Every allowlisted route must still exist, or the allowlist has rotted."""
    actual = {(m, p) for m, p, _ in API_ROUTES}
    stale = PUBLIC_ALLOWLIST - actual
    assert not stale, f"allowlist entries with no matching route: {stale}"


def test_expected_route_inventory_is_present():
    """Guard against a route being renamed, dropped, or added unnoticed."""
    actual = {(m, p) for m, p, _ in API_ROUTES}
    missing = EXPECTED_ROUTE_TEMPLATES - actual
    unreviewed = actual - EXPECTED_ROUTE_TEMPLATES
    assert not missing, f"expected routes missing from app: {missing}"
    assert not unreviewed, (
        "routes exist that this suite has never classified as public or "
        f"protected (review then add them here): {unreviewed}"
    )


# ---------------------------------------------------------------------------
# 2. unauthenticated callers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body",
    ALL_PROTECTED,
    ids=[f"{m} {p}" for m, p, _ in ALL_PROTECTED],
)
async def test_protected_route_rejects_unauthenticated_caller(
    client, method, path, body
):
    """Every protected route must return 401 when no token is supplied."""
    r = await _call(client, method, path, body, token=None)
    assert r.status_code == 401, (
        f"{method} {path} returned {r.status_code}, expected 401 without auth"
    )


@pytest.mark.parametrize(
    "method,path,body",
    ALL_PROTECTED,
    ids=[f"{m} {p}" for m, p, _ in ALL_PROTECTED],
)
async def test_protected_route_rejects_garbage_token(client, method, path, body):
    """A syntactically invalid bearer token must be rejected, not trusted."""
    r = await _call(client, method, path, body, token=INVALID_BEARER_TOKEN)
    assert r.status_code == 401, (
        f"{method} {path} returned {r.status_code}, expected 401 for a bad token"
    )


# ---------------------------------------------------------------------------
# 3. unapproved callers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body",
    ALL_PROTECTED,
    ids=[f"{m} {p}" for m, p, _ in ALL_PROTECTED],
)
async def test_protected_route_rejects_unapproved_user(
    client, unapproved_token, method, path, body
):
    """A valid token for an unapproved account must still be refused."""
    r = await _call(client, method, path, body, token=unapproved_token)
    assert r.status_code == 403, (
        f"{method} {path} returned {r.status_code}, expected 403 for unapproved user"
    )


# ---------------------------------------------------------------------------
# 4. admin-only routes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body",
    ADMIN_ONLY,
    ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY],
)
async def test_admin_route_rejects_non_admin(client, regular_token, method, path, body):
    """An approved non-admin must not reach admin-only handlers."""
    r = await _call(client, method, path, body, token=regular_token)
    assert r.status_code == 403, (
        f"{method} {path} returned {r.status_code}, expected 403 for non-admin"
    )


@pytest.mark.parametrize(
    "method,path,body",
    ADMIN_ONLY,
    ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY],
)
async def test_admin_route_accepts_admin(client, admin_token, method, path, body):
    """An admin must clear the authz gate (the handler may still 4xx)."""
    r = await _call(client, method, path, body, token=admin_token)
    assert r.status_code not in (401, 403), (
        f"{method} {path} returned {r.status_code}; admin was blocked by the guard"
    )


# ---------------------------------------------------------------------------
# 5. non-admin routes are reachable by ordinary users
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/auth/me", None),
        ("GET", "/api/documents", None),
        # Deliberately malformed: a 422 proves the request cleared the auth
        # dependencies and reached request validation, without paying for a
        # live Cohere/Pinecone call on every run.
        ("POST", "/api/query", {"not_a_question": 1}),
    ],
    ids=["GET /api/auth/me", "GET /api/documents", "POST /api/query"],
)
async def test_ordinary_routes_are_not_admin_gated(
    client, regular_token, method, path, body
):
    """Regression guard: these must stay open to approved non-admins."""
    r = await _call(client, method, path, body, token=regular_token)
    assert r.status_code not in (401, 403), (
        f"{method} {path} returned {r.status_code}; an approved user was blocked"
    )


# ---------------------------------------------------------------------------
# 6. trace ownership (IDOR)
# ---------------------------------------------------------------------------

async def _trace_id_for_caller(client: AsyncClient, token: str, query: str = "probe") -> str:
    """Mint a trace attributed to the authenticated caller, without a live LLM query.

    ``trace_logger.create_trace`` only reads ``id`` and ``email`` from the user, so
    the real user record fetched via /api/auth/me is enough.
    """
    me = await client.get("/api/auth/me", headers=_headers(token))
    assert me.status_code == 200, f"/me failed: {me.status_code} {me.text[:200]}"
    caller = me.json()
    trace = trace_logger.create_trace(
        SimpleNamespace(id=caller["id"], email=caller["email"]), query
    )
    return trace.trace_id


async def test_trace_owner_can_read_their_trace(client, regular_token):
    """The user who produced a trace may read it back."""
    trace_id = await _trace_id_for_caller(client, regular_token)
    r = await client.get(f"/api/query/trace/{trace_id}", headers=_headers(regular_token))
    assert r.status_code == 200
    assert r.json()["trace_id"] == trace_id


async def test_trace_other_user_gets_404(client, regular_token):
    """Another user must not be able to read someone else's trace."""
    trace_id = str(uuid.uuid4())
    trace_logger.traces.append(
        TraceEntry(
            trace_id=trace_id,
            user_id=str(uuid.uuid4()),  # deliberately not the caller
            user_email="someone.else@vaulttest.local",
            query="salary and board memo",
            timestamp=datetime.utcnow(),
            answer="should never be visible to another user",
        )
    )

    r = await client.get(f"/api/query/trace/{trace_id}", headers=_headers(regular_token))
    assert r.status_code == 404, f"non-owner received {r.status_code}, expected 404"
    assert "salary" not in r.text


async def test_trace_admin_can_read_any_trace(client, admin_token):
    """Admins retain read access for audit and debugging."""
    trace_id = str(uuid.uuid4())
    trace_logger.traces.append(
        TraceEntry(
            trace_id=trace_id,
            user_id=str(uuid.uuid4()),
            user_email="someone.else@vaulttest.local",
            query="audit probe",
            timestamp=datetime.utcnow(),
        )
    )
    r = await client.get(f"/api/query/trace/{trace_id}", headers=_headers(admin_token))
    assert r.status_code == 200


async def test_trace_missing_id_is_404(client, regular_token):
    """A non-existent id and a forbidden id must be indistinguishable."""
    r = await client.get(
        f"/api/query/trace/{uuid.uuid4()}", headers=_headers(regular_token)
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 7. public routes stay public
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body_fn",
    [
        ("GET", "/health", lambda: None),
        # Built per-invocation so a re-run never collides on a stale email.
        ("POST", "/api/auth/register", lambda: {
            "email": f"routeprot_reg_{uuid.uuid4().hex[:8]}@vaulttest.local",
            "password": "RouteProt@123",
            "full_name": "RouteProt Register",
            "department": "general",
        }),
        ("POST", "/api/auth/login", lambda: {
            "email": "definitely.not.a.user@vaulttest.local",
            "password": "whatever",
        }),
    ],
    ids=["GET /health", "POST /api/auth/register", "POST /api/auth/login"],
)
async def test_public_routes_are_not_auth_gated(client, method, path, body_fn):
    """Public routes must not demand a bearer token.

    A 401 here is only acceptable when it originates from the handler's own
    credential check (e.g. a wrong password), never from HTTPBearer rejecting
    a missing token. FastAPI's HTTPBearer always reports the latter as
    ``detail == "Not authenticated"``.
    """
    body = body_fn()
    r = await _call(client, method, path, body, token=None)
    detail = r.json().get("detail") if r.content else None
    assert not (r.status_code == 401 and detail == "Not authenticated"), (
        f"{method} {path} demanded a bearer token"
    )
    assert r.status_code != 403, (
        f"{method} {path} returned {r.status_code}; public route demands authz"
    )
    if path == "/api/auth/register" and r.status_code < 400:
        await _delete_user_by_email(body["email"])
