from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Convert postgresql:// to postgresql+asyncpg:// for async driver
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Strip sslmode query param (asyncpg doesn't support it; handled via connect_args)
parsed = urlparse(_db_url)
qs = parse_qs(parsed.query)
qs.pop("sslmode", None)
_db_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

_connect_args = {}
if "sslmode" in (settings.DATABASE_URL or ""):
    _connect_args["ssl"] = ssl.create_default_context()

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    future=True,
    connect_args=_connect_args,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
