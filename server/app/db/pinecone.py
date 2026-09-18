import os
from pinecone import Pinecone, ServerlessSpec
from typing import Optional


class PineconeClient:
    """Pinecone vector database client."""

    def __init__(self):
        self._client: Optional[Pinecone] = None
        self._index = None

    def _get_api_key(self):
        return os.environ.get("PINECONE_API_KEY", "")

    def _get_index_name(self):
        return os.environ.get("PINECONE_INDEX_NAME", "vault")

    def _get_index_host(self):
        return os.environ.get("PINECONE_INDEX_HOST", "")

    def _get_environment(self):
        return os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")

    @property
    def client(self) -> Pinecone:
        api_key = self._get_api_key()
        if self._client is None or self._client._api_key != api_key:
            self._client = Pinecone(api_key=api_key)
        return self._client

    @property
    def index(self):
        host = self._get_index_host()
        index_name = self._get_index_name()
        if self._index is None:
            if host:
                self._index = self.client.Index(index_name, host=host)
            else:
                self._index = self.client.Index(index_name)
        return self._index

    def reset(self):
        self._client = None
        self._index = None

    async def create_index(self, dimension: int = 768):
        existing_indexes = [idx.name for idx in self.client.list_indexes()]
        if self._get_index_name() not in existing_indexes:
            self.client.create_index(
                name=self._get_index_name(),
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self._get_environment()
                )
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
