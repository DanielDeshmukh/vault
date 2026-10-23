import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

    PINECONE_API_KEY: str = os.environ.get("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.environ.get("PINECONE_INDEX_NAME", "vault")
    PINECONE_INDEX_HOST: str = os.environ.get("PINECONE_INDEX_HOST", "")
    PINECONE_ENVIRONMENT: str = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")

    # Retrieval namespace inside PINECONE_INDEX_NAME. "" (default) is the
    # legacy corpus that production still queries -- the rollout switch.
    # Staging/Phase 6 points this at "v2"; production is NOT switched until
    # Phase 6 passes and the switch is explicitly approved.
    PINECONE_NAMESPACE: str = os.environ.get("PINECONE_NAMESPACE", "")

    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "embed-english-v3.0")

    COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
    COHERE_MODEL: str = os.environ.get("COHERE_MODEL", "rerank-english-v3.0")
    COHERE_EMBED_MODEL: str = os.environ.get("COHERE_EMBED_MODEL", "embed-english-v3.0")
    COHERE_CHAT_MODEL: str = os.environ.get("COHERE_CHAT_MODEL", "command-a-03-2025")

    # No-relevant-answer gate (plan decision locked at CP3): when the top
    # rerank relevance score is below this, answer with an explicit
    # "nothing relevant found" instead of stretching weak chunks into a
    # confident reply. Applies to Cohere rerank scores only (0..1); the
    # vector-score fallback path is a different scale and is not gated.
    # Phase 6 tuning (30 answerable / 15 unanswerable on namespace v2):
    # at T=0.19 all 15 unanswerables stay below the floor (FP=0, margin
    # 0.12 over the worst unanswerable) while refusing only the two
    # statute-snippet queries Cohere scores at ~0.00-0.01; the old 0.4
    # refused four answerables (0.0042-0.3591) for no safety gain.
    RERANK_NO_ANSWER_THRESHOLD: float = float(
        os.environ.get("RERANK_NO_ANSWER_THRESHOLD", "0.19")
    )

    # Embeddings moved off Cohere (trial quota exhausted) onto NVIDIA NIM.
    # app.embeddings is the only module that may use these keys.
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    NVIDIA_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")

    # Embedding dimension. NIM nemotron-3-embed-1b accepts only 2048, and a
    # Pinecone index created with any other dimension silently returns
    # garbage retrieval, so startup verifies the live index against this.
    EMBED_DIM: int = int(os.environ.get("EMBED_DIM", "2048"))

    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES: int = int(os.environ.get("JWT_EXPIRATION_MINUTES", "60"))

    APP_NAME: str = os.environ.get("APP_NAME", "Vault")
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    # Comma-separated exact origins for CORSMiddleware. Starlette's
    # allow_origins does exact string matching only -- a "https://*.vercel.app"
    # entry never matches, so the default pins the production domain.
    CORS_ORIGINS: str = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,https://vault-rbac-rag.vercel.app",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
