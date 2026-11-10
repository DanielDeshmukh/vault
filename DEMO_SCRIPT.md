# Vault Demo Script — Frontend Walkthrough

> **Time:** ~10 minutes
> **URL:** https://vault-rbac-rag.vercel.app
> **Goal:** Show evaluators the full app flow — from landing page to RBAC in action

---

## Step 1: Landing Page (1 min)

**What to do:**
1. Open `https://vault-rbac-rag.vercel.app`
2. Scroll through the landing page

**What to say:**
> "This is the Vault landing page. It shows the architecture: 7 source connectors (Jira, Zendesk, Slack, Confluence, and more), RBAC at the vector store level, and cited generation. The system ingests documents from enterprise sources, chunks and embeds them in Pinecone, then serves permission-aware queries with citations."

**Key points to highlight:**
- Architecture diagram showing connectors → ingestion → Pinecone → query → citations
- Feature list: RBAC, cited generation, audit trail, 8 roles
- The "Try it" button leads to login

---

## Step 2: Login as Admin (1 min)

**What to do:**
1. Click "Sign In" or navigate to `/login`
2. Login with:
   - Email: `admin@vaultdemo.com`
   - Password: `Vault2026!`
3. You'll be redirected to the dashboard

**What to say:**
> "I'm logging in as the admin — Sarah Chen. The admin has full access to all 4,879 documents across all departments. After login, I land on the dashboard with the chat interface."

---

## Step 3: Ask a Question — Cited Answer (2 min)

**What to do:**
1. In the chat input, type: **"What is the cloud native tools strategy?"**
2. Press Enter and watch the streaming response
3. Click on a citation to see the source document

**What to say:**
> "I'm asking about the cloud native tools strategy. The system:
> 1. Searches Pinecone with my permission filter (admin = all docs)
> 2. Reranks results with Cohere for quality
> 3. Generates a cited answer with the LLM
> 4. Returns the answer with source citations I can click
>
> Notice the answer includes `[doc_id]` references inline, and each citation shows the document title, source department, and relevance score."

**Key points:**
- Streaming response (tokens appear in real-time)
- Citations are clickable — click one to see the source chunk
- The answer is grounded in the retrieved documents, not hallucinated

---

## Step 4: Document Listing — Admin View (1 min)

**What to do:**
1. Click "Documents" in the sidebar
2. Show the document list with 4,879 total
3. Note the department and classification columns

**What to say:**
> "As admin, I can see all 4,879 documents. Each document shows its department, classification level, and which roles can access it. For example, engineering ADRs are restricted to admin, engineer, and manager roles."

---

## Step 5: Logout & Login as Intern (1 min)

**What to do:**
1. Click logout (or open incognito window)
2. Login with:
   - Email: `intern1@vaultdemo.com`
   - Password: `Vault2026!`

**What to say:**
> "Now I'm logging in as an intern — the lowest privilege role. The intern can only see documents classified as public or internal in the general department."

---

## Step 6: Document Listing — Intern View (1 min)

**What to do:**
1. Click "Documents" in the sidebar
2. Show the document list — **1,556 total** (vs 4,879 for admin)

**What to say:**
> "This is the key RBAC demonstration. The same documents endpoint returns only 1,556 documents for the intern — compared to 4,879 for the admin. That's 3,323 documents blocked (68% of the corpus). The filtering happens at the database level before any document content is fetched, so the intern never even sees the existence of restricted documents."

**Key visual:**
- Admin: 4,879 documents
- Intern: 1,556 documents
- **3,323 documents blocked = 68% of corpus**

---

## Step 7: Ask the Same Question as Intern (1 min)

**What to do:**
1. In the chat, type the same question: **"What is the cloud native tools strategy?"**
2. Compare the answer with the admin's answer

**What to say:**
> "Asking the same question as the intern. The answer will be different because the intern can only access general department documents — no engineering or sales docs. The citations will be fewer and from a narrower set of sources. This proves RBAC works at the retrieval level, not just the display level."

---

## Step 8: Admin User Management (1 min)

**What to do:**
1. Logout, login as admin again
2. Click "Admin" → "Users" in the sidebar
3. Show the user list with roles and approval status

**What to say:**
> "The admin can manage users — approve new registrations, assign roles, and see the full user directory. New users register with a requested role, but they're pending approval until an admin approves them and assigns their actual role."

**Key points:**
- 20 users in the system
- Each user has roles (e.g., "intern", "engineer", "admin")
- Approval workflow: register → pending → admin approves → role assigned

---

## Step 9: Connectors Page (1 min)

**What to do:**
1. Click "Connectors" in the sidebar
2. Show the available connectors: Jira, Zendesk, Slack, Confluence

**What to say:**
> "Vault supports 7 source connectors for ingesting documents from enterprise systems. These are real implementations — not stubs. For example, the Jira connector fetches issues with comments, extracts text from ADF format, and handles pagination. The Zendesk connector does the same for tickets and comments."

---

## Summary for Evaluators

**What Vault does:**
1. **Ingests** documents from 7 enterprise sources (Jira, Zendesk, Slack, Confluence, etc.)
2. **Chunks and embeds** them in Pinecone with role-based metadata
3. **Serves queries** with permission-aware retrieval — each user only sees what their role allows
4. **Generates cited answers** — every claim is backed by a source document
5. **Manages users** with RBAC — 8 roles, approval workflow, admin controls

**Key differentiator:**
- RBAC at the **vector store level** — restricted documents are never fetched, not just hidden
- **Cited generation** — answers include inline references to source documents
- **Audit trail** — every query is traced with full metadata

**Numbers:**
- 4,879 documents, ~49,018 chunks in Pinecone
- 8 roles, 20 users
- Admin sees 100% of docs, intern sees 32%
- Queries return in ~5 seconds with 3-6 citations
