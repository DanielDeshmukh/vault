from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.auth.jwt import get_current_user
from app.db.models import User
from app.db.sessions import async_session
from app.retrieval.search import HybridSearch
from app.retrieval.generator import CitationGenerator
from app.tracing.logger import trace_logger

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    context: Optional[str] = None


class Citation(BaseModel):
    document_id: str
    title: str
    source: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str


@router.post("/", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Query the knowledge base with permission-aware retrieval.
    
    This endpoint:
    1. Authenticates the user
    2. Builds permission filter (pre-retrieval)
    3. Searches with hybrid vector + keyword
    4. Reranks with Cohere
    5. Generates cited answer with Groq
    6. Logs full trace for audit
    """
    # Create trace
    trace = trace_logger.create_trace(current_user, request.question)
    
    try:
        start_time = datetime.utcnow()
        
        # Initialize components
        search = HybridSearch()
        generator = CitationGenerator()
        
        # Execute permission-aware search
        results = await search.search(
            query=request.question,
            user=current_user,
            top_k=5,
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
            results=results
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
        
    except Exception as e:
        trace_logger.log_error(trace, str(e))
        raise


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get trace details for debugging."""
    trace = trace_logger.get_trace(trace_id)
    if not trace:
        return {"error": "Trace not found"}
    
    return trace_logger.to_dict(trace)
