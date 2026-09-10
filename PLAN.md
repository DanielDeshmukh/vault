# Vault — Implementation Plan

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         QUERY FLOW                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User ──► JWT Auth ──► Permission Scope ──► Query ──► Response      │
│                                │                    │                │
│                                ▼                    ▼                │
│                         ┌──────────┐        ┌──────────────┐        │
│                         │ RBAC     │        │ Filtered     │        │
│                         │ Policy   │        │ Retrieval    │        │
│                         │ Engine   │        │ (pre-model)  │        │
│                         └──────────┘        └──────────────┘        │
│                                                   │                 │
│                                                   ▼                 │
│                                            ┌──────────────┐         │
│                                            │ Hybrid       │         │
│                                            │ Search +     │         │
│                                            │ Rerank       │         │
│                                            └──────────────┘         │
│                                                   │                 │
│                                                   ▼                 │
│                                            ┌──────────────┐         │
│                                            │ Cited Gen    │         │
│                                            │ (Groq/LLaMA) │         │
│                                            └──────────────┘         │
│                                                   │                 │
│                                                   ▼                 │
│                                            ┌──────────────┐         │
│                                            │ Trace Log    │         │
│                                            └──────────────┘         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       INGESTION PIPELINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Sources ──► Parsers ──► Chunker ──► Metadata Tagger ──► Qdrant    │
│      │            │           │              │                      │
│      ▼            ▼           ▼              ▼                      │
│   ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐             │
│   │Zendesk │ │ PDF     │ │Semantic │ │ source       │             │
│   │Jira    │ │ DOCX    │ │ chunk   │ │ account_id   │             │
│   │Slack   │ │ HTML    │ │ +overlap│ │ department   │             │
│   │Confl.  │ │ TXT     │ │         │ │ access_level │             │
│   │CSV     │ │         │ │         │ │ timestamp    │             │
│   └────────┘ └─────────┘ └─────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **API** | FastAPI | Async, type-safe, auto-docs |
| **LLM** | Groq (Llama 3 70B) | Free tier, fast inference, open-source |
| **Embeddings** | Groq (nomic-embed-text) | Same provider, consistent, fast |
| **Reranker** | Cohere Rerank v3.0 | State-of-the-art cross-encoder |
| **Vector DB** | Qdrant | Native metadata filtering, fast |
| **Relational DB** | PostgreSQL | Users, roles, permissions, audit logs |
| **ORM** | SQLAlchemy 2.0 | Async support, mature ecosystem |
| **Auth** | JWT (python-jose) | Self-contained, no vendor lock-in |
| **Orchestration** | LangChain | Chains, retrieval pipelines |
| **Evaluation** | Custom + Ragas | Retrieval + generation metrics |
| **Infra** | Docker Compose | Local dev, easy demo |

---

## Directory Structure

