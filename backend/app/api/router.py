from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.api.queries import router as queries_router
from app.api.documents import router as documents_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(queries_router, prefix="/query", tags=["queries"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
