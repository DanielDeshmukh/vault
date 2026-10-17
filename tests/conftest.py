"""Bootstrap the database the suites assume.

CI starts from an empty postgres -- no schema, no roles, no corpus -- while a
developer machine runs against the loaded corpus. This session fixture closes
the gap without ever touching a populated database:

* ``create_all`` is idempotent and writes the same schema the ingest scripts do;
* the 12 roles (4 tier + 8 corpus) are inserted if missing. Registration is
  hard-wired to ``DEFAULT_PENDING_ROLE = "intern"`` (app/auth/router.py) and
  answers 500 when that row is absent, which is how 23 tests failed;
* fixture documents are inserted **only when the documents table is empty**, so
  a local run against the real corpus never gets synthetic rows.

The fixture corpus is shaped by what the tests assert:

* 30 rows -- ``test_pages_partition_the_result_set`` needs ``total >= 20``;
* classification ``internal`` and ``restricted`` both present, as
  ``test_classification_filter_narrows_the_corpus`` requires both to be > 0;
* 12 documents whose ``allowed_roles`` contains ``"intern"`` -- listing
  visibility for a non-admin is purely ``allowed_roles`` overlap, so the
  scoped-role test and the pending-user test need an ``intern`` slice, and the
  pending test additionally asserts every row it sees carries ``"intern"``;
* three title/content groups so a full-text term can narrow a non-empty strict
  subset (``test_a_real_term_narrows_the_corpus``).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from scripts.seed_local import ROLES

# (title stem, classification, allowed_roles, access_level, count, body text)
_FIXTURE_GROUPS = (
    (
        "Employee Handbook",
        "internal",
        ["intern", "employee"],
        1,
        12,
        "Attendance, leave and workplace policy for salaried staff.",
    ),
    (
        "Vendor Contract",
        "restricted",
        ["manager", "legal"],
        3,
        9,
        "Renewal schedule, payment terms and liability clauses.",
    ),
    (
        "Information Security Policy",
        "internal",
        ["engineer", "hr"],
        1,
        9,
        "Incident response procedure and access review policy.",
    ),
)

_BASE_TIME = datetime(2026, 1, 1)


def _fixture_documents():
    """Build the synthetic corpus in a fixed order.

    ``created_at`` is pinned per row: the listing orders by
    ``created_at DESC, id DESC``, and a random UUID tiebreak would make
    "take the first page and search a term from it" non-deterministic.
    """
    from app.db.models import Document

    docs = []
    index = 0
    for stem, classification, roles, level, count, body in _FIXTURE_GROUPS:
        for n in range(count):
            docs.append(
                Document(
                    doc_id=f"fixture-{index:03d}",
                    title=f"{stem} {n + 1:02d}",
                    content=f"{stem}: {body} Section {n + 1} of {count}.",
                    source="fixture",
                    account_id="test",
                    department="general",
                    access_level=level,
                    classification=classification,
                    allowed_roles=list(roles),
                    doc_metadata={},
                    created_at=_BASE_TIME + timedelta(days=index),
                )
            )
            index += 1
    return docs


@pytest.fixture(scope="session", autouse=True)
async def bootstrap_database():
    """Schema + roles always; fixture documents only into an empty corpus."""
    from sqlalchemy import delete

    from app.db.models import Document, Role
    from app.db.sessions import Base, async_session, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        added_roles = 0
        for spec in ROLES:
            exists = await db.scalar(select(Role.id).where(Role.name == spec["name"]))
            if exists is None:
                db.add(Role(**spec))
                added_roles += 1

        doc_count = (await db.execute(select(func.count(Document.id)))).scalar_one()
        added_docs = 0
        if doc_count == 0:
            for doc in _fixture_documents():
                db.add(doc)
                added_docs += 1

        await db.commit()

    print(
        f"\n[bootstrap] schema created; roles +{added_roles}; "
        f"documents {'+' + str(added_docs) + ' (fixture corpus)' if added_docs else 'existing corpus left untouched'}"
    )

    yield

    # Fixture rows live for the whole session (module-scoped fixtures and the
    # paging tests read them across modules); they only ever exist in a
    # database that was empty at session start, so removing them restores the
    # pre-test state exactly.
    if added_docs:
        async with async_session() as db:
            await db.execute(
                delete(Document).where(Document.doc_id.like("fixture-%"))
            )
            await db.commit()
