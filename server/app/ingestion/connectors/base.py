from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SourceType(StrEnum):
    ZENDESK = "zendesk"
    JIRA = "jira"
    SLACK = "slack"
    CONFLUENCE = "confluence"
    TRANSCRIPT = "transcript"
    POLICY = "policy"
    CSV = "csv"


@dataclass
class RawDocument:
    """Raw document from a source connector before parsing."""
    source: SourceType
    source_id: str
    title: str
    content: str
    metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None
    author: str | None = None


@dataclass
class DocumentMetadata:
    """Structured metadata for permission filtering and context."""
    source: str
    source_id: str
    account_id: str
    department: str
    access_level: int  # 0=public, 1=internal, 2=confidential, 3=restricted
    owner_id: str | None = None
    allowed_roles: list[str] = field(default_factory=list)
    allowed_users: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    tags: list[str] = field(default_factory=list)


class BaseConnector(ABC):
    """Abstract base class for all source connectors."""

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Return the source type for this connector."""
        pass

    @abstractmethod
    def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        """
        Fetch documents from the source.

        Declared without `async` so implementations may be async generator
        functions (`async def` + `yield`), which are callables returning
        AsyncIterator rather than coroutines.

        Args:
            config: Source-specific configuration (API keys, filters, etc.)

        Yields:
            RawDocument instances
        """
        ...

    @abstractmethod
    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        """
        Extract structured metadata from a raw document.

        Args:
            doc: The raw document
            config: Source-specific configuration

        Returns:
            DocumentMetadata with permission and context info
        """
        pass

    async def test_connection(self, config: dict) -> bool:
        """
        Test if the source connection is valid.

        Args:
            config: Source-specific configuration

        Returns:
            True if connection is successful
        """
        return True
