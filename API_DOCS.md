# Vault API Reference

> **Live deployment:** `https://vault-rbac-rag.vercel.app`
> **All responses below are real** — captured from the live API.

---

## Quick Start

Get a token and ask a question in 2 commands. Examples work on **Windows CMD**, **PowerShell**, and **Linux/macOS bash**.

### Windows CMD

```cmd
:: 1. Login — copies the full token to your clipboard and prints it
powershell -Command "(Invoke-RestMethod -Uri 'https://vault-rbac-rag.vercel.app/api/auth/login' -Method Post -ContentType 'application/json' -Body '{\"email\":\"admin@vaultdemo.com\",\"password\":\"Vault2026!\"}').access_token | Clip; Write-Host '--- FULL TOKEN (copied to clipboard) ---'; (Invoke-RestMethod -Uri 'https://vault-rbac-rag.vercel.app/api/auth/login' -Method Post -ContentType 'application/json' -Body '{\"email\":\"admin@vaultdemo.com\",\"password\":\"Vault2026!\"}').access_token"

:: Paste the token above into TOKEN variable
set TOKEN=paste_your_token_here

:: 2. Query
curl.exe -s -X POST https://vault-rbac-rag.vercel.app/api/query -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"question\":\"What is the cloud native tools strategy?\"}"
```

**Easier option — just run this single command to see your full token:**
```cmd
powershell -Command "(Invoke-RestMethod -Uri 'https://vault-rbac-rag.vercel.app/api/auth/login' -Method Post -ContentType 'application/json' -Body '{\"email\":\"admin@vaultdemo.com\",\"password\":\"Vault2026!\"}').access_token"
```

### PowerShell

```powershell
# 1. Login — prints the full token so you can copy it
$response = Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@vaultdemo.com","password":"Vault2026!"}'
Write-Host "--- FULL TOKEN (copy below) ---"
$response.access_token
$TOKEN = $response.access_token

# 2. Query
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/query" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $TOKEN"} -Body '{"question":"What is the cloud native tools strategy?"}' | ConvertTo-Json
```

### Linux / macOS (Bash)

```bash
# 1. Login — prints the full token so you can copy it
TOKEN=$(curl -s -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vaultdemo.com","password":"Vault2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "--- FULL TOKEN (copy below) ---"
echo "$TOKEN"

# 2. Query
curl -s https://vault-rbac-rag.vercel.app/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What is the cloud native tools strategy?"}' \
  | python3 -m json.tool
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/health
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/health"
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@vaultdemo.com\",\"password\":\"Vault2026!\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@vaultdemo.com","password":"Vault2026!"}'
```

