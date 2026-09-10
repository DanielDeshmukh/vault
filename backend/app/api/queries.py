from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.auth.jwt import get_current_user
from app.db.models import User

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
    # Phase 3: Implement full query pipeline
    return QueryResponse(
        answer="This endpoint will be implemented in Phase 3.",
        citations=[],
        trace_id="placeholder"
    )
