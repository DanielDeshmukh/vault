from dataclasses import asdict

from app.ingestion.chunker import SemanticChunker, Chunk

DOC_ID = "doc-test-1"


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
        chunks = chunker.chunk(text, DOC_ID)

        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_chunk_long_text(self):
        """Test chunking long text that requires multiple chunks."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)

        text = "word " * 200  # 200 words
        chunks = chunker.chunk(text, DOC_ID)

        assert len(chunks) > 1

    def test_chunk_overlap(self):
        """Test that chunks have proper overlap."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)

        text = " ".join(["word"] * 200)
        chunks = chunker.chunk(text, DOC_ID)

        # Check that consecutive chunks share some content
        for i in range(len(chunks) - 1):
            chunk1_words = set(chunks[i].content.split())
            chunk2_words = set(chunks[i + 1].content.split())

            # There should be some overlap
            overlap = chunk1_words & chunk2_words
            assert len(overlap) > 0 or len(chunks[i].content) < 50

    def test_chunk_preserves_content(self):
        """Test that chunking preserves original content."""
        chunker = SemanticChunker(chunk_size=50, chunk_overlap=10, min_chunk_size=5)

        text = "This is a test document with some content that should be preserved."
        chunks = chunker.chunk(text, DOC_ID)

        # All original words should appear in at least one chunk
        all_chunk_text = " ".join([c.content for c in chunks])

        for word in text.split():
            assert word in all_chunk_text

    def test_chunk_with_metadata(self):
        """Test that chunks can carry metadata."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)

        text = "This is a test document."
        chunks = chunker.chunk_with_metadata(text, DOC_ID, {"source": "test"})

        assert len(chunks) == 1
        assert chunks[0]["source"] == "test"
        assert chunks[0]["document_id"] == DOC_ID
        assert chunks[0]["content"] == text

    def test_chunk_indices(self):
        """Test that chunks have proper indices."""
        chunker = SemanticChunker(chunk_size=50, chunk_overlap=10, min_chunk_size=5)

        text = " ".join(["word"] * 200)
        chunks = chunker.chunk(text, DOC_ID)

        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)

        chunks = chunker.chunk("", DOC_ID)

        assert len(chunks) == 0

    def test_whitespace_only_text(self):
        """Test chunking whitespace-only text."""
        chunker = SemanticChunker(chunk_size=512, chunk_overlap=128)

        chunks = chunker.chunk("   \n\t  ", DOC_ID)

        assert len(chunks) == 0

    def test_chunk_char_offsets_are_ordered(self):
        """Chunk character offsets must be monotonic and within bounds."""
        chunker = SemanticChunker(chunk_size=80, chunk_overlap=20, min_chunk_size=10)
        text = " ".join(["sentence"] * 100)
        chunks = chunker.chunk(text, DOC_ID)

        assert len(chunks) > 1
        for c in chunks:
            assert 0 <= c.start_char < c.end_char <= len(text)
            assert text[c.start_char:c.end_char].strip() == c.content


class TestChunk:
    """Test Chunk dataclass."""

    def test_chunk_creation(self):
        """Test creating a Chunk object."""
        chunk = Chunk(
            content="Test content",
            index=0,
            start_char=0,
            end_char=12,
        )

        assert chunk.content == "Test content"
        assert chunk.index == 0
        assert chunk.start_char == 0
        assert chunk.end_char == 12

    def test_chunk_to_dict(self):
        """Test converting Chunk to dictionary."""
        chunk = Chunk(
            content="Test content",
            index=0,
            start_char=0,
            end_char=12,
        )

        chunk_dict = asdict(chunk)

        assert isinstance(chunk_dict, dict)
        assert chunk_dict["content"] == "Test content"
        assert chunk_dict["index"] == 0
        assert chunk_dict["start_char"] == 0
        assert chunk_dict["end_char"] == 12


class TestChunkingStrategies:
    """Test different chunking strategies."""

    def test_recursive_splitting(self):
        """Test recursive text splitting."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)

        # Text with natural boundaries
        text = "First sentence. Second sentence. Third sentence. " * 20
        chunks = chunker.chunk(text, DOC_ID)

        assert len(chunks) > 1

    def test_sentence_aware_chunking(self):
        """Test chunking respects sentence boundaries."""
        chunker = SemanticChunker(chunk_size=60, chunk_overlap=10, min_chunk_size=10)

        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk(text, DOC_ID)

        assert len(chunks) >= 1
        # Each chunk should end at a sentence boundary if possible
        for chunk in chunks:
            is_last_chunk = chunk == chunks[-1]
            ends_with_period = chunk.content.rstrip().endswith(".")

            # Either it ends with a period or it's the last chunk
            # (or the chunk is too small to contain a full sentence)
            assert ends_with_period or is_last_chunk or len(chunk.content) < 50
