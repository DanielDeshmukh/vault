import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.jwt import get_current_user
from app.db.models import User
from app.retrieval.generator import CitationGenerator
from app.retrieval.search import HybridSearch
from app.tracing.logger import trace_logger

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    context: str | None = Field(default=None, max_length=6000)


def build_retrieval_query(question: str, conversation_context: str | None) -> str:
    """Keep follow-up retrieval anchored to the current conversation topic."""
    if not conversation_context:
        return question
    return f"{conversation_context}\n\nFollow-up question: {question}"


class Citation(BaseModel):
    document_id: str
    title: str
    source: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Query the knowledge base with permission-aware retrieval.

    This endpoint:
    1. Authenticates the user
    2. Builds permission filter (pre-retrieval)
    3. Searches with vector similarity
    4. Reranks with Cohere
    5. Generates cited answer with Cohere
    6. Logs full trace for audit
    """
    # Create trace
    trace = trace_logger.create_trace(current_user, request.question)

    # Check if user is approved and has a role
    if not current_user.is_admin and not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval. You cannot query documents yet."
        )

    # Access is enforced by the role filter applied inside retrieval
    # (PermissionFilter.build_filter -> {"allowed_roles": {"$in": [...]}}),
    # which runs before any chunk is fetched. There is deliberately no
    # keyword or clearance-tier pre-gate here: gating on question wording
    # both leaks that restricted topics exist and denies legitimate
    # questions whose words happen to overlap a restricted term.
    try:
        start_time = datetime.utcnow()

        # Initialize components
        search = HybridSearch()
        generator = CitationGenerator()

        # Execute permission-aware search
        results = await search.search(
            query=request.question,
            user=current_user,
            top_k=6,
            use_reranker=True
        )

        # Log retrieved chunks
        trace_logger.log_retrieved_chunks(
            trace,
            [
                {
                    "id": r.id,
                    "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                    "score": r.score,
                    "metadata": r.metadata
                }
                for r in results
            ]
        )

        # Generate cited answer
        generated = await generator.generate(
            query=request.question,
            results=results,
            conversation_context=request.context,
        )

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log answer
        trace_logger.log_answer(
            trace,
            generated.answer,
            generated.citations,
            latency_ms
        )

        return QueryResponse(
            answer=generated.answer,
            citations=[
                Citation(
                    document_id=c["document_id"],
                    title=c["title"],
                    source=c["source"],
                    score=c["score"]
                )
                for c in generated.citations
            ],
            trace_id=trace.trace_id
        )

    except HTTPException:
        raise
    except Exception as e:
        trace_logger.log_error(trace, str(e))
        msg = str(e).lower()
        if "429" in msg or "rate" in msg or "too many" in msg:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {str(e)[:300]}"
            )
        if "pinecone" in msg or "vector" in msg:
            raise HTTPException(
                status_code=503,
                detail="Search service temporarily unavailable. Please try again later."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)[:200]}"
        )


@router.post("/stream")
async def query_stream(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """Stream query results as SSE events."""
    trace = trace_logger.create_trace(current_user, request.question)

    if not current_user.is_admin and not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval."
        )

    search = HybridSearch()
    generator = CitationGenerator()

    async def event_generator():
        # Same as the non-streaming path: enforcement lives in the role
        # filter applied by search, so a user with no matching roles simply
        # streams back no sources rather than being rejected up front.
        try:
            results = await search.search(
                query=build_retrieval_query(request.question, request.context),
                user=current_user,
                top_k=8,
                use_reranker=True
            )

            source_list = []
            for r in results:
                source_list.append({
                    "document_id": r.metadata.get("doc_id", r.id),
                    "title": r.metadata.get("source_title", "Untitled"),
                    "source": r.metadata.get("citation",
                                             r.metadata.get("source_file", "unknown")),
                    "score": round(r.score, 4),
                })

            yield f"data: {json.dumps({'type': 'sources', 'sources': source_list})}\n\n"

            full_answer = ""
            async for chunk in generator.generate_stream(
                request.question,
                results,
                conversation_context=request.context,
            ):
                full_answer += chunk
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

            citations = generator.extract_citations(full_answer, results)
            trace_logger.log_answer(trace, full_answer, citations, 0)

            yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'trace_id': trace.trace_id})}\n\n"

        except Exception as e:
            trace_logger.log_error(trace, str(e))
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user)
):
    """Return a trace the caller owns. Admins may read any trace.

    A trace records the caller's question, the retrieved chunks and the
    generated answer, so it is user data. A non-owner receives the same 404
    as a missing id, otherwise the response would confirm which trace ids
    exist and let an attacker enumerate other people's activity.
    """
    trace = trace_logger.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    if trace.user_id != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace_logger.to_dict(trace)
