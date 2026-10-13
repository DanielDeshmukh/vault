import uuid

import pytest

from app.auth.permissions import (
    AccessLevel,
    build_pinecone_filter,
    document_role_names,
    get_question_access_level,
)


class TestAccessLevel:
    """Test AccessLevel enum."""

    def test_access_levels(self):
        """Test all access levels exist."""
        assert AccessLevel.PUBLIC.value == 0
        assert AccessLevel.INTERNAL.value == 1
        assert AccessLevel.CONFIDENTIAL.value == 2
        assert AccessLevel.RESTRICTED.value == 3

    def test_access_level_ordering(self):
        """Test access levels are properly ordered."""
        assert AccessLevel.PUBLIC < AccessLevel.INTERNAL
        assert AccessLevel.INTERNAL < AccessLevel.CONFIDENTIAL
        assert AccessLevel.CONFIDENTIAL < AccessLevel.RESTRICTED


class TestBuildPineconeFilter:
    """Test the Pinecone metadata filter that enforces pre-retrieval RBAC."""

    def test_ceiling_filters_higher_levels_out(self):
        """A user ceiling of N must produce access_level <= N."""
        for level in range(4):
            f = build_pinecone_filter(max_access_level=level)
            assert f["access_level"]["$lte"] == level

    def test_public_ceiling_only_sees_public(self):
        """Public users must be restricted to public documents only."""
        f = build_pinecone_filter(max_access_level=0)
        assert f["access_level"]["$lte"] == 0

    def test_admin_style_unrestricted_ceiling(self):
        """Admin ceiling (99) still produces a valid filter expression."""
        f = build_pinecone_filter(max_access_level=99)
        assert f["access_level"]["$lte"] == 99

    def test_account_restriction_adds_condition(self):
        """Providing allowed accounts must add an $in condition."""
        f = build_pinecone_filter(max_access_level=1, allowed_account_ids=["acct-a"])
        assert "$and" in f
        assert {"account_id": {"$in": ["acct-a"]}} in f["$and"]
        assert {"access_level": {"$lte": 1}} in f["$and"]

    def test_role_restriction_adds_condition(self):
        """Providing allowed roles must add an allowed_roles condition."""
        f = build_pinecone_filter(max_access_level=2, allowed_role_names=["hr"])
        assert "$and" in f
        assert {"allowed_roles": {"$in": ["hr"]}} in f["$and"]

    def test_single_condition_is_not_wrapped(self):
        """With only a ceiling, the filter must be the bare condition (Pinecone syntax)."""
        f = build_pinecone_filter(max_access_level=1, allowed_account_ids=[], allowed_role_names=[])
        assert f == {"access_level": {"$lte": 1}}

    def test_defaults_to_public_when_unspecified(self):
        """No ceiling specified must default to the public level, never open access."""
        f = build_pinecone_filter()
        assert f["access_level"]["$lte"] == 0

    def test_public_user_filter_restricts_to_public_level_only(self):
        """Public users must not see internal, confidential, or restricted content."""
        f = build_pinecone_filter(
            max_access_level=0,
            allowed_account_ids=[],
            allowed_role_names=[],
            user_id="public-user-id",
        )
        assert f["access_level"]["$lte"] == 0


class TestQuestionAccessLevel:
    """Test the question-side guard that classifies required access level."""

    def test_plain_question_is_public(self):
        """Ordinary policy questions map to the public level."""
        assert get_question_access_level("Can I take time off after my kid is born?") == 0

    def test_nist_question_is_confidential(self):
        """NIST/security-framework questions must require above-public access."""
        assert get_question_access_level("What is the NIST Cybersecurity Framework?") >= 2

    def test_restricted_keywords_map_high(self):
        """Board/executive/payroll questions must map to restricted."""
        assert get_question_access_level("Show me the board executive memo") == 3
        assert get_question_access_level("What is the CEO payroll?") == 3

    def test_internal_keywords(self):
        """Internal handbook questions must map above public."""
        assert get_question_access_level("What does the engineering handbook say?") >= 1

    def test_empty_question_is_public(self):
        """Empty input must not escalate access."""
        assert get_question_access_level("") == 0


