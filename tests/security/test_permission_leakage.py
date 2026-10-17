import os

import pytest
from datetime import datetime

from eval.golden_set import get_golden_set_by_category, QuestionCategory
from eval.evaluator import Evaluator, EvalConfig
from app.db.models import User, Role, UserRole, Document, DocumentAccess
from app.db.sessions import async_session
from app.auth.jwt import get_password_hash
from app.retrieval.permission_filter import PermissionFilter

# Retrieval + generation runs against live Pinecone, Cohere and NVIDIA NIM.
# CI has no secrets, and these tests deliberately fail on infrastructure
# errors rather than passing vacuously -- so without the keys they must skip,
# not fail. Everything else in this file is DB/logic only and always runs.
needs_live_services = pytest.mark.skipif(
    not all(os.environ.get(k) for k in ("PINECONE_API_KEY", "COHERE_API_KEY", "NVIDIA_API_KEY")),
    reason="live retrieval+generation: set PINECONE_API_KEY, COHERE_API_KEY, NVIDIA_API_KEY",
)


@pytest.fixture
async def test_user():
    """Create a test user with limited permissions."""
    async with async_session() as db:
        # Create user
        user = User(
            email="test@vault.com",
            hashed_password=get_password_hash("testpassword"),
            full_name="Test User",
            department="support",
            is_admin=False,
        )
        db.add(user)
        await db.flush()
        
        # Create role
        role = Role(
            name="Support Agent",
            description="Support team member",
            access_level=1,  # Internal
        )
        db.add(role)
        await db.flush()
        
        # Assign role
        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.add(user_role)
        
        await db.commit()
        await db.refresh(user)
        
        yield user
        
        # Cleanup
        await db.delete(user_role)
        await db.delete(role)
        await db.delete(user)
        await db.commit()


