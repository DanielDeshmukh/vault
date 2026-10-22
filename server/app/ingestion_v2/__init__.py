"""Parser-based corpus ingestion v2 (plan: opencode_prompt_corpus_rebuild.md).

Offline only: parse + chunk + record building. No DB writes, no Pinecone,
no embedding calls — those belong to later approved phases.
"""
from .blocks import Block, ParsedDoc
from .chunker import Draft, chunk_doc
from .pipeline import build_records, detect_source_type, parse_file, process_file, source_title
from .records import CHUNK_VERSION, ChunkRecord, DropRecord, build_chunk_id, content_hash

__all__ = [
    "Block",
    "ParsedDoc",
    "Draft",
    "chunk_doc",
    "build_records",
    "detect_source_type",
    "parse_file",
    "process_file",
    "source_title",
    "CHUNK_VERSION",
    "ChunkRecord",
    "DropRecord",
    "build_chunk_id",
    "content_hash",
]
