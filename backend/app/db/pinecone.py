from pinecone import Pinecone, ServerlessSpec
from typing import Optional
from app.config import settings


class PineconeClient:
    """Pinecone vector database client."""
    
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
            host = getattr(settings, "PINECONE_INDEX_HOST", None)
            if host:
                self._index = self.client.Index(settings.PINECONE_INDEX_NAME, host=host)
            else:
                self._index = self.client.Index(settings.PINECONE_INDEX_NAME)
        return self._index
    
    async def create_index(self, dimension: int = 768):
        """Create Pinecone index if it doesn't exist."""
        existing_indexes = [idx.name for idx in self.client.list_indexes()]
        
        if settings.PINECONE_INDEX_NAME not in existing_indexes:
            self.client.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.PINECONE_ENVIRONMENT
                )
            )
    
    async def upsert_vectors(
        self,
        vectors: list[dict]
    ):
        """
        Upsert vectors to Pinecone.
        
        Each vector dict should have:
            - id: Unique vector ID
            - values: Embedding vector
            - metadata: Metadata dict for filtering
        """
        self.index.upsert(vectors=vectors)
    
    async def query_vectors(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: Optional[dict] = None,
        include_metadata: bool = True
    ) -> list[dict]:
        """
        Query vectors from Pinecone.
        
        Args:
            vector: Query embedding vector
            top_k: Number of results to return
            filter: Metadata filter for permission-aware search
            include_metadata: Whether to include metadata in results
            
        Returns:
            List of matching vectors with scores
        """
        results = self.index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata
        )
        
        return results.get("matches", [])
    
    async def delete_vectors(self, ids: list[str]):
        """Delete vectors by ID."""
        self.index.delete(ids=ids)
    
    async def delete_by_filter(self, filter: dict):
        """Delete vectors by metadata filter."""
        self.index.delete(filter=filter)


# Singleton instance
pinecone_client = PineconeClient()