**cURL (Bash):**
```bash
curl -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vaultdemo.com","password":"Vault2026!"}'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<full JWT token>",
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

### 🔑 Get Your Token (Copy-Paste Ready)

Use these commands to get a full token you can copy and paste into other commands:

**Windows CMD:**
```cmd
powershell -Command "(Invoke-RestMethod -Uri 'https://vault-rbac-rag.vercel.app/api/auth/login' -Method Post -ContentType 'application/json' -Body '{\"email\":\"admin@vaultdemo.com\",\"password\":\"Vault2026!\"}').access_token"
```

**PowerShell:**
```powershell
(Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@vaultdemo.com","password":"Vault2026!"}').access_token
```

**Bash:**
```bash
curl -s -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vaultdemo.com","password":"Vault2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

> **For other roles**, just replace `admin@vaultdemo.com` with the email from the [Demo Credentials](#demo-credentials) table above. All use password `Vault2026!`.

### POST /api/auth/register

**Auth:** Not required

**cURL (Windows CMD):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/auth/register -H "Content-Type: application/json" -d "{\"email\":\"newuser@example.com\",\"password\":\"SecurePass123!\",\"full_name\":\"Jane Doe\",\"department\":\"Engineering\",\"requested_role\":\"employee\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/register" -Method Post -ContentType "application/json" -Body '{"email":"newuser@example.com","password":"SecurePass123!","full_name":"Jane Doe","department":"Engineering","requested_role":"employee"}'
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/auth/me -H "Authorization: Bearer %TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/me" -Headers @{"Authorization"="Bearer $TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/query -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"question\":\"What is the cloud native tools strategy?\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/query" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $TOKEN"} -Body '{"question":"What is the cloud native tools strategy?"}'
```

**cURL (Bash):**
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

### 🔑 Get Intern Token (Copy-Paste Ready)

**Windows CMD:**
```cmd
powershell -Command "(Invoke-RestMethod -Uri 'https://vault-rbac-rag.vercel.app/api/auth/login' -Method Post -ContentType 'application/json' -Body '{\"email\":\"intern1@vaultdemo.com\",\"password\":\"Vault2026!\"}').access_token"
```

**PowerShell:**
```powershell
(Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/auth/login" -Method Post -ContentType "application/json" -Body '{"email":"intern1@vaultdemo.com","password":"Vault2026!"}').access_token
```

**Bash:**
```bash
curl -s -X POST https://vault-rbac-rag.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"intern1@vaultdemo.com","password":"Vault2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

---

### POST /api/query (Intern — Restricted Results)

**Auth:** Required (Intern Bearer token)

**cURL (Windows CMD):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/query -H "Content-Type: application/json" -H "Authorization: Bearer %INTERN_TOKEN%" -d "{\"question\":\"What are the working groups?\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/query" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $INTERN_TOKEN"} -Body '{"question":"What are the working groups?"}'
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -N -X POST https://vault-rbac-rag.vercel.app/api/query/stream -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"question\":\"What is the cloud native tools strategy?\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/query/stream" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $TOKEN"} -Body '{"question":"What is the cloud native tools strategy?"}'
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/query/trace/81517e9c-b265-4022-bb8f-37575ac8c67d -H "Authorization: Bearer %TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/query/trace/81517e9c-b265-4022-bb8f-37575ac8c67d" -Headers @{"Authorization"="Bearer $TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe "https://vault-rbac-rag.vercel.app/api/documents?limit=5" -H "Authorization: Bearer %TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/documents?limit=5" -Headers @{"Authorization"="Bearer $TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/documents/ffe60a68-886d-49f4-83f9-c1f7475cf028 -H "Authorization: Bearer %TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/documents/ffe60a68-886d-49f4-83f9-c1f7475cf028" -Headers @{"Authorization"="Bearer $TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X DELETE https://vault-rbac-rag.vercel.app/api/documents/{document_id} -H "Authorization: Bearer %ADMIN_TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/documents/{document_id}" -Method Delete -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD — multipart):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/ingest -H "Authorization: Bearer %ADMIN_TOKEN%" -F "file=@C:\path\to\document.md" -F "department=engineering" -F "classification=internal"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/ingest" -Method Post -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"} -Form @{file=(Get-Item "C:\path\to\document.md"); department="engineering"; classification="internal"}
```

**cURL (Bash — multipart):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X POST https://vault-rbac-rag.vercel.app/api/ingest/direct -H "Content-Type: application/json" -H "Authorization: Bearer %ADMIN_TOKEN%" -d "{\"title\":\"My Document\",\"content\":\"Document content here...\",\"source\":\"manual\",\"department\":\"general\",\"classification\":\"internal\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/ingest/direct" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"} -Body '{"title":"My Document","content":"Document content here...","source":"manual","department":"general","classification":"internal"}'
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X POST "https://vault-rbac-rag.vercel.app/api/ingest/test-connector?source=jira" -H "Content-Type: application/json" -H "Authorization: Bearer %ADMIN_TOKEN%" -d "{\"jira_url\":\"https://your-company.atlassian.net\",\"jira_email\":\"user@company.com\",\"jira_token\":\"your-api-token\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/ingest/test-connector?source=jira" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"} -Body '{"jira_url":"https://your-company.atlassian.net","jira_email":"user@company.com","jira_token":"your-api-token"}'
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/admin/users -H "Authorization: Bearer %ADMIN_TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/admin/users" -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe https://vault-rbac-rag.vercel.app/api/admin/roles -H "Authorization: Bearer %ADMIN_TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/admin/roles" -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

**cURL (Bash):**
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

**cURL (Windows CMD):**
```cmd
curl.exe -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/approve -H "Authorization: Bearer %ADMIN_TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/approve" -Method Put -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

**cURL (Bash):**
```bash
curl -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/approve \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### PUT /api/admin/users/{id}/role

**Auth:** Required (Admin only)

**cURL (Windows CMD):**
```cmd
curl.exe -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/role -H "Content-Type: application/json" -H "Authorization: Bearer %ADMIN_TOKEN%" -d "{\"role\":\"engineer\"}"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/role" -Method Put -ContentType "application/json" -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"} -Body '{"role":"engineer"}'
```

**cURL (Bash):**
```bash
curl -X PUT https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}/role \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"role": "engineer"}'
```

### DELETE /api/admin/users/{id}

**Auth:** Required (Admin only)

**cURL (Windows CMD):**
```cmd
curl.exe -X DELETE https://vault-rbac-rag.vercel.app/api/admin/users/{user_id} -H "Authorization: Bearer %ADMIN_TOKEN%"
```

**cURL (PowerShell):**
```powershell
Invoke-RestMethod -Uri "https://vault-rbac-rag.vercel.app/api/admin/users/{user_id}" -Method Delete -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

**cURL (Bash):**
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

## Evaluation Framework

The project includes an automated evaluation system (`run_eval.py`) that tests RBAC and RAG quality against the live API. It runs queries as different roles and measures answer relevance, citation presence, latency, and permission boundary enforcement.

### Quick Setup

```bash
pip install httpx
```

### Running Evaluations

#### Quick Mode (Recommended for demos)

Runs **3 questions per role** across all 8 roles (~24 queries, ~2-3 minutes):
- **1 easy passing** — straightforward factual question about the corpus
- **1 tricky passing** — cross-document synthesis requiring deeper reasoning
- **1 out-of-scope** — irrelevant question that should be refused

```bash
# All 8 roles, 3 questions each (default)
python run_eval.py --quick

# Specific roles only
python run_eval.py --quick --roles admin intern engineer

# With lower concurrency to avoid rate limiting
python run_eval.py --quick --concurrency 2
```

#### Full Mode

Runs **all 30 questions per role** across all 8 roles (~240 queries, ~20-30 minutes):

```bash
# All roles, all questions
python run_eval.py --full

# Single role, all questions
python run_eval.py --full --roles admin

# Filter by category
python run_eval.py --full --categories easy_lookup edge_case
```

### Command Line Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--quick` | 3 questions per role (1 easy, 1 tricky, 1 out-of-scope) | All 8 roles |
| `--full` | All 30 questions per role | All 8 roles |
| `--roles` | Space-separated roles to evaluate | All 8 demo roles |
| `--categories` | Filter by category: `easy_lookup`, `cross_doc_synthesis`, `permission_boundary`, `edge_case` | All categories |
| `--base-url` | API base URL for local dev | Live Vercel deployment |
| `--concurrency` | Max concurrent API calls | 3 |
| `--output` | Markdown report output path | `eval_report.md` |
| `--json-output` | JSON results output path | `eval_results.json` |

### Available Roles

`admin`, `intern`, `employee`, `engineer`, `manager`, `hr`, `legal`, `finance`

### Output Files

- **`eval_report.md`** — Detailed markdown report with per-question answers, citations, latency, relevance scores, and timestamps
- **`eval_results.json`** — Machine-readable JSON with all query results for programmatic analysis

### Example Output

```
======================================================================
  Vault Evaluation Runner
  Mode: quick
  Started: 2026-11-10 22:00:00 UTC
======================================================================

Base URL: https://vault-rbac-rag.vercel.app
Roles: all 8 demo roles
Questions per role: 3
Total queries: ~24

Running evaluation...
  Progress: 10/24 queries completed
  Progress: 20/24 queries completed
Completed in 45.2s

======================================================================
  EVALUATION SUMMARY
======================================================================
Total queries:    24
Successful:       22
Errors:            2
Refused:           8
With citations:   14
Avg latency:      21000ms
Avg relevance:    65.00%

By Role:
  admin        |   3 queries |   3 success |   1 refused | rel=66.67% | lat=20000ms
  intern       |   3 queries |   3 success |   1 refused | rel=63.33% | lat=22000ms
  ...

RBAC Comparison (Admin vs Intern):
  Admin relevance:   66.67%
  Intern relevance:  63.33%
  Admin with citations: 2/3
  Intern with citations: 1/3
```

### Question Categories

| Category | Description | Count |
|----------|-------------|-------|
| `easy_lookup` | Single-source factual questions | 15 |
| `cross_doc_synthesis` | Multi-document synthesis | 5 |
| `permission_boundary` | Tests RBAC filtering | 5 |
| `edge_case` | Out-of-scope / adversarial | 5 |

---

## Architecture Notes

- **Vector store:** Pinecone with metadata-based permission filtering
- **Embeddings:** Cohere embed-v4 (2048 dimensions)
- **Reranker:** Cohere rerank for result quality
- **LLM:** Cohere Command for answer generation
- **Database:** Neon Postgres (users, documents metadata, roles)
- **Deployment:** Vercel serverless (API) + Next.js 14 (frontend)
- **Corpus:** 4,879 GitLab handbook documents, ~49,018 chunks
