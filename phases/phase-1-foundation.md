# Phase 1 — Foundation

**Duration:** Days 1–3  
**Goal:** Working backend with auth, database, and frontend scaffolding

---

## Day 1 — Project Setup

### Backend

- [ ] Initialize `pyproject.toml` with all dependencies
- [ ] Create `Dockerfile` and `docker-compose.yml`
- [ ] Set up `.env.example` with all required variables
- [ ] Create `app/config.py` with Pydantic Settings
- [ ] Create `app/main.py` with FastAPI app + health check

### Frontend

- [ ] Initialize Next.js 14 with App Router
- [ ] Install and configure shadcn/ui
- [ ] Set up Tailwind CSS
- [ ] Configure PWA (next-pwa, manifest.json, service worker)
- [ ] Create basic layout and landing page

### Infrastructure

- [ ] PostgreSQL container in docker-compose
- [ ] Database connection pooling
- [ ] Alembic migration setup

---

## Day 2 — Database Models

### SQLAlchemy Models

- [ ] `User` — id, email, hashed_password, full_name, department, is_active, is_admin
- [ ] `Role` — id, name, description, access_level (0-3)
- [ ] `UserRole` — user_id, role_id (many-to-many)
- [ ] `Document` — id, title, content, source, source_id, account_id, department, access_level, owner_id, metadata
- [ ] `DocumentChunk` — id, document_id, content, chunk_index, qdrant_point_id
- [ ] `DocumentAccess` — id, document_id, user_id, role_id

### Migrations

- [ ] Create initial migration
- [ ] Test migration up/down
- [ ] Seed default roles (Public, Internal, Confidential, Restricted)

---

## Day 3 — Authentication

### Backend Auth

- [ ] Password hashing with passlib/bcrypt
- [ ] JWT token generation (python-jose)
- [ ] `POST /api/auth/register` — Create user
- [ ] `POST /api/auth/login` — Get token
- [ ] `GET /api/auth/me` — Get current user
- [ ] Auth middleware for protected routes

### Frontend Auth

- [ ] Login page with form
- [ ] Register page with form
- [ ] Auth context (store JWT, handle refresh)
- [ ] Protected route wrapper
- [ ] Redirect logic (unauthenticated → login)

---

## Exit Criteria

- [ ] User can register via UI
- [ ] User can login and receive JWT
- [ ] Protected API endpoints require valid token
- [ ] Frontend shows login/register pages
- [ ] All containers start with `docker-compose up`

---

## Files Created

```
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   └── auth/
│       ├── models.py
│       ├── router.py
│       ├── jwt.py
│       └── permissions.py
├── db/
│   ├── models.py
│   └── sessions.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example

frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── (auth)/
│       ├── login/page.tsx
│       └── register/page.tsx
├── components/ui/
├── lib/
│   ├── api.ts
│   └── auth.ts
├── public/manifest.json
├── package.json
└── tailwind.config.ts
```
