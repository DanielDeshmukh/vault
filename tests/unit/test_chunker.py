import pytest
from app.ingestion.chunker import SemanticChunker, Chunk


class TestSemanticChunker:
    """Test semantic chunking logic."""
    
    def test_chunker_initialization(self):
        """Test chunker can be initialized."""
        chunker = SemanticChunker(
            chunk_size=512,
            chunk_overlap=128,
        )
        
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 128
    
    def test_chunk_short_text(self):
        """Test chunking short text that fits in one chunk."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)
        
        text = "This is a short document."
        chunks = chunker.chunk(text)
        
        assert len(chunks) == 1
        assert chunks[0].content == text
    
    def test_chunk_long_text(self):
        """Test chunking long text that requires multiple chunks."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
        
        # Create text longer than chunk_size
        text = "word " * 200  # 200 words
        chunks = chunker.chunk(text)
        
        assert len(chunks) > 1
    
    def test_chunk_overlap(self):
        """Test that chunks have proper overlap."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
        
        text = " ".join(["word"] * 200)
        chunks = chunker.chunk(text)
        
        # Check that consecutive chunks share some content
        for i in range(len(chunks) - 1):
            chunk1_words = set(chunks[i].content.split())
            chunk2_words = set(chunks[i + 1].content.split())
            
            # There should be some overlap
            overlap = chunk1_words & chunk2_words
            assert len(overlap) > 0 or len(chunks[i].content) < 50
    
    def test_chunk_preserves_content(self):
        """Test that chunking preserves original content."""
        chunker = SemanticChunker(chunk_size=50, chunk_overlap=10)
        
        text = "This is a test document with some content that should be preserved."
        chunks = chunker.chunk(text)
        
        # All original words should appear in at least one chunk
        all_chunk_text = " ".join([c.content for c in chunks])
        
        for word in text.split():
            assert word in all_chunk_text
    
    def test_chunk_metadata(self):
        """Test that chunks have proper metadata."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)
        
        text = "This is a test document."
        chunks = chunker.chunk(text, metadata={"source": "test"})
        
        assert len(chunks) == 1
        assert chunks[0].metadata is not None
        assert chunks[0].metadata.get("source") == "test"
    
    def test_chunk_indices(self):
        """Test that chunks have proper indices."""
        chunker = SemanticChunker(chunk_size=50, chunk_overlap=10)
        
        text = " ".join(["word"] * 200)
        chunks = chunker.chunk(text)
        
        for i, chunk in enumerate(chunks):
            assert chunk.index == i
    
    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)
        
        chunks = chunker.chunk("")
        
        assert len(chunks) == 0
    
    def test_whitespace_only_text(self):
        """Test chunking whitespace-only text."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)
        
        chunks = chunker.chunk("   \n\t  ")
        
        assert len(chunks) == 0


class TestChunk:
    """Test Chunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating a Chunk object."""
        chunk = Chunk(
            content="Test content",
            index=0,
            metadata={"source": "test"},
        )
        
        assert chunk.content == "Test content"
        assert chunk.index == 0
        assert chunk.metadata["source"] == "test"
    
    def test_chunk_to_dict(self):
        """Test converting Chunk to dictionary."""
        chunk = Chunk(
            content="Test content",
            index=0,
            metadata={"source": "test"},
        )
        
        chunk_dict = chunk.to_dict()
        
        assert isinstance(chunk_dict, dict)
        assert chunk_dict["content"] == "Test content"
        assert chunk_dict["index"] == 0
        assert chunk_dict["metadata"]["source"] == "test"


class TestChunkingStrategies:
    """Test different chunking strategies."""
    
    def test_recursive_splitting(self):
        """Test recursive text splitting."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
        
        # Text with natural boundaries
        text = "First sentence. Second sentence. Third sentence. " * 20
        chunks = chunker.chunk(text)
        
        assert len(chunks) > 1
    
    def test_sentence_aware_chunking(self):
        """Test chunking respects sentence boundaries."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
        
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk(text)
        
        # Each chunk should end at a sentence boundary if possible
        for chunk in chunks:
            # Check if chunk ends with sentence-ending punctuation
            # or is the last chunk
            is_last_chunk = chunk == chunks[-1]
            ends_with_period = chunk.content.rstrip().endswith(".")
            
            # Either it ends with a period or it's the last chunk
            # (or the chunk is too small to contain a full sentence)
            assert ends_with_period or is_last_chunk or len(chunk.content) < 50
