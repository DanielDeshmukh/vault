import os
from dotenv import load_dotenv


def _load_production_env():
    """Load env.production file (bundled in deployment) to override stale Vercel env vars."""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "env.production"),
        os.path.join(os.getcwd(), "server", "env.production"),
        os.path.join(os.getcwd(), "env.production"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            load_dotenv(p, override=True)
            return p
    return None


_load_production_env()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://vault:vault@localhost:5432/vault"

    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "vault"
    PINECONE_INDEX_HOST: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    EMBEDDING_MODEL: str = "embed-english-v3.0"

    COHERE_API_KEY: str = ""
    COHERE_MODEL: str = "rerank-english-v3.0"
    COHERE_EMBED_MODEL: str = "embed-english-v3.0"
    COHERE_CHAT_MODEL: str = "command-a-03-2025"

    JWT_SECRET_KEY: str = "supersecretkey123"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    APP_NAME: str = "Vault"
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
