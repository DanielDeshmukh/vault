from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.router import api_router
from app.config import settings
from app.db.sessions import Base, async_session, engine

app = FastAPI(
    title=settings.APP_NAME,
    description="Permission-Aware Enterprise Knowledge System",
    version="0.1.0",
    redirect_slashes=False,
)

# CORS: exact origins only -- Starlette allow_origins does not glob, so the
# old "https://*.vercel.app" entry never matched any deployment.
CORS_ORIGINS = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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

    from sqlalchemy import func

    from app.db.models import User
    async with async_session() as session:
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        if not user_count or user_count == 0:
            import logging
            logging.warning("No users found. Run: cd server && python -m scripts.seed_local")

    # Ensure the Pinecone index exists with the configured embedding
    # dimension. An index whose dimension differs from EMBED_DIM returns
    # garbage retrieval, so a mismatch aborts startup instead of being
    # swallowed like the old blanket try/except did.
    import logging

    from app.db.pinecone import pinecone_client
    try:
        existing = [idx.name for idx in pinecone_client.client.list_indexes()]
        if settings.PINECONE_INDEX_NAME not in existing:
            await pinecone_client.create_index(dimension=settings.EMBED_DIM)
        else:
            desc = pinecone_client.client.describe_index(settings.PINECONE_INDEX_NAME)
            actual = getattr(desc, "dimension", None)
            if actual != settings.EMBED_DIM:
                raise RuntimeError(
                    f"Pinecone index {settings.PINECONE_INDEX_NAME!r} has dimension "
                    f"{actual!r} but EMBED_DIM={settings.EMBED_DIM}; refusing to start "
                    "with a mismatched index (recreate it or set EMBED_DIM to match)"
                )
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - infra absence (no key/network) warns only
        logging.warning("Pinecone startup check skipped: %s", exc)


@app.get("/health")
@app.get("/api/health")
async def health():
    """Liveness probe.

    Both paths are registered on purpose: locally ``test_api.py`` hits the bare
    ``/health`` against uvicorn, but Vercel only routes ``/api/*`` (plus an
    explicit ``/health`` entry in vercel.json) into this function, so a single
    route leaves one of the two environments answering 404.
    """
    return {"status": "healthy", "app": settings.APP_NAME}