@pytest.fixture
async def restricted_document(test_user):
    """Create a document that the test user should NOT access."""
    async with async_session() as db:
        doc = Document(
            title="Executive Notes - Beta Corp",
            content="Confidential executive notes about Beta Corp acquisition",
            source="policy",
            source_id="exec-beta-001",
            account_id="beta-corp",
            department="executive",
            access_level=3,  # Restricted
            owner_id=None,
            doc_metadata={"allowed_roles": ["executive", "board"]},
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        yield doc
        
        # Cleanup
        await db.delete(doc)
        await db.commit()


@pytest.fixture
async def accessible_document(test_user):
    """Create a document that the test user SHOULD access."""
    async with async_session() as db:
        doc = Document(
            title="Support FAQ",
            content="Frequently asked questions for support team",
            source="policy",
            source_id="support-faq-001",
            account_id="internal",
            department="support",
            access_level=1,  # Internal
            owner_id=test_user.id,
            doc_metadata={"allowed_roles": ["support"]},
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        yield doc
        
        # Cleanup
        await db.delete(doc)
        await db.commit()


class TestPermissionFilter:
    """Test permission filter logic."""
    
    @pytest.mark.asyncio
    async def test_admin_gets_no_filter(self, test_user):
        """Admin users should get no filter (full access)."""
        test_user.is_admin = True
        
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(test_user)
            
            assert filter_dict is None
    
    @pytest.mark.asyncio
    async def test_regular_user_gets_filter(self, test_user):
        """Regular users should get a permission filter."""
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(test_user)
            
            assert filter_dict is not None
            # A non-admin must always be constrained by an allowed_roles list
            assert "allowed_roles" in filter_dict
            assert "$in" in filter_dict["allowed_roles"]
    
    @pytest.mark.asyncio
    async def test_filter_enforces_allowed_roles(self, test_user):
        """Filter should constrain retrieval to the caller's own roles."""
        async with async_session() as db:
            perm_filter = PermissionFilter(db)
            filter_dict = await perm_filter.build_filter(test_user)
            
            assert filter_dict is not None
            
            # test_user holds only the "Support Agent" role
            roles = filter_dict["allowed_roles"]["$in"]
            assert isinstance(roles, list)
            assert roles == ["support agent"]


def test_query_model_loads_and_classifies_high_level_question():
    """The query schema should load and high-level questions should map above public access."""
    from app.api.queries import QueryRequest
    from app.auth.permissions import get_question_access_level

    req = QueryRequest(question="What is the NIST Cybersecurity Framework?")
    assert req.question == "What is the NIST Cybersecurity Framework?"
    assert get_question_access_level(req.question) > 0


@pytest.mark.asyncio
async def test_permission_filter_does_not_force_owner_only_access():
    """Regular users must not be restricted to only their own owned documents."""
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
            return FakeResult([])

    class FakeUser:
        id = "user-123"
        is_admin = False

    perm_filter = PermissionFilter(FakeDB())
    filter_dict = await perm_filter.build_filter(FakeUser())

    assert filter_dict is not None
    assert "owner_id" not in str(filter_dict)


class TestPermissionBoundary:
    """Test permission boundary enforcement."""
    
    @needs_live_services
    @pytest.mark.asyncio
    async def test_permission_boundary_questions(self, test_user):
        """
        CRITICAL TEST: Permission boundary questions should be refused.
        
        This test verifies that the system refuses to answer questions
        about restricted content.
        """
        # Get permission boundary questions
        pb_questions = get_golden_set_by_category(QuestionCategory.PERMISSION_BOUNDARY)
        
        evaluator = Evaluator(EvalConfig(top_k=5, use_reranker=False))
        
        for question in pb_questions:
            result = await evaluator.evaluate_question(test_user, question)
            
            # An infrastructure failure (e.g. LLM rate limit) is NOT a pass:
            # we must actually exercise retrieval + generation to verify security.
            assert not result.error, (
                f"evaluation of {question.id} failed infrastructure check: {result.error[:200]}"
            )
            
            # For permission boundary questions, the system should either:
            # 1. Refuse to answer, or
            # 2. Only cite authorized sources
            
            if question.should_refuse:
                # Check that the answer is a refusal or only authorized
                assert result.did_refuse or await self._only_authorized_sources(
                    result.citations, test_user
                ), f"Question {question.id} leaked unauthorized content"
    
    @needs_live_services
    @pytest.mark.asyncio
    async def test_no_unauthorized_chunk_leakage(self, test_user, restricted_document):
        """
        CRITICAL TEST: Zero unauthorized chunk leakage.
        
        This test verifies that unauthorized chunks never reach the model.
        """
        # Query for restricted content
        query = f"Tell me about {restricted_document.title}"
        
        evaluator = Evaluator(EvalConfig(top_k=5, use_reranker=False))
        
        # Create a mock question
        from eval.golden_set import GoldenQuestion
        test_question = GoldenQuestion(
            id="SEC-001",
            question=query,
            category=QuestionCategory.PERMISSION_BOUNDARY,
            should_refuse=True,
        )
        
        result = await evaluator.evaluate_question(test_user, test_question)
        
        # Fail loudly on infrastructure errors instead of passing vacuously
        assert not result.error, (
            f"evaluation failed infrastructure check (no retrieval exercised): {result.error[:200]}"
        )
        
        # Verify the restricted document was not retrieved
        restricted_id = str(restricted_document.id)
        
        for citation in result.citations:
            assert citation.get("document_id") != restricted_id, \
                f"Restricted document {restricted_id} was retrieved!"
    
    async def _only_authorized_sources(self, citations: list[dict], user: User) -> bool:
        """Check every citation against the user's effective access ceiling."""
        from sqlalchemy import select

        from app.auth.permissions import get_user_max_access_level
        from app.db.models import Document
        from app.db.sessions import async_session

        async with async_session() as db:
            max_level = await get_user_max_access_level(user, db)
            for citation in citations:
                doc_id = citation.get("document_id")
                if not doc_id:
                    continue
                result = await db.execute(select(Document).where(Document.id == doc_id))
                document = result.scalar_one_or_none()
                if document is not None and document.access_level > max_level:
                    return False
        return True


class TestZeroLeakage:
    """
    CRITICAL TEST SUITE: Zero unauthorized leakage.
    
    This test suite verifies that the system never leaks unauthorized content.
    The target is 0.0 unauthorized leakage rate.
    """
    
    @needs_live_services
    @pytest.mark.asyncio
    async def test_zero_leakage_across_all_categories(self, test_user):
        """
        Verify zero leakage across all question categories.
        
        This is the non-negotiable metric:
        Unauthorized Leakage Rate MUST be 0.0
        """
        evaluator = Evaluator(EvalConfig(top_k=5, use_reranker=False))
        
        # Run a subset of questions from each category
        categories_to_test = [
            QuestionCategory.EASY_LOOKUP,
            QuestionCategory.CROSS_DOC_SYNTHESIS,
            QuestionCategory.PERMISSION_BOUNDARY,
        ]
        
        total_queries = 0
        total_leaks = 0
        infra_errors = []
        
        for category in categories_to_test:
            questions = get_golden_set_by_category(category)[:3]  # Test 3 per category
            
            for question in questions:
                result = await evaluator.evaluate_question(test_user, question)
                total_queries += 1
                
                # Infrastructure failures must fail the test, not count as "no leak"
                if result.error:
                    infra_errors.append(f"{question.id}: {result.error[:120]}")
                
                # Check for leaks
                if result.security_metrics.total_leaks > 0:
                    total_leaks += result.security_metrics.total_leaks
        
        assert not infra_errors, (
            f"{len(infra_errors)}/{total_queries} evaluations hit infrastructure errors "
            f"(leakage NOT verified): {infra_errors[:3]}"
        )
        
        # ZERO TOLERANCE: No leaks allowed
        assert total_leaks == 0, \
            f"CRITICAL FAILURE: {total_leaks} unauthorized leaks detected!"
        
        # Log success
        print(f"\n✓ Zero leakage verified across {total_queries} queries")


class TestGoldenSetCoverage:
    """Test that the golden set provides adequate coverage."""
    
    def test_golden_set_has_all_categories(self):
        """Verify golden set covers all required categories."""
        from eval.golden_set import get_golden_set
        
        golden_set = get_golden_set()
        
        categories = set(q.category for q in golden_set)
        
        assert QuestionCategory.EASY_LOOKUP in categories
        assert QuestionCategory.CROSS_DOC_SYNTHESIS in categories
        assert QuestionCategory.CONFLICTING_SOURCES in categories
        assert QuestionCategory.STALE_INFO in categories
        assert QuestionCategory.PERMISSION_BOUNDARY in categories
        assert QuestionCategory.EDGE_CASE in categories
    
    def test_golden_set_has_50_questions(self):
        """Verify golden set has exactly 50 questions."""
        from eval.golden_set import get_golden_set
        
        golden_set = get_golden_set()
        
        assert len(golden_set) == 50, f"Expected 50 questions, got {len(golden_set)}"
    
    def test_golden_set_has_permission_questions(self):
        """Verify golden set has permission boundary questions."""
        from eval.golden_set import get_golden_set
        
        golden_set = get_golden_set()
        
        pb_questions = [q for q in golden_set if q.category == QuestionCategory.PERMISSION_BOUNDARY]
        
        assert len(pb_questions) >= 10, \
            f"Expected at least 10 permission questions, got {len(pb_questions)}"
