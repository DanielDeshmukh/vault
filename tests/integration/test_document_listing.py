"""Pagination, filtering and full-text search for ``GET /api/documents``.

The endpoint used to ``SELECT`` every row. Three properties are easy to get
subtly wrong once it pages, filters and searches, so each gets an explicit
test:

* pages must partition the result set -- no overlap, no gaps, stable totals;
* a classification filter must narrow the ACL rather than replace it, and a
  filter must never surface a document to a caller who could not already see
  it;
* no list response may ever carry ``content`` back -- that column is 94 MB
  across the corpus and is not what a row of results needs.

Asserted against the real corpus, so the checks are written as invariants
(ordering, containment, cardinality) rather than golden counts that would
break on the next re-ingest.
"""

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.jwt import create_access_token, get_password_hash
from app.db.models import Role, User, UserRole
from app.db.sessions import async_session
from app.main import app


@pytest.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_user(tag: str, *, admin: bool, role: str | None) -> tuple[User, str]:
    async with async_session() as db:
        user = User(
            email=f"doclist_{tag}_{uuid.uuid4().hex[:8]}@vaulttest.local",
            hashed_password=get_password_hash("DocList@123"),
            full_name=f"DocList {tag}",
            department="general",
            is_admin=admin,
            is_approved=True,
        )
        db.add(user)
        await db.flush()
        if role is not None:
            role_row = (
                await db.execute(select(Role).where(Role.name == role))
            ).scalar_one()
            db.add(UserRole(user_id=user.id, role_id=role_row.id))
        await db.commit()
        await db.refresh(user)
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return user, token


async def _cleanup(user: User) -> None:
    async with async_session() as db:
        found = (
            await db.execute(select(User).where(User.id == user.id))
        ).scalar_one_or_none()
        if found is None:
            return
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        await db.delete(found)
        await db.commit()


@pytest.fixture(scope="module")
async def admin_token():
    user, token = await _make_user("admin", admin=True, role=None)
    yield token
    await _cleanup(user)


@pytest.fixture(scope="module")
async def role_token():
    """An approved non-admin holding a single, deliberately narrow role."""
    user, token = await _make_user("scoped", admin=False, role="intern")
    yield token
    await _cleanup(user)


@pytest.fixture(scope="module")
async def roleless_token():
    """Approved but holding no roles: deny-by-default must yield nothing."""
    user, token = await _make_user("roleless", admin=False, role=None)
    yield token
    await _cleanup(user)


async def _list(client: AsyncClient, token: str, **params) -> dict:
    r = await client.get(
        "/api/documents",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _ids(page: dict) -> set[str]:
    return {d["id"] for d in page["items"]}


async def test_pages_partition_the_result_set(client, admin_token):
    first = await _list(client, admin_token, limit=10, offset=0)
    second = await _list(client, admin_token, limit=10, offset=10)

    assert len(first["items"]) == 10
    assert len(second["items"]) == 10
    assert first["total"] == second["total"]
    assert first["total"] >= 20
    assert _ids(first).isdisjoint(_ids(second)), "pages overlapped"


async def test_envelope_echoes_the_requested_window(client, admin_token):
    page = await _list(client, admin_token, limit=7, offset=3)
    assert page["limit"] == 7
    assert page["offset"] == 3
    assert len(page["items"]) <= 7


async def test_offset_past_the_end_is_empty_not_an_error(client, admin_token):
    everything = await _list(client, admin_token, limit=1)
    past = await _list(
        client, admin_token, limit=10, offset=everything["total"]
    )
    assert past["items"] == []
    assert past["total"] == everything["total"]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"classification": "top-secret"},
        {"q": "x" * 201},
    ],
)
async def test_out_of_range_paging_and_unknown_filters_are_rejected(
    client, admin_token, params
):
    r = await client.get(
        "/api/documents",
        params=params,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422, r.text


async def test_classification_filter_narrows_the_list(client, admin_token):
    everything = await _list(client, admin_token, limit=1)
    internal = await _list(
        client, admin_token, limit=100, classification="internal"
    )
    restricted = await _list(
        client, admin_token, limit=100, classification="restricted"
    )

    assert internal["total"] > 0, "corpus should contain internal documents"
    assert restricted["total"] > 0, "corpus should contain restricted documents"
    assert internal["total"] + restricted["total"] <= everything["total"]
    assert all(d["classification"] == "internal" for d in internal["items"])
    assert all(d["classification"] == "restricted" for d in restricted["items"])


async def test_filter_is_anded_with_the_acl_not_substituted_for_it(
    client, admin_token, role_token
):
    """A filter may only narrow what the ACL already allows."""
    admin_wide = await _list(client, admin_token, limit=1)
    admin_narrow = await _list(
        client, admin_token, limit=1, classification="restricted"
    )
    user_wide = await _list(client, role_token, limit=1)
    user_narrow = await _list(
        client, role_token, limit=1, classification="restricted"
    )

    assert user_wide["total"] > 0, "scoped role should still see a slice"
    assert user_wide["total"] <= admin_wide["total"]
    assert user_narrow["total"] <= admin_narrow["total"]
    assert user_narrow["total"] <= user_wide["total"]


async def test_roleless_user_sees_nothing_under_every_shape_of_query(
    client, roleless_token
):
    assert (await _list(client, roleless_token, limit=10))["total"] == 0
    assert (
        await _list(
            client, roleless_token, limit=10, classification="internal"
        )
    )["total"] == 0
    assert (
        await _list(client, roleless_token, limit=10, q="policy")
    )["total"] == 0


async def test_a_token_that_cannot_exist_matches_nothing(client, admin_token):
    """Guards against the search silently degrading to "return everything"."""
    page = await _list(client, admin_token, limit=10, q=f"zzqv{uuid.uuid4().hex}")
    assert page["total"] == 0
    assert page["items"] == []

    # ...including when composed with a classification filter.
    composed = await _list(
        client,
        admin_token,
        limit=10,
        classification="internal",
        q=f"zzqv{uuid.uuid4().hex}",
    )
    assert composed["total"] == 0
    assert composed["items"] == []


async def test_a_real_term_narrows_the_corpus(client, admin_token):
    everything = await _list(client, admin_token, limit=1)
    seed = await _list(client, admin_token, limit=10)

    # Titles are file paths and headings, so they carry plenty of distinctive
    # 6+ character tokens. Stopwords ("through", "between") are dropped by
    # websearch_tsquery, hence trying several rather than committing to one.
    candidates = sorted(
        {w for d in seed["items"] for w in re.findall(r"[A-Za-z]{6,}", d["title"])},
        key=len,
        reverse=True,
    )
    assert candidates, "expected a seed title with a usable search term"

    narrowed = [
        (await _list(client, admin_token, limit=10, q=term))["total"]
        for term in candidates[:8]
    ]
    assert any(
        0 < total < everything["total"] for total in narrowed
    ), f"no seed term narrowed the corpus: {narrowed}"


async def test_search_ordering_is_deterministic(client, admin_token):
    term = "policy"
    one = await _list(client, admin_token, limit=20, q=term)
    two = await _list(client, admin_token, limit=20, q=term)
    assert [d["id"] for d in one["items"]] == [d["id"] for d in two["items"]]


async def test_list_responses_never_carry_content(client, admin_token, role_token):
    for token in (admin_token, role_token):
        for params in (
            {"limit": 100},
            {"limit": 100, "classification": "restricted"},
            {"limit": 100, "q": "policy"},
        ):
            page = await _list(client, token, **params)
            for doc in page["items"]:
                assert "content" not in doc, (
                    f"list response leaked content for {doc['title']!r}"
                )
