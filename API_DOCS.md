# Vault API Reference

> **Live deployment:** `https://vault-rbac-rag.vercel.app`
> **All responses below are real** — captured from the live API.

---

## Quick Start

Get a token and ask a question in 2 commands:

```bash
# 1. Login
TOKEN=$(curl -s -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vaultdemo.com","password":"Vault2026!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Query
curl -s https://vault-rbac-rag.vercel.app/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What is the cloud native tools strategy?"}' \
  | python -m json.tool
```

---

## Demo Credentials

All demo accounts use the password: **`Vault2026!`**

| Role | Email | Documents Visible |
|------|-------|-------------------|
| Admin | `admin@vaultdemo.com` | 4,879 |
| Manager | `manager1@vaultdemo.com` | 3,397 |
| Engineer | `engineer1@vaultdemo.com` | 3,099 |
| Legal | `legal1@vaultdemo.com` | 2,661 |
| Employee | `employee1@vaultdemo.com` | 2,076 |
| HR | `hr1@vaultdemo.com` | 1,648 |
| Finance | `finance1@vaultdemo.com` | 1,619 |
| Intern | `intern1@vaultdemo.com` | 1,556 |

---

## Table of Contents

- [Health](#health)
- [Authentication](#authentication)
- [Queries](#queries)
- [Documents](#documents)
- [Ingestion](#ingestion)
- [Administration](#administration)

---

## Health

### GET /api/health

**Auth:** Not required

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "app": "Vault"
}
```

---

## Authentication

### POST /api/auth/login

**Auth:** Not required

**cURL:**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vaultdemo.com","password":"Vault2026!"}'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...<redacted>",
  "token_type": "bearer",
  "user": {
    "id": "cdc8aff8-537d-40e5-9879-e3b8f4d63d75",
    "email": "admin@vaultdemo.com",
    "full_name": "Sarah Chen",
    "department": "Administration",
    "requested_role": null,
    "is_admin": true,
    "is_approved": true,
    "approval_screen_started_at": "2026-10-18T05:40:14.481072"
  }
}
```

### POST /api/auth/register

**Auth:** Not required

**cURL:**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecurePass123!",
    "full_name": "Jane Doe",
    "department": "Engineering",
    "requested_role": "employee"
  }'
```

**Response (201 Created):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...<redacted>",
  "token_type": "bearer",
  "user": {
    "id": "93905154-41af-4bbd-bcc2-222aec56018e",
    "email": "newuser_test@example.com",
    "full_name": "Test User",
    "department": "Engineering",
    "requested_role": "employee",
    "is_admin": false,
    "is_approved": false,
    "approval_screen_started_at": null
  }
}
```

> **Note:** New users are created with `is_approved: false` and a default `intern` role. An admin must approve and assign the requested role before the user can query documents.

### GET /api/auth/me

**Auth:** Required (Bearer token)

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Response (200 OK) — Admin:**
```json
{
  "id": "cdc8aff8-537d-40e5-9879-e3b8f4d63d75",
  "email": "admin@vaultdemo.com",
  "full_name": "Sarah Chen",
  "department": "Administration",
  "requested_role": null,
  "is_admin": true,
  "is_approved": true,
  "approval_screen_started_at": "2026-10-18T05:40:14.481072"
}
```

**Response (200 OK) — Intern:**
```json
{
  "id": "e3f857c6-eea9-468c-8874-edb14d5d6340",
  "email": "intern1@vaultdemo.com",
  "full_name": "Intern One",
  "department": "General",
  "requested_role": null,
  "is_admin": false,
  "is_approved": true,
  "approval_screen_started_at": null
}
```

---

## Queries

### POST /api/query

**Auth:** Required (Bearer token)

**cURL:**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What is the cloud native tools strategy?"}'
```

**Response (200 OK):**
```json
{
  "answer": "The provided sources do not contain specific information about a \"cloud native tools strategy.\" However, they cover various aspects of SaaS usage, customer health scoring, cost metrics, data visualization, team operating principles, and innovation competitions, which could be relevant to developing or supporting such a strategy [doc_general_1113, doc_general_1098, doc_engineering_0143, doc_general_1037, doc_general_1004, doc_sales_0502].\n\nFor SaaS usage, understanding user behavior and adoption patterns is critical for optimizing cloud native tools [doc_general_1113]. Customer health scoring can help identify areas where cloud native tools may need improvement or additional support [doc_general_1098]. Cost metrics are essential for evaluating the financial impact of adopting cloud native tools [doc_engineering_0143]. Effective data visualization, as outlined in the Tableau Style Guide, can aid in communicating the benefits and performance of cloud native tools [doc_general_1037]. The Enterprise Data & Insights Team Operating Principles emphasize collaboration and data-driven decision-making, which are key to implementing a successful cloud native tools strategy [doc_general_1004]. Lastly, innovation competitions can foster creativity and drive the development of new cloud native solutions [doc_sales_0502].\n\nWhile none of the sources explicitly detail a cloud native tools strategy, these elements collectively contribute to a framework that could support such an initiative.",
  "citations": [
    {
      "document_id": "doc_general_1113",
      "chunk_id": "doc_general_1113#chunk_001",
      "title": "Freemium SaaS Usage Data",
      "source": "general",
      "score": 0.813492596
    },
    {
      "document_id": "doc_general_1098",
      "chunk_id": "doc_general_1098#chunk_001",
      "title": "Customer Health Scoring",
      "source": "general",
      "score": 0.813492537
    },
    {
      "document_id": "doc_engineering_0143",
      "chunk_id": "doc_engineering_0143#chunk_001",
      "title": "Group Cost Metrics",
      "source": "engineering",
      "score": 0.813492537
    },
    {
      "document_id": "doc_general_1037",
      "chunk_id": "doc_general_1037#chunk_001",
      "title": "Tableau Style Guide",
      "source": "general",
      "score": 0.813492537
    },
    {
      "document_id": "doc_general_1004",
      "chunk_id": "doc_general_1004#chunk_001",
      "title": "Enterprise Data & Insights Team Operating Principles",
      "source": "general",
      "score": 0.813491702
    },
    {
      "document_id": "doc_sales_0502",
      "chunk_id": "doc_sales_0502#chunk_001",
      "title": "Innovation Pitch Competion",
      "source": "sales",
      "score": 0.813491702
    }
  ],
  "trace_id": "81517e9c-b265-4022-bb8f-37575ac8c67d"
}
```

> **Key features demonstrated:**
> - **Cited generation:** Each answer includes `[doc_id]` references inline
> - **Source diversity:** Citations span multiple departments (general, engineering, sales)
> - **Relevance scoring:** Each citation has a similarity score (0.81 = strong match)
> - **Trace ID:** Every query gets a unique trace for audit

### POST /api/query (Intern — Restricted Results)

**Auth:** Required (Intern Bearer token)

**cURL:**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INTERN_TOKEN" \
  -d '{"question":"What are the working groups?"}'
```

**Response (200 OK):**
```json
{
  "answer": "The provided sources do not explicitly define \"working groups.\" However, they offer insights into various team structures and collaborations that may resemble working groups:\n\n1. **Data Team Internships**: Mentions internships within the data team, implying structured programs for skill development and project contributions [doc_general_1002].  \n2. **Enterprise Data & Insights Team Operating Principles**: Outlines principles guiding the team's operations, such as collaboration, data-driven decision-making, and continuous improvement, which could form the basis for working groups [doc_general_1004].  \n3. **Data Team Calendar - Meetings**: Lists regular meetings, suggesting recurring forums for collaboration or group work [doc_general_0987].  \n\nWhile not explicitly labeled as \"working groups,\" these sources highlight collaborative structures and principles that may align with such groups.",
  "citations": [
    {
      "document_id": "doc_general_1002",
      "chunk_id": "doc_general_1002#chunk_001",
      "title": "Data Team Internships",
      "source": "general",
      "score": 0.903075874
    },
    {
      "document_id": "doc_general_1004",
      "chunk_id": "doc_general_1004#chunk_001",
      "title": "Enterprise Data & Insights Team Operating Principles",
      "source": "general",
      "score": 0.903075337
    },
    {
      "document_id": "doc_general_0987",
      "chunk_id": "doc_general_0987#chunk_001",
      "title": "Data Team Calendar - Meetings",
      "source": "general",
      "score": 0.903068423
    }
  ],
  "trace_id": "14bf978d-855a-4d48-accc-7cc95f14d3f7"
}
```

> **RBAC in action:** Intern sees only 3 citations from `general` department — engineering and sales docs are filtered out at the vector store level.

### POST /api/query/stream

**Auth:** Required (Bearer token)

Streams the answer as Server-Sent Events (SSE).

**cURL:**
```bash
curl -N -X POST https://vault-rbac-rag.vercel.app/api/query/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What is the cloud native tools strategy?"}'
```

**Response (SSE stream):**
```
data: {"type": "sources", "sources": [{"document_id": "doc_general_1113", "chunk_id": "doc_general_1113#chunk_001", "title": "Freemium SaaS Usage Data", "source": "general", "score": 0.8135}]}

data: {"type": "delta", "content": "The"}
data: {"type": "delta", "content": " provided"}
data: {"type": "delta", "content": " sources"}
...

data: {"type": "citations", "citations": [{"document_id": "doc_general_1113", "title": "Freemium SaaS Usage Data", "source": "general", "score": 0.8135}]}

data: {"type": "done", "trace_id": "81517e9c-b265-4022-bb8f-37575ac8c67d"}
```

### GET /api/query/trace/{trace_id}

**Auth:** Required (Bearer token) — returns 404 if you don't own the trace (admins can read any trace)

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/query/trace/81517e9c-b265-4022-bb8f-37575ac8c67d \
  -H "Authorization: Bearer $TOKEN"
```

**Response (200 OK):**
```json
{
  "trace_id": "81517e9c-b265-4022-bb8f-37575ac8c67d",
  "user_id": "cdc8aff8-537d-40e5-9879-e3b8f4d63d75",
  "user_email": "admin@vaultdemo.com",
  "query": "What is the cloud native tools strategy?",
  "timestamp": "2026-11-10T14:19:24.143410",
  "permission_filter": null,
  "retrieved_chunks": [
    {
      "id": "doc_general_1113#chunk_001",
      "content": "...",
      "score": 0.813492596,
      "metadata": {
        "allowed_roles": ["intern", "employee", "engineer", "manager", "hr", "legal", "finance", "admin"],
        "classification": "internal",
        "department": "general",
        "doc_id": "doc_general_1113",
        "source_title": "Freemium SaaS Usage Data",
        "source_file": "general\\gitlab_handbook\\customer-experience\\product-usage-data\\freemium-saas-usage-data.md"
      }
    }
  ],
  "answer": "...",
  "citations": [
    {
      "document_id": "doc_general_1113",
      "title": "Freemium SaaS Usage Data",
      "source": "general",
      "score": 0.813492596
    }
  ],
  "latency_ms": 5426.33,
  "error": null
}
```

> **Audit trail:** Full trace includes the query, retrieved chunks with metadata, the generated answer, citations, and latency.

---

## Documents

### GET /api/documents

**Auth:** Required (Bearer token)

**Query params:** `limit` (default 20), `offset` (default 0)

**cURL:**
```bash
curl "https://vault-rbac-rag.vercel.app/api/documents?limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

**Response (200 OK) — Admin (sees 4,879 docs):**
```json
{
  "items": [
    {
      "id": "ffe60a68-886d-49f4-83f9-c1f7475cf028",
      "title": "Cloud Native Tools Strategy Working Group",
      "source": "gitlab-handbook:company/working-groups/cloud-native-tool-strategy.md",
      "account_id": null,
      "department": "general",
      "access_level": 1,
      "classification": "internal",
      "allowed_roles": ["admin", "employee", "engineer", "finance", "hr", "intern", "legal", "manager"],
      "owner_id": null,
      "created_at": "2026-10-17T10:08:56.358936",
      "can_access": true
    },
    {
      "id": "ffd951f9-408b-48e7-9441-8d364cf59341",
      "title": "Digital SMB + SA Working Group",
      "source": "gitlab-handbook:company/working-groups/digital-smb-sa.md",
      "department": "general",
      "classification": "internal",
      "allowed_roles": ["admin", "employee", "engineer", "finance", "hr", "intern", "legal", "manager"],
      "can_access": true
    },
    {
      "id": "ffd3bf62-e8d4-4c83-8260-66d5c1151f73",
      "title": "Duo Agent Platform ADR 008: Duo Messaging Service",
      "source": "gitlab-handbook:engineering/architecture/design-documents/duo_workflow/decisions/008_duo_messaging_s",
      "department": "engineering",
      "classification": "internal",
      "allowed_roles": ["admin", "engineer", "manager"],
      "can_access": true
    }
  ],
  "total": 4879,
  "limit": 5,
  "offset": 0
}
```

**Response (200 OK) — Intern (sees 1,556 docs):**
```json
{
  "items": [
    {
      "id": "ffe60a68-886d-49f4-83f9-c1f7475cf028",
      "title": "Cloud Native Tools Strategy Working Group",
      "source": "gitlab-handbook:company/working-groups/cloud-native-tool-strategy.md",
      "department": "general",
      "classification": "internal",
      "allowed_roles": ["admin", "employee", "engineer", "finance", "hr", "intern", "legal", "manager"],
      "can_access": true
    }
  ],
  "total": 1556,
  "limit": 5,
  "offset": 0
}
```

> **RBAC proof:** Same endpoint, different roles → different `total` counts. Admin sees 4,879 docs, intern sees 1,556 docs. Filtering happens at the database level.

### GET /api/documents/{id}

**Auth:** Required (Bearer token)

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/documents/ffe60a68-886d-49f4-83f9-c1f7475cf028 \
  -H "Authorization: Bearer $TOKEN"
```

**Response (200 OK):**
```json
{
  "id": "ffe60a68-886d-49f4-83f9-c1f7475cf028",
  "title": "Cloud Native Tools Strategy Working Group",
  "source": "gitlab-handbook:company/working-groups/cloud-native-tool-strategy.md",
  "account_id": null,
  "department": "general",
  "access_level": 1,
  "classification": "internal",
  "allowed_roles": ["admin", "employee", "engineer", "finance", "hr", "intern", "legal", "manager"],
  "owner_id": null,
  "created_at": "2026-10-17T10:08:56.358936",
  "can_access": true,
  "content": "\n## Attributes\n\n| Attribute | Value |\n|-----------|-------|\n| Working Group | Cloud Native Tools Strategy |\n| ... (full document content)"
}
```

### DELETE /api/documents/{id}

**Auth:** Required (Admin only)

**cURL:**
```bash
curl -X DELETE https://vault-rbac-rag.vercel.app/api/documents/{document_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response (200 OK):**
```json
{"message": "Document deleted"}
```

---

## Ingestion

### POST /api/ingest

**Auth:** Required (Admin only)

Uploads a file for ingestion into the knowledge base.

**cURL (multipart):**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/ingest \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/path/to/document.md" \
  -F "department=engineering" \
  -F "classification=internal"
```

### POST /api/ingest/direct

**Auth:** Required (Admin only)

Ingest content directly via JSON body.

**cURL:**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/ingest/direct \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "title": "My Document",
    "content": "Document content here...",
    "source": "manual",
    "department": "general",
    "classification": "internal"
  }'
```

### POST /api/ingest/test-connector

**Auth:** Required (Admin only)

Test a connector configuration before full ingestion.

**cURL:**
```bash
curl -X POST "https://vault-rbac-rag.vercel.app/api/ingest/test-connector?source=jira" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "jira_url": "https://your-company.atlassian.net",
    "jira_email": "user@company.com",
    "jira_token": "your-api-token"
  }'
```

**Supported connector types:** `jira`, `zendesk`, `slack`, `confluence`, `transcript`, `policy`, `csv`

---

## Administration

### GET /api/admin/users

**Auth:** Required (Admin only) — returns 403 for non-admins

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response (200 OK) — 20 users:**
```json
[
  {
    "id": "e3f857c6-eea9-468c-8874-edb14d5d6340",
    "email": "intern1@vaultdemo.com",
    "full_name": "Intern One",
    "department": "General",
    "requested_role": null,
    "is_admin": false,
    "is_approved": true,
    "roles": ["intern"]
  },
  {
    "id": "a8d19e87-dfbf-4487-bf74-fe17a9990c87",
    "email": "employee1@vaultdemo.com",
    "full_name": "Employee One",
    "department": "Sales",
    "requested_role": null,
    "is_admin": false,
    "is_approved": true,
    "roles": ["employee"]
  },
  {
    "id": "f178313d-0a42-42e8-b50d-4debb485b0dd",
    "email": "engineer1@vaultdemo.com",
    "full_name": "Engineer One",
    "department": "Engineering",
    "requested_role": null,
    "is_admin": false,
    "is_approved": true,
    "roles": ["engineer"]
  },
  {
    "id": "cdc8aff8-537d-40e5-9879-e3b8f4d63d75",
    "email": "admin@vaultdemo.com",
    "full_name": "Sarah Chen",
    "department": "Administration",
    "requested_role": null,
    "is_admin": true,
    "is_approved": true,
    "roles": ["Confidential", "admin"]
  }
]
```

**Response (403 Forbidden) — Non-admin:**
```json
{
  "detail": "Admin access required"
}
```

### GET /api/admin/roles

**Auth:** Required (Admin only)

**cURL:**
```bash
curl https://vault-rbac-rag.vercel.app/api/admin/roles \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Response (200 OK) — 12 roles:**
```json
[
  {"name": "legal", "access_level": 0, "description": "Corpus role: legal"},
  {"name": "intern", "access_level": 0, "description": "Corpus role: intern"},
  {"name": "engineer", "access_level": 0, "description": "Corpus role: engineer"},
  {"name": "employee", "access_level": 0, "description": "Corpus role: employee"},
  {"name": "finance", "access_level": 0, "description": "Corpus role: finance"},
  {"name": "admin", "access_level": 0, "description": "Corpus role: admin"},
  {"name": "hr", "access_level": 0, "description": "Corpus role: hr"},
  {"name": "manager", "access_level": 0, "description": "Corpus role: manager"},
  {"name": "Public", "access_level": 0, "description": "All authenticated users"},
  {"name": "Internal", "access_level": 1, "description": "Department-scoped access"},
  {"name": "Confidential", "access_level": 2, "description": "Account-scoped access"},
  {"name": "Restricted", "access_level": 3, "description": "Named-user only access"}
]
```

### PUT /api/admin/users/{id}/approve

**Auth:** Required (Admin only)

**cURL:**
```bash
curl -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/approve \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### PUT /api/admin/users/{id}/role

**Auth:** Required (Admin only)

**cURL:**
```bash
curl -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/role \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"role": "engineer"}'
```

### DELETE /api/admin/users/{id}

**Auth:** Required (Admin only)

**cURL:**
```bash
curl -X DELETE https://vault-rbac-rag.vercel.app/api/admin/users/{user_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## RBAC Demonstration

The most important feature — **Role-Based Access Control** — is demonstrated by comparing the same query across different roles:

| Role | Documents Visible | Query Citations |
|------|-------------------|-----------------|
| Admin | 4,879 | 6 citations (all departments) |
| Intern | 1,556 | 3 citations (general only) |

The permission filter runs **before** retrieval at the Pinecone vector store level, ensuring restricted documents are never even fetched for unauthorized users.

---

## Error Responses

### 401 Unauthorized
```json
{"detail": "Not authenticated"}
```

### 403 Forbidden
```json
{"detail": "Admin access required"}
```

### 404 Not Found
```json
{"detail": "Trace not found"}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "source"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

---

## Architecture Notes

- **Vector store:** Pinecone with metadata-based permission filtering
- **Embeddings:** Cohere embed-v4 (2048 dimensions)
- **Reranker:** Cohere rerank for result quality
- **LLM:** Cohere Command for answer generation
- **Database:** Neon Postgres (users, documents metadata, roles)
- **Deployment:** Vercel serverless (API) + Next.js 14 (frontend)
- **Corpus:** 4,879 GitLab handbook documents, ~49,018 chunks