```
vault/
├── app/
│   ├── main.py                         # FastAPI entry point
│   ├── config.py                       # Settings from env vars
│   ├── auth/
│   │   ├── models.py                   # User, Role, Permission
│   │   ├── router.py                   # /register, /login
│   │   ├── jwt.py                      # Token encode/decode
│   │   └── permissions.py              # RBAC policy engine
│   ├── ingestion/
│   │   ├── pipeline.py                 # Orchestrator
│   │   ├── connectors/
│   │   │   ├── base.py                 # Abstract connector
│   │   │   ├── zendesk.py              # Tickets, comments
│   │   │   ├── jira.py                 # Issues, linked docs
│   │   │   ├── slack.py                # Channel exports, threads
│   │   │   ├── confluence.py           # Pages, spaces
│   │   │   ├── transcripts.py          # Call/meeting transcripts
│   │   │   ├── policies.py             # Company docs, SOPs
│   │   │   └── csv_uploader.py         # Generic CSV import
│   │   ├── parsers/
│   │   │   ├── pdf.py
│   │   │   ├── docx.py
│   │   │   ├── html.py
│   │   │   └── text.py
│   │   ├── chunker.py                  # Semantic chunking
│   │   └── metadata.py                 # Tag extraction
│   ├── retrieval/
│   │   ├── permission_filter.py        # Pre-retrieval gate
│   │   ├── search.py                   # Hybrid (vector + BM25)
│   │   ├── reranker.py                 # Cohere reranking
│   │   └── generator.py               # Cited generation
│   ├── db/
│   │   ├── models.py                   # SQLAlchemy models
│   │   ├── sessions.py                 # Async session factory
│   │   └── migrations/                 # Alembic
│   ├── api/
│   │   ├── router.py                   # Route aggregation
│   │   ├── queries.py                  # POST /query
│   │   └── documents.py               # CRUD documents
│   └── tracing/
│       ├── logger.py                   # Structured trace log
│       └── models.py                   # Trace schema
├── eval/
│   ├── golden_set.py                   # 50 questions
│   ├── evaluator.py                    # Automated eval
│   └── metrics.py                      # Precision, recall, MRR
├── tests/
│   ├── unit/
│   ├── integration/
│   └── security/
│       └── test_permission_leakage.py  # Zero leakage tests
├── scripts/
│   ├── seed_data.py
│   ├── run_eval.py
│   └── setup_db.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Phases

### Phase 1 — Foundation (Days 1–3)

| Task | Deliverable |
|------|-------------|
| Project scaffolding | pyproject.toml, Dockerfile, docker-compose.yml |
| PostgreSQL models | User, Role, UserRole, Document, DocumentChunk, DocumentAccess |
| JWT auth | /register, /login, token middleware |
| RBAC engine | Permission scope resolver |
| FastAPI skeleton | Health check, router stubs |

**Exit criteria:** Can register a user, login, receive a JWT, hit a protected endpoint.

---

### Phase 2 — Ingestion Pipeline (Days 4–7)

| Task | Deliverable |
|------|-------------|
| Base connector interface | Abstract class with fetch() and extract_metadata() |
| Zendesk connector | Tickets, comments, org_id mapping |
| Jira connector | Issues, comments, project key mapping |
| Slack connector | Channel exports, thread context |
| Confluence connector | Pages, space key mapping |
| Transcript connector | Call/meeting transcripts with customer_id |
| Policy connector | Company docs, SOPs |
| CSV uploader | Generic bulk import with column mapping |
| Parsers | PDF, DOCX, HTML, plain text |
| Semantic chunker | Fixed-size + overlap, configurable |
| Metadata tagger | source, account_id, department, access_level, timestamp |
| Qdrant integration | Collection creation, point upsert with metadata |

**Exit criteria:** Can ingest a document from any source, chunk it, tag it, store it in Qdrant with metadata.

---

### Phase 3 — Permission-Aware Retrieval (Days 8–10)

| Task | Deliverable |
|------|-------------|
| Permission filter | Filter at Qdrant query level (pre-retrieval) |
| Hybrid search | Vector similarity + BM25 keyword |
| Cohere reranker | Cross-encoder reranking |
| Groq LLM integration | Llama 3 70B cited generation |
| Citation engine | Inline [source_id] references |
| Trace logger | Full audit trail per query |

**Exit criteria:** Query returns a cited answer from only authorized sources. Unauthorized chunks never reach the model.

---

### Phase 4 — Evaluation (Days 11–12)

| Task | Deliverable |
|------|-------------|
| Golden set | 50 questions across 6 categories |
| Evaluator | Automated retrieval + generation scoring |
| Metrics | Precision@5, Recall@k, MRR, Faithfulness, Relevance |
| Security tests | Zero unauthorized leakage verification |
| Report generator | Markdown eval reports |

**Exit criteria:** 50-question eval runs end-to-end, zero leakage confirmed.

---

### Phase 5 — Polish (Days 13–14)

| Task | Deliverable |
|------|-------------|
| Integration tests | Full query flow tests |
| Security audit | Permission boundary verification |
| Error handling | Graceful failures, retry logic |
| Logging | Structured logs with correlation IDs |
| Documentation | API docs, README finalization |

**Exit criteria:** Production-ready demo, all tests passing.

---

## Permission Model

### Four-Tier Access Control

| Tier | Scope | Example |
|------|-------|---------|
| 0 — Public | All authenticated users | Company policies, onboarding |
| 1 — Internal | Department-scoped | Team procedures, internal docs |
| 2 — Confidential | Account-scoped | Customer contracts, support history |
| 3 — Restricted | Named-user only | Executive notes, legal matters |

### Pre-Retrieval Filtering (Non-Negotiable)

```python
# CORRECT: Filter at vector store level
authorized_collections = get_user_scope(user)
results = qdrant.search(
    query_vector=embedding,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="collection_id",
                match=MatchAny(any=authorized_collections)
            )
        ]
    )
)

# WRONG: Filter after generation (leaks content)
results = qdrant.search(query_vector=embedding)
filtered = [r for r in results if can_access(r, user)]  # Model already saw it
```

---

## Metadata Schema

```python
{
    "document_id": "uuid",
    "source": "zendesk|jira|slack|confluence|transcript|policy|csv",
    "source_id": "original_id_from_system",
    "account_id": "customer_or_org_identifier",
    "department": "support|sales|engineering|hr|legal",
    "access_level": 0,  # 0=public, 1=internal, 2=confidential, 3=restricted
    "owner_id": "user_uuid",
    "allowed_roles": ["support_agent", "account_manager"],
    "allowed_users": ["specific_user_uuid"],
    "timestamp": "2024-01-15T10:30:00Z",
    "chunk_index": 0,
    "total_chunks": 5
}
```

---

## Evaluation Golden Set (50 Questions)

| Category | Count | Example |
|----------|-------|---------|
| Easy Lookup | 10 | "What is our refund policy?" |
| Cross-Doc Synthesis | 10 | "What did we promise Acme Corp in Q3?" |
| Conflicting Sources | 5 | "What's the current SLA?" (sources disagree) |
| Stale Info | 5 | "What was the pricing in 2023?" |
| Permission Boundary | 10 | "Show me executive notes for Beta Corp" (should refuse) |
| Edge Cases | 10 | Malformed, ambiguous, adversarial queries |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Retrieval Precision@5 | ≥ 0.85 |
| Retrieval Recall@k | ≥ 0.90 |
| MRR | ≥ 0.80 |
| Faithfulness | ≥ 0.90 |
| Citation Accuracy | ≥ 0.95 |
| **Unauthorized Leakage Rate** | **0.0** |
| Permission Boundary Accuracy | ≥ 0.98 |

---

## Environment Variables

```bash
# Required
GROQ_API_KEY=gsk_...
COHERE_API_KEY=...
DATABASE_URL=postgresql://vault:vault@db:5432/vault
QDRANT_URL=http://qdrant:6333
JWT_SECRET_KEY=...

# Optional
GROQ_MODEL=llama3-70b-8192
EMBEDDING_MODEL=nomic-embed-text
COHERE_MODEL=rerank-english-v3.0
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
```
