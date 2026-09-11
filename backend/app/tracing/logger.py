from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
import json

from app.db.models import User


@dataclass
class TraceEntry:
    """A single trace log entry."""
    trace_id: str
    user_id: str
    user_email: str
    query: str
    timestamp: datetime
    permission_filter: Optional[dict] = None
    retrieved_chunks: list[dict] = field(default_factory=list)
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None


class TraceLogger:
    """
    Structured trace logger for query audit trail.
    
    Logs every query, retrieved chunk, and generated answer
    for compliance and debugging purposes.
    """
    
    def __init__(self):
        self.traces: list[TraceEntry] = []
    
    def create_trace(self, user: User, query: str) -> TraceEntry:
        """Create a new trace entry."""
        import uuid
        
        trace = TraceEntry(
            trace_id=str(uuid.uuid4()),
            user_id=str(user.id),
            user_email=user.email,
            query=query,
            timestamp=datetime.utcnow()
        )
        self.traces.append(trace)
        return trace
    
    def log_permission_filter(self, trace: TraceEntry, filter_dict: Optional[dict]):
        """Log the permission filter applied."""
        trace.permission_filter = filter_dict
    
    def log_retrieved_chunks(self, trace: TraceEntry, chunks: list[dict]):
        """Log retrieved chunks."""
        trace.retrieved_chunks = chunks
    
    def log_answer(
        self,
        trace: TraceEntry,
        answer: str,
        citations: list[dict],
        latency_ms: float
    ):
        """Log the generated answer."""
        trace.answer = answer
        trace.citations = citations
        trace.latency_ms = latency_ms
    
    def log_error(self, trace: TraceEntry, error: str):
        """Log an error."""
        trace.error = error
    
    def get_trace(self, trace_id: str) -> Optional[TraceEntry]:
        """Get a trace by ID."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                return trace
        return None
    
    def to_dict(self, trace: TraceEntry) -> dict:
        """Convert trace to dictionary for logging/storage."""
        return {
            "trace_id": trace.trace_id,
            "user_id": trace.user_id,
            "user_email": trace.user_email,
            "query": trace.query,
            "timestamp": trace.timestamp.isoformat(),
            "permission_filter": trace.permission_filter,
            "retrieved_chunks": trace.retrieved_chunks,
            "answer": trace.answer,
            "citations": trace.citations,
            "latency_ms": trace.latency_ms,
            "error": trace.error,
        }


# Singleton instance
trace_logger = TraceLogger()
