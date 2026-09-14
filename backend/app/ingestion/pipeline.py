from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.connectors.base import BaseConnector, RawDocument, DocumentMetadata, SourceType
from app.ingestion.parsers.router import ParserRouter
from app.ingestion.chunker import SemanticChunker, Chunk
from app.ingestion.metadata import MetadataEnricher
from app.db.models import Document, DocumentChunk
from app.db.pinecone import pinecone_client


async def _get_embedding(text: str) -> list[float]:
    """Get embedding vector for text using Cohere."""
    import cohere
    from app.config import settings

    client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    response = client.embed(
        texts=[text],
        model=settings.COHERE_EMBED_MODEL,
        input_type="search_document",
    )
    return response.embeddings[0]


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    documents_processed: int
    chunks_created: int
    errors: list[str]


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline."""
    
    def __init__(self):
        self.parsers = ParserRouter()
        self.chunker = SemanticChunker()
        self.metadata_enricher = MetadataEnricher()
        self.connectors: dict[SourceType, BaseConnector] = {}
    
    def register_connector(self, connector: BaseConnector):
        """Register a source connector."""
        self.connectors[connector.source_type] = connector
    
    async def ingest_from_connector(
        self,
        source_type: SourceType,
        config: dict,
        db: AsyncSession,
        user_id: str
    ) -> IngestionResult:
        """
        Run full ingestion pipeline for a source.
        
        Pipeline: Fetch -> Parse -> Chunk -> Enrich Metadata -> Store
        """
        connector = self.connectors.get(source_type)
        if not connector:
            raise ValueError(f"No connector registered for {source_type}")
        
        result = IngestionResult(documents_processed=0, chunks_created=0, errors=[])
        
        async for raw_doc in connector.fetch(config):
            try:
                # Extract base metadata from connector
                base_metadata = connector.extract_metadata(raw_doc, config)
                
                # Parse content (handle different formats)
                parsed_content = await self.parsers.parse(raw_doc.content, raw_doc.source.value)
                
                # Enrich metadata
                enriched_metadata = self.metadata_enricher.enrich(
                    base_metadata,
                    parsed_content
                )
                
                # Store document
                doc = await self._store_document(
                    db=db,
                    raw_doc=raw_doc,
                    content=parsed_content,
                    metadata=enriched_metadata,
                    user_id=user_id
                )
                
                # Chunk document
                chunks = self.chunker.chunk(
                    content=parsed_content,
                    document_id=str(doc.id)
                )

                # Generate embeddings for chunks
                pinecone_vectors = []
                for i, chunk in enumerate(chunks):
                    try:
                        embedding = await _get_embedding(chunk.content)
                        pinecone_vectors.append({
                            "id": f"{doc.id}-chunk-{i}",
                            "values": embedding,
                            "metadata": {
                                "content": chunk.content[:500],
                                "document_id": str(doc.id),
                                "title": raw_doc.title,
                                "source": raw_doc.source.value,
                                "account_id": raw_doc.metadata.get("account_id", "unknown"),
                                "department": raw_doc.metadata.get("department", "general"),
                                "access_level": raw_doc.metadata.get("access_level", 0),
                                "owner_id": user_id,
                            }
                        })
                    except Exception as e:
                        result.errors.append(f"Embedding error for chunk {i}: {str(e)}")

                # Store chunks + embeddings
                await self._store_chunks(db, doc.id, chunks, pinecone_vectors)
                
                result.documents_processed += 1
                result.chunks_created += len(chunks)
                
            except Exception as e:
                result.errors.append(f"Error processing {raw_doc.source_id}: {str(e)}")
        
        await db.commit()
        return result
    
    async def ingest_single_document(
        self,
        raw_doc: RawDocument,
        db: AsyncSession,
        user_id: str,
        config: Optional[dict] = None
    ) -> IngestionResult:
        """Ingest a single document directly."""
        result = IngestionResult(documents_processed=0, chunks_created=0, errors=[])
        config = config or {}
        
        try:
            # Parse content
            parsed_content = await self.parsers.parse(raw_doc.content, raw_doc.source.value)
            
            # Create metadata
            metadata = DocumentMetadata(
                source=raw_doc.source.value,
                source_id=raw_doc.source_id,
                account_id=raw_doc.metadata.get("account_id", "unknown"),
                department=raw_doc.metadata.get("department", "general"),
                access_level=raw_doc.metadata.get("access_level", 0),
                owner_id=user_id,
                timestamp=raw_doc.created_at
            )
            
            # Store document
            doc = await self._store_document(
                db=db,
                raw_doc=raw_doc,
                content=parsed_content,
                metadata=metadata,
                user_id=user_id
            )
            
            # Chunk document
            chunks = self.chunker.chunk(
                content=parsed_content,
                document_id=str(doc.id)
            )

            # Generate embeddings for chunks
            pinecone_vectors = []
            for i, chunk in enumerate(chunks):
                try:
                    embedding = await _get_embedding(chunk.content)
                    pinecone_vectors.append({
                        "id": f"{doc.id}-chunk-{i}",
                        "values": embedding,
                        "metadata": {
                            "content": chunk.content[:500],
                            "document_id": str(doc.id),
                            "title": raw_doc.title,
                            "source": raw_doc.source.value,
                            "account_id": raw_doc.metadata.get("account_id", "unknown"),
                            "department": raw_doc.metadata.get("department", "general"),
                            "access_level": raw_doc.metadata.get("access_level", 0),
                            "owner_id": user_id,
                        }
                    })
                except Exception as e:
                    result.errors.append(f"Embedding error for chunk {i}: {str(e)}")

            # Store chunks + embeddings
            await self._store_chunks(db, doc.id, chunks, pinecone_vectors)
            
            result.documents_processed = 1
            result.chunks_created = len(chunks)
            
        except Exception as e:
            result.errors.append(f"Error: {str(e)}")
        
        await db.commit()
        return result
    
    async def _store_document(
        self,
        db: AsyncSession,
        raw_doc: RawDocument,
        content: str,
        metadata: DocumentMetadata,
        user_id: str
    ) -> Document:
        """Store document in PostgreSQL."""
        doc = Document(
            title=raw_doc.title,
            content=content,
            source=metadata.source,
            source_id=metadata.source_id,
            account_id=metadata.account_id,
            department=metadata.department,
            access_level=metadata.access_level,
            owner_id=user_id,
            doc_metadata={
                "tags": metadata.tags,
                "allowed_roles": metadata.allowed_roles,
                "allowed_users": metadata.allowed_users,
            }
        )
        db.add(doc)
        await db.flush()
        return doc
    
    async def _store_chunks(
        self,
        db: AsyncSession,
        document_id: str,
        chunks: list[Chunk],
        pinecone_vectors: Optional[list[dict]] = None,
    ):
        """Store chunks in PostgreSQL and upsert embeddings to Pinecone."""
        for i, chunk in enumerate(chunks):
            doc_chunk = DocumentChunk(
                document_id=document_id,
                content=chunk.content,
                chunk_index=i
            )
            db.add(doc_chunk)

        # Upsert embeddings to Pinecone if provided
        if pinecone_vectors:
            await pinecone_client.upsert_vectors(vectors=pinecone_vectors)
