import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://vault:vault@localhost:5432/vault"

    PINECONE_API_KEY: str = "pcsk_51kowd_4vknyxyhZbVj3mucgEqNDouayNhMSnbWWzdsy4cNtU4jH1DXGAmz6wewEPsG7jV"
    PINECONE_INDEX_NAME: str = "vault"
    PINECONE_INDEX_HOST: str = "vault-i2m1jrk.svc.aped-4627-b74a.pinecone.io"
    PINECONE_ENVIRONMENT: str = "us-east-1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    EMBEDDING_MODEL: str = "embed-english-v3.0"

    COHERE_API_KEY: str = "cohere_3JyLroF1j12Qu0aCjaRMwEKGLvIGv9e65tPgogUt4AIwff"
    COHERE_MODEL: str = "rerank-english-v3.0"
    COHERE_EMBED_MODEL: str = "embed-english-v3.0"
    COHERE_CHAT_MODEL: str = "command-a-03-2025"

    JWT_SECRET_KEY: str = "1_XAHlEmDaXu_shIbHexlNzNIG7p0CUf8vTiW4ea8zjek8_ZwVOvbtIezh-O96Ian5Wiu7h2zsJuAxMpXX981A"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    APP_NAME: str = "Vault"
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
