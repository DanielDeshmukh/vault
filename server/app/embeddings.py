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
    - ``input_type`` (NVIDIA docs): ``passage`` for corpus/index text,
      ``query`` for retrieval queries. Omitting it makes the endpoint treat
      every input as a query, which measurably degrades retrieval quality,
      so both call sites pass it explicitly.
    - Trial tier: free endpoint, unpublished per-model rate limits (a ~40
      RPM baseline is commonly reported and shown in the build.nvidia.com
      UI), no credits/quota/expiry; production requires NVIDIA AI
      Enterprise licensing or self-hosting. Retry/backoff plus the query
      cache below exist for that tier.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from app.config import settings

# NIM accepts large batches; 128 balances throughput against per-call
# latency. The cap keeps a single batch under provider payload limits.
NIM_BATCH = 128
# 12k chars (Phase 5): the old 2000-char blind slice cut the tail off
# 17.6% of records; individual texts are still capped by ``truncate``
# below the provider's 4096-token input limit.
NIM_MAX_CHARS = 12000
EMBED_DIM = settings.EMBED_DIM
_MODEL = "nvidia/nemotron-3-embed-1b"
_ENDPOINT = "https://integrate.api.nvidia.com/v1/embeddings"

_MAX_RETRIES = 6
_RETRY_BASE_SECS = 3.0

# Short TTL cache for query-time embeddings: repeated queries are common
# in demos/tests, and the trial endpoint's rate limit is the scarcest
# runtime resource. Ingest batches never use this cache.
_QUERY_CACHE: dict[str, tuple[float, list[float]]] = {}
_QUERY_CACHE_TTL_SECS = 300.0
_QUERY_CACHE_MAX = 512


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


def _post(
    texts: list[str],
    dim: int = EMBED_DIM,
    input_type: str | None = None,
) -> list[list[float]]:
    payload = {
        "input": [t[:NIM_MAX_CHARS] for t in texts],
        "model": _MODEL,
        # Belt-and-braces for the 4096-token input limit: cut the tail of
        # any pathological text instead of failing the whole batch.
        "truncate": "END",
    }
    if input_type is not None:
        payload["input_type"] = input_type
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


def _embed_batch(
    texts: list[str],
    dim: int = EMBED_DIM,
    input_type: str | None = None,
) -> list[list[float]]:
    """Embed one batch, backing off on rate limits.

    Every retry is logged: a silent exponential backoff is indistinguishable
    from a hung process, which is exactly how an earlier Gemini run stalled
    for eight minutes with no output.
    """
    last: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return _post(texts, dim, input_type)
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


def embed_texts(
    texts: list[str],
    dim: int = EMBED_DIM,
    input_type: str | None = None,
) -> list[list[float]]:
    """Embed ``texts``, batching to respect provider payload limits.

    ``input_type`` must be ``"passage"`` at ingest and ``"query"`` at
    retrieval; NVIDIA's endpoint otherwise treats every input as a query.
    """
    if not texts:
        return []
    out: list[list[float]] = []
    for start in range(0, len(texts), NIM_BATCH):
        out.extend(_embed_batch(texts[start : start + NIM_BATCH], dim, input_type))
    return out


def embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Embed a single string (convenience wrapper)."""
    return embed_texts([text], dim)[0]


def embed_query(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Embed one retrieval query (``input_type="query"``) with a short TTL cache.

    The cache exists because the free NIM tier is rate-limited (~40 RPM
    baseline) and repeated queries are common in demos and tests; ingest
    traffic must use :func:`embed_texts` with ``input_type="passage"``
    instead, which bypasses this cache.
    """
    return embed_query_batch([text], dim)[0]


def embed_query_batch(texts: list[str], dim: int = EMBED_DIM) -> list[list[float]]:
    """Embed query texts with the TTL cache, batching only the cache misses.

    Repeated queries (demos, tests, back-to-back retries) cost zero API
    calls until they expire; novel texts go out in one request so the
    runtime query path stays within the trial rate limit.
    """
    if not texts:
        return []
    now = time.monotonic()
    out: list[list[float] | None] = [None] * len(texts)
    misses: list[int] = []
    for i, text in enumerate(texts):
        key = f"{dim}\x00{text}"
        hit = _QUERY_CACHE.get(key)
        if hit is not None and now - hit[0] < _QUERY_CACHE_TTL_SECS:
            out[i] = list(hit[1])
        else:
            misses.append(i)
    if misses:
        fresh = embed_texts([texts[i] for i in misses], dim, input_type="query")
        for i, vec in zip(misses, fresh):
            out[i] = vec
            if len(_QUERY_CACHE) >= _QUERY_CACHE_MAX:
                _QUERY_CACHE.clear()
            _QUERY_CACHE[f"{dim}\x00{texts[i]}"] = (now, vec)
    return [v for v in out if v is not None]
