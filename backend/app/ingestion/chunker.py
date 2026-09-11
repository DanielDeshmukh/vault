from dataclasses import dataclass


@dataclass
class Chunk:
    """A chunk of text from a document."""
    content: str
    index: int
    start_char: int
    end_char: int


class SemanticChunker:
    """Chunks documents into smaller pieces for embedding."""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk(self, content: str, document_id: str) -> list[Chunk]:
        """
        Split content into overlapping chunks.
        
        Args:
            content: The text content to chunk
            document_id: The document ID (for reference)
            
        Returns:
            List of Chunk objects
        """
        if not content or len(content.strip()) == 0:
            return []
        
        # Clean content
        content = content.strip()
        
        # If content is smaller than chunk_size, return as single chunk
        if len(content) <= self.chunk_size:
            return [Chunk(
                content=content,
                index=0,
                start_char=0,
                end_char=len(content)
            )]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(content):
            # Calculate end position
            end = start + self.chunk_size
            
            # If not at the end, try to break at a sentence or paragraph
            if end < len(content):
                # Look for sentence boundaries
                for sep in ["\n\n", "\n", ". ", "! ", "? "]:
                    last_sep = content.rfind(sep, start + self.min_chunk_size, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break
            
            # Extract chunk
            chunk_content = content[start:end].strip()
            
            if chunk_content and len(chunk_content) >= self.min_chunk_size:
                chunks.append(Chunk(
                    content=chunk_content,
                    index=chunk_index,
                    start_char=start,
                    end_char=end
                ))
                chunk_index += 1
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start >= len(content):
                break
        
        return chunks
    
    def chunk_with_metadata(
        self,
        content: str,
        document_id: str,
        metadata: dict
    ) -> list[dict]:
        """
        Chunk content and attach metadata to each chunk.
        
        Returns:
            List of dicts with content and metadata
        """
        chunks = self.chunk(content, document_id)
        
        return [
            {
                "content": chunk.content,
                "document_id": document_id,
                "chunk_index": chunk.index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "total_chunks": len(chunks),
                **metadata
            }
            for chunk in chunks
        ]
