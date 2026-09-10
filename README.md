# Vault

**Permission-Aware Enterprise Knowledge System**

Vault is an enterprise-grade knowledge retrieval system that enables support teams, account managers, and customer success staff to ask natural-language questions across scattered internal documents and receive cited, grounded answers — while enforcing strict permission boundaries that prevent unauthorized content from ever reaching the language model.

---

## The Problem

Enterprise knowledge is fragmented across dozens of systems:

- **Support tickets** in Zendesk or Intercom
- **Engineering discussions** in Jira and Confluence
- **Team conversations** in Slack
- **Call recordings and transcripts** in Gong or Chorus
- **Company policies** in Google Docs or Notion
- **Customer data** in CSVs and spreadsheets

When a support agent asks, *"What did we promise this customer?"*, the answer might exist across a support ticket from last quarter, a Slack thread from the engineering team, and a signed contract amendment — but finding it requires navigating three different tools, each with its own search limitations.

Worse, some of those documents contain information the agent shouldn't see: HR notes, executive escalations, or confidential pricing details for other accounts.

**Vault solves both problems simultaneously.**

---

## How It Works

Vault ingests documents from multiple enterprise sources, parses and chunks them into searchable segments, and indexes them in a vector database with rich metadata — including source, account, department, timestamp, and access level.

When a user asks a question, Vault:

1. **Authenticates** the user and determines their permission scope
2. **Filters retrieval** at the database level, before any content reaches the language model
3. **Searches** using a hybrid approach (vector similarity + keyword matching)
4. **Reranks** results for maximum relevance
5. **Generates** a cited answer using only authorized sources
6. **Logs** the full trace for audit and compliance

The critical design principle: **permission filtering happens before retrieval, not after generation.** Unauthorized content never enters the model's context window.

---

## Key Features

### Permission-First Architecture

Vault's permission model is not a post-processing filter — it's architectural. User roles and document access controls are enforced at the vector store query level. The language model only ever sees content the authenticated user is authorized to access.

- **Role-based access control (RBAC)** with four permission tiers: Public, Internal, Confidential, Restricted
- **Document-level overrides** for exceptions and special cases
- **Account-scoped access** so support agents only see their assigned customers
- **Audit logging** of every query, retrieved chunk, and generated answer

### Multi-Source Ingestion

Vault connects to the tools your team already uses:

| Source | Data Ingested |
|--------|---------------|
| **Zendesk** | Tickets, comments, attachments, agent notes |
| **Jira** | Issues, comments, linked documentation |
| **Slack** | Channel exports, threads, reactions context |
| **Confluence** | Pages, spaces, embedded documents |
| **Transcripts** | Call recordings, meeting notes, interview summaries |
| **Policies** | Company docs, SOPs, compliance materials |
| **CSV Upload** | Custom datasets, CRM exports, spreadsheets |

Each source connector extracts structured metadata (account, department, timestamp) and maps it to Vault's unified permission model.

### Hybrid Search

Vault combines two search paradigms for maximum recall:

- **Vector similarity** for semantic understanding ("customer complained about billing" matches "invoice discrepancy")
- **BM25 keyword search** for exact matches (specific ticket IDs, error codes, proper nouns)

Results are merged and reranked using Cohere's cross-encoder for state-of-the-art relevance.

### Cited Generation

Every answer includes inline citations linking back to source documents. Users can verify claims, trace information to its origin, and assess recency. The system explicitly refuses to answer when insufficient authorized information exists, rather than hallucinating a response.

### Trace Logging

Every query generates a complete audit trail:

- User identity and timestamp
- Permission scope applied
- Retrieved chunks (with scores)
- Generated answer with citations
- Processing latency

This supports compliance requirements, debugging, and continuous quality improvement.

---

## Use Cases

### Customer Support

**Question:** *"What's the SLA for this customer's enterprise tier?"*

Vault retrieves the customer's contract terms, their support history, and the current SLA policy — but only if the agent has access to that account's documents.

### Account Management

**Question:** *"What did we promise in the last renewal call?"*

Vault synthesizes the call transcript, the follow-up email, and the contract amendment to provide a complete answer with source citations.

### Engineering Handoff

**Question:** *"What was the root cause of the outage affecting Acme Corp?"*

Vault pulls from the incident report, Slack discussion thread, and post-mortem document — scoped to the engineering team's permission level.

### Compliance Audit

**Question:** *"Show me all references to data retention policies across our support documentation."**

Vault searches across all policy documents, support scripts, and training materials, citing each reference with its source and last-updated timestamp.

---

## Security Model

Vault's security model is designed for enterprise compliance requirements:

### Pre-Retrieval Permission Filtering

Unlike systems that filter results after the language model has already processed them, Vault filters at the vector store query level. Unauthorized content is never loaded into memory, never sent to the model, and never appears in logs or traces.

### Four-Tier Access Control

| Level | Description | Example |
|-------|-------------|---------|
| **Public** | All authenticated users | Company policies, onboarding docs |
| **Internal** | Department-scoped | Team-specific procedures |
| **Confidential** | Account-scoped | Customer contracts, support history |
| **Restricted** | Named-user only | Executive notes, legal matters |

### Audit Trail

Every interaction is logged with full context: who asked what, what was retrieved, what was generated, and which permissions were applied. This supports SOC 2, HIPAA, and enterprise compliance requirements.

---

## Evaluation Framework

Vault includes a comprehensive evaluation framework to measure system quality:

### Golden Set

A curated set of 50 questions spanning:

- **Easy lookups** — Single-source factual questions
- **Cross-document synthesis** — Answers requiring multiple sources
- **Conflicting sources** — Cases where documents disagree
- **Stale information** — Questions about outdated content
- **Permission boundaries** — Cases requiring refusal or restricted answers
- **Edge cases** — Ambiguous, malformed, or adversarial queries

### Metrics

**Retrieval Quality** (measured independently from generation):
- Precision@5 — Relevance of top-5 retrieved chunks
- Recall@k — Coverage of all relevant documents
- Mean Reciprocal Rank — Position of first relevant result

**Generation Quality:**
- Faithfulness — Groundedness in retrieved sources
- Relevance — Alignment with user's question
- Citation accuracy — Correctness of source attributions

**Security (Non-Negotiable):**
- Unauthorized leakage rate — Must be exactly 0.0
- Permission boundary accuracy — Correct refusals and scoping

---

## API Reference

### Authentication

```
POST /api/auth/register
POST /api/auth/login
```

### Queries

```
POST /api/query
Authorization: Bearer <token>
Body: { "question": "string", "context": "optional" }
Response: { "answer": "string", "citations": [...], "trace_id": "string" }
```

### Document Management

```
POST /api/documents/ingest
GET  /api/documents/{id}
DELETE /api/documents/{id}
```

### Health

```
GET /health
```

---

## Technology

| Component | Purpose |
|-----------|---------|
| **Groq (Llama 3 70B)** | Fast, high-quality language model inference |
| **Groq Embeddings** | Vector representations for semantic search |
| **Cohere Rerank** | Cross-encoder for result relevance |
| **Qdrant** | Vector database with metadata filtering |
| **PostgreSQL** | User, role, and permission storage |
| **FastAPI** | High-performance async API framework |

---

## License

MIT License. See [LICENSE](LICENSE) for details.
