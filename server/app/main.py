from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router
from app.db.sessions import engine, Base, async_session
from sqlalchemy import select


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

    # Seed real-world public documents (runs locally, not on Vercel)
    # On Vercel, data persists in Neon DB from local seed
    # To seed locally: cd backend && python -m scripts.seed_local
    from sqlalchemy import select, func
    from app.db.models import User
    async with async_session() as session:
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        if not user_count or user_count == 0:
            import logging
            logging.warning("No users found. Run: cd backend && python -m scripts.seed_local")

    # Ensure Pinecone index has correct dimension (1024 for Cohere embed-english-v3.0)
    from app.db.pinecone import pinecone_client
    try:
        existing = [idx.name for idx in pinecone_client.client.list_indexes()]
        if settings.PINECONE_INDEX_NAME not in existing:
            await pinecone_client.create_index(dimension=1024)
    except Exception:
        pass


@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/admin/recreate-index")
async def recreate_index():
    """One-time: delete and recreate Pinecone index with correct dimension."""
    from app.db.pinecone import pinecone_client
    try:
        pinecone_client.client.delete_index(settings.PINECONE_INDEX_NAME)
        pinecone_client._index = None
    except Exception:
        pass
    await pinecone_client.create_index(dimension=1024)
    return {"status": "Index recreated with dimension 1024"}
