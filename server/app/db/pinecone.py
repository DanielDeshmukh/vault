from pinecone import Pinecone, ServerlessSpec
from typing import Optional

from app.config import settings


class PineconeClient:
    def __init__(self):
        self._client: Optional[Pinecone] = None
        self._index = None

    @property
    def client(self) -> Pinecone:
        if self._client is None:
            self._client = Pinecone(api_key=settings.PINECONE_API_KEY)
        return self._client

    @property
    def index(self):
        if self._index is None:
            self._index = self.client.Index(settings.PINECONE_INDEX_NAME, host=settings.PINECONE_INDEX_HOST)
        return self._index

    def reset(self):
        self._client = None
        self._index = None

    async def create_index(self, dimension: int = 1024):
        existing_indexes = [idx.name for idx in self.client.list_indexes()]
        if settings.PINECONE_INDEX_NAME not in existing_indexes:
            self.client.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENVIRONMENT)
            )

    async def upsert_vectors(self, vectors: list[dict]):
        self.index.upsert(vectors=vectors)

    async def query_vectors(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: Optional[dict] = None,
        include_metadata: bool = True
    ) -> list[dict]:
        results = self.index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata
        )
        return results.get("matches", [])

    async def delete_vectors(self, ids: list[str]):
        self.index.delete(ids=ids)

    async def delete_by_filter(self, filter: dict):
        self.index.delete(filter=filter)


pinecone_client = PineconeClient()
