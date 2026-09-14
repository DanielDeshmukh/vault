from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router
from app.db.sessions import engine, Base


app = FastAPI(
    title=settings.APP_NAME,
    description="Permission-Aware Enterprise Knowledge System",
    version="0.1.0",
    redirect_slashes=False,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://frontend-eight-theta-77.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def startup():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Recreate Pinecone index with correct dimension (1024 for Cohere embed-english-v3.0)
    from app.db.pinecone import pinecone_client
    try:
        existing = [idx.name for idx in pinecone_client.client.list_indexes()]
        if settings.PINECONE_INDEX_NAME in existing:
            pinecone_client.client.delete_index(settings.PINECONE_INDEX_NAME)
            pinecone_client._index = None
        await pinecone_client.create_index(dimension=1024)
    except Exception:
        pass  # Index creation is best-effort


@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.APP_NAME}
