from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://vault:vault@localhost:5432/vault"
    
    # Pinecone
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "vault"
    PINECONE_INDEX_HOST: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"
    
    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-70b-8192"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Cohere
    COHERE_API_KEY: str = ""
    COHERE_MODEL: str = "rerank-english-v3.0"
    
    # JWT
    JWT_SECRET_KEY: str = "supersecretkey123"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    
    # App
    APP_NAME: str = "Vault"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
