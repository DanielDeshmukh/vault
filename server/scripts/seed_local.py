"""
Local seed script for Vault - synchronous version (avoids Neon pooler issues).
Run: cd server && python -m scripts.seed_local

Seeding is idempotent and the phases are independent:
  * documents are ingested only while the corpus is empty -- 5 or more
    documents means the real corpus is already loaded and must not be
    re-ingested;
  * roles and users are seeded on every run, so a populated corpus no longer
    blocks user seeding (the old script returned before reaching them).

Both role families come from one command: the tier roles (Public, Internal,
Confidential, Restricted) that gate the legacy UI, and the 8 corpus roles
(intern, employee, ...) that registration and retrieval depend on. Without the
corpus set, POST /api/auth/register answers 500 -- app/auth/router.py assigns
DEFAULT_PENDING_ROLE = "intern" and fails when that row is missing, which is
exactly how 23 integration/security tests broke.

VAULT_DEMO_PASSWORD must be set when a user has to be created; it is refused
rather than stored empty, because an empty hash would be a broken login.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.auth.jwt import get_password_hash
from app.config import settings
from app.db.models import Document, DocumentChunk, Role, User, UserRole
from scripts.seed_corpus_roles import CORPUS_ROLES as CORPUS_ROLE_NAMES
from scripts.seed_corpus_roles import GRANTS as CORPUS_GRANTS

# Sync engine for local seed (use direct Neon endpoint, not pooler)
_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").replace("postgres://", "postgresql+psycopg2://")
_db_url = _db_url.replace("-pooler", "")
_sync_engine = create_engine(_db_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_sync_engine)

ROLES = [
    {"name": "Public", "description": "All authenticated users", "access_level": 0},
    {"name": "Internal", "description": "Department-scoped access", "access_level": 1},
    {"name": "Confidential", "description": "Account-scoped access", "access_level": 2},
    {"name": "Restricted", "description": "Named-user only access", "access_level": 3},
    # Corpus roles, imported so this script and seed_corpus_roles.py can never
    # drift apart. access_level=0: they drive retrieval, not the tier ceiling.
    *(
        {"name": n, "description": f"Corpus role: {n}", "access_level": 0}
        for n in CORPUS_ROLE_NAMES
    ),
]

USERS = [
    {"email": "admin@vaultdemo.com", "password": os.environ.get("VAULT_DEMO_PASSWORD", ""), "full_name": "Sarah Chen", "department": "engineering", "is_admin": True, "roles": ["Confidential"]},
    {"email": "engineer@vaultdemo.com", "password": os.environ.get("VAULT_DEMO_PASSWORD", ""), "full_name": "Marcus Johnson", "department": "engineering", "is_admin": False, "roles": ["Internal"]},
    {"email": "hr@vaultdemo.com", "password": os.environ.get("VAULT_DEMO_PASSWORD", ""), "full_name": "Priya Sharma", "department": "human_resources", "is_admin": False, "roles": ["Confidential"]},
    {"email": "intern@vaultdemo.com", "password": os.environ.get("VAULT_DEMO_PASSWORD", ""), "full_name": "Alex Kim", "department": "marketing", "is_admin": False, "roles": ["Public"]},
]

REAL_DOCUMENTS = [
    {"title": "City of Ankeny Employee Handbook (2025)", "url": "https://ankenyiowa.gov/DocumentCenter/View/403/Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Jonesboro Employee Handbook (2025)", "url": "https://www.jonesboroar.gov/DocumentCenter/View/10316/2025-Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Perrysburg Employee Handbook (EHOPP)", "url": "https://perrysburgoh.gov/DocumentCenter/View/268/Employee-Handbook-EHOPP-Revised-12312025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Georgetown Employee Handbook (2025)", "url": "https://www.georgetownky.gov/DocumentCenter/View/3212/Employee-Handbook---Revised-July-2025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of South Burlington Employee Handbook (2025)", "url": "https://www.southburlingtonvt.gov/AgendaCenter/ViewFile/Item/4742?fileID=6624", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Union City Employee Handbook (2022)", "url": "https://www.unioncityga.gov/files/assets/city/v/1/hr/documents/employee-handbook.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "NIST Cybersecurity Framework 2.0", "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2, "owner_email": "admin@vaultdemo.com"},
    {"title": "City of New Ulm Personnel Policy Manual", "url": "https://www.newulmmn.gov/DocumentCenter/View/203/Personnel-Policy-Manual-PDF?bidId", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
]


def _extract_text(pdf_bytes):
    from pypdf import PdfReader
    return "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)


def _clean(text):
    return re.sub(r'\n{3,}', '\n\n', re.sub(r' {2,}', ' ', text)).strip()[:15000]


def _download_documents():
    print("Phase 1: Downloading real-world documents...")
    fetched = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for d in REAL_DOCUMENTS:
            print(f"  {d['title']}...", end=" ")
            try:
                r = client.get(d["url"])
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                content = _extract_text(r.content) if ("pdf" in ct or d["url"].endswith(".pdf")) else re.sub(r'<[^>]+>', ' ', r.text)
                if len(content) >= 100:
                    fetched.append((d, _clean(content)))
                    print(f"OK ({len(fetched[-1][1])} chars)")
                else:
                    print("skip (short)")
            except Exception as e:
                print(f"error: {e}")
    print(f"  Downloaded {len(fetched)} documents\n")
    return fetched


def _seed_users():
    """Create the roles and the demo users, and backfill any missing role links.

    Safe to run repeatedly: existing users keep their password and their other
    attributes; only absent rows are added. Returns {email: str(user id)}.
    """
    password = os.environ.get("VAULT_DEMO_PASSWORD", "")

    with SyncSession() as session:
        role_map = {}
        for r in ROLES:
            role = session.scalar(select(Role).where(Role.name == r["name"]))
            if not role:
                role = Role(**r)
                session.add(role)
                session.flush()
            role_map[role.name] = role

        created = 0
        user_ids = {}
        for u in USERS:
            user = session.scalar(select(User).where(User.email == u["email"]))
            if user is None:
                if not password:
                    raise SystemExit(
                        "VAULT_DEMO_PASSWORD is not set -- refusing to create "
                        f"{u['email']} with an empty password.\n"
                        "Set it in server/.env, e.g. VAULT_DEMO_PASSWORD=demo1234"
                    )
                user = User(
                    email=u["email"],
                    hashed_password=get_password_hash(password),
                    full_name=u["full_name"],
                    department=u["department"],
                    is_admin=u["is_admin"],
                )
                session.add(user)
                session.flush()
                created += 1

            # Tier roles declared above, plus the corpus grants this user's
            # persona needs (admin gets "admin", intern gets intern+employee,
            # ...). Both are link-if-missing, so re-running never duplicates.
            for rn in [*u["roles"], *CORPUS_GRANTS.get(u["email"], [])]:
                if rn not in role_map:
                    continue
                link = session.scalar(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == role_map[rn].id,
                    )
                )
                if link is None:
                    session.add(UserRole(user_id=user.id, role_id=role_map[rn].id))

            user_ids[u["email"]] = str(user.id)

        # Extract IDs before commit (objects expire after)
        session.commit()

    n_users = session.scalar(select(func.count(User.id)))
    n_roles = session.scalar(select(func.count(Role.id)))
    # UserRole is a composite-key link table: it has no surrogate id column.
    n_links = session.scalar(select(func.count()).select_from(UserRole))
    print(f"  users created {created}, total {n_users}; roles {n_roles}; role links {n_links}")
    return user_ids


def _store_documents(fetched, user_ids):
    print("Phase 3: Embedding and storing documents...")
    import cohere
    from pinecone import Pinecone

    co = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    idx = pc.Index("vault", host=settings.PINECONE_INDEX_HOST)

    for doc_info, content in fetched:
        with SyncSession() as session:
            owner_id = user_ids.get(doc_info["owner_email"], list(user_ids.values())[0])

            doc = Document(title=doc_info["title"], content=content, source=doc_info["source"], account_id=doc_info["account_id"], department=doc_info["department"], access_level=doc_info["access_level"], owner_id=owner_id, doc_metadata={"tags": [], "allowed_roles": [], "allowed_users": []})
            session.add(doc)
            session.flush()

            # Simple chunking: split into ~500 char pieces
            chunk_size = 500
            text_chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

            # Batch embed (max 96 at a time for Cohere)
            vectors = []
            for batch_start in range(0, len(text_chunks), 96):
                batch = text_chunks[batch_start:batch_start+96]
                r = co.embed(texts=batch, model=settings.COHERE_EMBED_MODEL, input_type="search_document")
                for j, emb in enumerate(r.embeddings.float):
                    ci = batch_start + j
                    session.add(DocumentChunk(document_id=doc.id, content=text_chunks[ci], chunk_index=ci))
                    vectors.append({"id": f"{doc.id}-chunk-{ci}", "values": emb, "metadata": {"content": text_chunks[ci][:500], "document_id": str(doc.id), "title": doc_info["title"], "source": doc_info["source"], "account_id": doc_info["account_id"], "department": doc_info["department"], "access_level": doc_info["access_level"], "owner_id": owner_id}})

            session.commit()

            if vectors:
                idx.upsert(vectors=vectors)

            print(f"  {doc_info['title']}: {len(text_chunks)} chunks")


def seed():
    from app.db.sessions import Base
    Base.metadata.create_all(bind=_sync_engine)

    with SyncSession() as session:
        count = session.scalar(select(func.count(Document.id))) or 0

    # Only ingest into an empty corpus; a populated one must never be
    # re-ingested, but it also must not stop the user/role seeding below.
    fetched = []
    if count >= 5:
        print(f"Corpus already populated ({count:,} documents): skipping Phase 1 and Phase 3.")
    else:
        fetched = _download_documents()

    print("Phase 2: Creating users and roles...")
    user_ids = _seed_users()
    print("  Done\n")

    if fetched:
        _store_documents(fetched, user_ids)

    print("\nDone!")


if __name__ == "__main__":
    seed()
