# Phase 3 — Permission-Aware Retrieval

**Duration:** Days 8–10  
**Goal:** Query system returns cited answers from only authorized sources

---

## Day 8 — Permission Filter + Search

### Permission Filter (NON-NEGOTIABLE)

- [ ] Implement `get_user_scope(user)` function
  ```python
  def get_user_scope(user: User) -> dict:
      # Returns Pinecone filter based on user's roles and access
      return {
          "$or": [
              {"access_level": {"$lte": max_role_level}},
              {"allowed_users": {"$in": [user.id]}},
              {"account_id": {"$in": user.assigned_accounts}}
          ]
      }
  ```

- [ ] Test permission filter in isolation
- [ ] Verify unauthorized collections are excluded
- [ ] Log all filter applications for audit

### Hybrid Search

- [ ] Vector search via Pinecone (semantic similarity)
- [ ] BM25 keyword search (using Elasticsearch or simple implementation)
- [ ] Merge results with Reciprocal Rank Fusion (RRF)
- [ ] Configurable weights (vector vs keyword)

---

## Day 9 — Reranker + Groq LLM

### Cohere Reranker

- [ ] Initialize Cohere client
- [ ] Implement rerank function
  ```python
  def rerank(query: str, documents: list, top_k: int = 5) -> list:
      results = cohere.rerank(
          query=query,
          documents=documents,
          top_n=top_k,
          model="rerank-english-v3.0"
      )
      return [documents[r.index] for r in results.results]
  ```

- [ ] Integrate into search pipeline
- [ ] Return reranked results with scores

### Groq LLM Integration

- [ ] Initialize Groq client
- [ ] Implement cited generation prompt
  ```python
  SYSTEM_PROMPT = """
  Answer using ONLY the provided sources.
  Cite sources with [document_id] inline.
  If insufficient information, say so.
  Never fabricate citations.
  """
  ```

- [ ] Implement streaming response
- [ ] Parse citations from response
- [ ] Validate citation format

---

## Day 10 — API + Frontend Integration

### Query Endpoint

- [ ] `POST /api/query`
  - Authenticate user
  - Apply permission filter
  - Run hybrid search
  - Rerank results
  - Generate cited answer
  - Log trace
  - Return response

- [ ] Response schema:
  ```json
  {
    "answer": "Based on the documents...",
    "citations": [
      {"document_id": "...", "title": "...", "source": "zendesk", "score": 0.92}
    ],
    "trace_id": "..."
  }
  ```

### Frontend Query UI

- [ ] Query input component
- [ ] Loading state with progress
- [ ] Response display with inline citations
- [ ] Source cards showing document details
- [ ] Error handling (refusals, timeouts)

### Trace Logger

- [ ] Log query, user, permissions applied
- [ ] Log retrieved chunks with scores
- [ ] Log generated answer
- [ ] Log latency metrics
- [ ] Store in PostgreSQL for audit

---

## Exit Criteria

- [ ] Unauthorized chunks never reach the LLM
- [ ] Answers include inline citations
- [ ] User can verify citations in UI
- [ ] Full trace logged for every query
- [ ] Permission filter tested with multiple roles

---

## Files Created

```
backend/app/retrieval/
├── __init__.py
├── permission_filter.py
├── search.py
├── reranker.py
└── generator.py

backend/app/tracing/
├── __init__.py
├── logger.py
└── models.py

frontend/components/chat/
├── query-input.tsx
├── response-display.tsx
└── source-card.tsx

frontend/hooks/
└── use-query.ts
```