class TestPermissionFilterWithFakeDB:
    """Test PermissionFilter.build_filter without a live database."""

    @pytest.mark.asyncio
    async def test_admin_gets_none_filter(self):
        from app.retrieval.permission_filter import PermissionFilter

        class FakeUser:
            id = "admin-1"
            is_admin = True

        class FakeDB:
            async def execute(self, _stmt):  # pragma: no cover - admin short-circuits
                raise AssertionError("admin path must not query the database")

        pf = PermissionFilter(FakeDB())
        assert await pf.build_filter(FakeUser()) is None

    @pytest.mark.asyncio
    async def test_regular_user_gets_role_filter(self):
        from app.retrieval.permission_filter import PermissionFilter

        class FakeResult:
            def __init__(self, values):
                self._values = values

            def scalars(self):
                return self

            def all(self):
                return self._values

        class FakeDB:
            async def execute(self, _stmt):
                return FakeResult(["engineer"])

        class FakeUser:
            id = "user-1"
            is_admin = False

        pf = PermissionFilter(FakeDB())
        f = await pf.build_filter(FakeUser())

        assert f == {"allowed_roles": {"$in": ["engineer"]}}

    @pytest.mark.asyncio
    async def test_no_roles_denies_all(self):
        """A user with no roles must match nothing, not fall back to public."""
        from app.retrieval.permission_filter import PermissionFilter

        class FakeResult:
            def scalars(self):
                return self

            def all(self):
                return []

        class FakeDB:
            async def execute(self, _stmt):
                return FakeResult()

        class FakeUser:
            id = "user-2"
            is_admin = False

        pf = PermissionFilter(FakeDB())
        f = await pf.build_filter(FakeUser())

        assert f == {"allowed_roles": {"$in": ["__vault_deny_all__"]}}

    @pytest.mark.asyncio
    async def test_filter_does_not_force_owner_only_access(self):
        """Regular users must not be restricted to only their own owned documents."""
        from app.retrieval.permission_filter import PermissionFilter

        class FakeResult:
            def scalars(self):
                return self

            def all(self):
                return ["employee"]

        class FakeDB:
            async def execute(self, _stmt):
                return FakeResult()

        class FakeUser:
            id = "user-123"
            is_admin = False

        pf = PermissionFilter(FakeDB())
        f = await pf.build_filter(FakeUser())

        assert f is not None
        assert "owner_id" not in str(f)

    @pytest.mark.asyncio
    async def test_role_names_are_lowercased(self):
        """A legacy tier role like 'Internal' must still match a corpus ACL."""
        from app.retrieval.permission_filter import PermissionFilter

        class FakeResult:
            def scalars(self):
                return self

            def all(self):
                return ["Internal"]

        class FakeDB:
            async def execute(self, _stmt):
                return FakeResult()

        class FakeUser:
            id = "user-124"
            is_admin = False

        pf = PermissionFilter(FakeDB())
        assert await pf.build_filter(FakeUser()) == {"allowed_roles": {"$in": ["internal"]}}


def test_expand_query_handles_topic_hints_without_crashing():
    """Query expansion should turn list hints into a single string."""
    from app.retrieval.search import expand_query

    variants = expand_query("What are the paid vacation leave policies?")

    assert variants
    assert isinstance(variants[0], str)
    assert any("vacation" in variant.lower() for variant in variants)


def _make_document(allowed_roles, access_level=2):
    from app.db.models import Document

    return Document(
        id=uuid.uuid4(),
        title="Acme contract",
        content="terms",
        source="txt",
        access_level=access_level,
        allowed_roles=allowed_roles,
    )


class TestDocumentAclSerialization:
    """The response must expose the same ACL the pre-retrieval filter enforces."""

    def test_roles_are_lowercased_and_deduplicated(self):
        assert document_role_names(_make_document(["HR", "engineer", "hr"])) == {
            "hr",
            "engineer",
        }

    def test_null_acl_means_nobody(self):
        """NULL must read as 'no roles', never as 'everyone'."""
        assert document_role_names(_make_document(None)) == set()

    def test_double_encoded_json_means_nobody(self):
        """A JSON-stringified array is malformed and must not grant access.

        Regression guard: the corpus ingest once wrote every row's ACL as a
        double-encoded string, which silently widened access.
        """
        assert document_role_names(_make_document('["hr", "legal"]')) == set()

    def test_response_carries_sorted_roles(self):
        from app.api.documents import DocumentResponse

        doc = _make_document(["finance", "hr"])
        resp = DocumentResponse(
            id=str(doc.id),
            title=doc.title,
            source=doc.source,
            access_level=doc.access_level,
            allowed_roles=sorted(document_role_names(doc)),
        )
        assert resp.allowed_roles == ["finance", "hr"]

    def test_response_defaults_to_empty_roles(self):
        from app.api.documents import DocumentResponse

        resp = DocumentResponse(id="x", title="t", source="txt", access_level=1)
        assert resp.allowed_roles == []
