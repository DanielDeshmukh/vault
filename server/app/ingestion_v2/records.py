"""Chunk record schema (plan section D) — JSONL-ready, no DB imports."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

CHUNK_VERSION = 2


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    chunk_index: int
    source_path: str
    source_type: str  # md | cuad_txt | sec_htm | pdf
    doc_title: str
    heading_path: list[str]
    block_type: str  # prose | table | code | list | mixed
    text_md: str
    text_embed: str
    token_count: int
    char_count: int
    content_hash: str
    department: str
    classification: str
    allowed_roles: list[str]
    chunk_version: int = CHUNK_VERSION
    dropped_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DropRecord:
    """A chunk candidate that was dropped, with the reason (plan C)."""

    reason: str
    preview: str
    heading_path: list[str] = field(default_factory=list)
    block_type: str = ""  # prose | list | table | code | heading | mixed
    text: str = ""  # full dropped text (gate word-loss subtraction)

    def to_dict(self) -> dict:
        return asdict(self)


def content_hash(text_md: str) -> str:
    return hashlib.sha256(text_md.encode("utf-8")).hexdigest()


def build_chunk_id(doc_id: str, chunk_index: int) -> str:
    return f"{doc_id}#{chunk_index:04d}"
