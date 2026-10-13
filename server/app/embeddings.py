"""Single source of truth for text embeddings.

Both the corpus ingest and query-time search MUST go through this module.
Embedding the corpus with one model and the query with another (or at a
different dimensionality) silently produces garbage retrieval, because the
vectors no longer share a space.

Provider: NVIDIA NIM ``nvidia/nemotron-3-embed-1b``.
    - Fixed at 2048 dims: the API rejects any other value
      (``dimensions must be one of 2048``), so the Pinecone index is 2048.
    - Vectors are L2 unit-normalised, which is what Pinecone's ``cosine``
      metric expects.
    - No observed rate limit: 12/12 rapid calls of 64 succeeded, and a
      single call accepts up to 256 texts.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# NIM accepts large batches and showed no rate limiting; 128 balances
# throughput against per-call latency and payload size.
NIM_BATCH = 128
NIM_MAX_CHARS = 2000
EMBED_DIM = 2048
_MODEL = "nvidia/nemotron-3-embed-1b"
_ENDPOINT = "https://integrate.api.nvidia.com/v1/embeddings"

_MAX_RETRIES = 6
_RETRY_BASE_SECS = 3.0


def _api_key() -> str:
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        from app.config import settings

        key = getattr(settings, "NVIDIA_API_KEY", "")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set -- cannot embed")
    return key


def _retry_delay(attempt: int, exc: Exception) -> float:
    """Backoff for rate limits; -1 for fatal errors."""
    status = getattr(exc, "code", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    retryable = status in (408, 429, 500, 502, 503, 504) or isinstance(exc, (TimeoutError, OSError))
    if not retryable:
        return -1.0
    return _RETRY_BASE_SECS * (2**attempt)


def _post(texts: list[str], dim: int = EMBED_DIM) -> list[list[float]]:
    payload = {
        "input": [t[:NIM_MAX_CHARS] for t in texts],
        "model": _MODEL,
    }
    req = urllib.request.Request(
        _ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read())
    data = sorted(body.get("data") or [], key=lambda x: x.get("index", 0))
    if len(data) != len(texts):
        raise RuntimeError(f"expected {len(texts)} embeddings, got {len(data)}")
    out = [d["embedding"] for d in data]
    for v in out:
        if len(v) != dim:
            raise RuntimeError(f"expected {dim}-dim vector, got {len(v)}")
    return out


def _embed_batch(texts: list[str], dim: int = EMBED_DIM) -> list[list[float]]:
    """Embed one batch, backing off on rate limits.

    Every retry is logged: a silent exponential backoff is indistinguishable
    from a hung process, which is exactly how an earlier Gemini run stalled
    for eight minutes with no output.
    """
    last: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return _post(texts, dim)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode()[:200]
            except Exception:
                detail = ""
            last = RuntimeError(f"HTTP {exc.code}: {detail}")
            delay = _retry_delay(attempt, exc)
            if delay < 0:
                raise last from exc
            print(
                f"    [embed] HTTP {exc.code} on attempt {attempt + 1}/{_MAX_RETRIES}; "
                f"retrying in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
        except Exception as exc:  # noqa: BLE001 - retry transient, raise fatal
            last = exc
            delay = _retry_delay(attempt, exc)
            if delay < 0:
                raise
            print(
                f"    [embed] {type(exc).__name__} on attempt {attempt + 1}/{_MAX_RETRIES}; "
                f"retrying in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(f"embedding failed after {_MAX_RETRIES} attempts: {last}")


def embed_texts(texts: list[str], dim: int = EMBED_DIM) -> list[list[float]]:
    """Embed ``texts``, batching to respect provider payload limits."""
    if not texts:
        return []
    out: list[list[float]] = []
    for start in range(0, len(texts), NIM_BATCH):
        out.extend(_embed_batch(texts[start : start + NIM_BATCH], dim))
    return out


def embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Embed a single string (convenience wrapper)."""
    return embed_texts([text], dim)[0]
