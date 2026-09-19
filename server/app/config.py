import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

    PINECONE_API_KEY: str = os.environ.get("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.environ.get("PINECONE_INDEX_NAME", "vault")
    PINECONE_INDEX_HOST: str = os.environ.get("PINECONE_INDEX_HOST", "")
    PINECONE_ENVIRONMENT: str = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")

    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "embed-english-v3.0")

    COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
    COHERE_MODEL: str = os.environ.get("COHERE_MODEL", "rerank-english-v3.0")
    COHERE_EMBED_MODEL: str = os.environ.get("COHERE_EMBED_MODEL", "embed-english-v3.0")
    COHERE_CHAT_MODEL: str = os.environ.get("COHERE_CHAT_MODEL", "command-a-03-2025")

    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES: int = int(os.environ.get("JWT_EXPIRATION_MINUTES", "60"))

    APP_NAME: str = os.environ.get("APP_NAME", "Vault")
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
