"""
Local seed script for Vault - synchronous version (avoids Neon pooler issues).
Run: cd backend && python -m scripts.seed_local
"""
import io
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session, sessionmaker
from app.db.models import User, Role, UserRole, Document, DocumentChunk
from app.auth.jwt import get_password_hash
from app.config import settings
import httpx
import cohere

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


def seed():
    from app.db.sessions import Base
    Base.metadata.create_all(bind=_sync_engine)

    with SyncSession() as session:
        count = session.scalar(select(func.count(Document.id)))
        if count and count >= 5:
            print("Already seeded. Skipping.")
            return

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

    print("Phase 2: Creating users and roles...")
    with SyncSession() as session:
        role_map = {}
        for r in ROLES:
            role = session.scalar(select(Role).where(Role.name == r["name"]))
            if not role:
                role = Role(**r)
                session.add(role)
                session.flush()
            role_map[role.name] = role

        user_map = {}
        for u in USERS:
            user = session.scalar(select(User).where(User.email == u["email"]))
            if not user:
                user = User(email=u["email"], hashed_password=get_password_hash(u["password"]), full_name=u["full_name"], department=u["department"], is_admin=u["is_admin"])
                session.add(user)
                session.flush()
                for rn in u["roles"]:
                    if rn in role_map:
                        session.add(UserRole(user_id=user.id, role_id=role_map[rn].id))
            user_map[u["email"]] = user
        # Extract IDs before commit (objects expire after)
        user_ids = {email: str(u.id) for email, u in user_map.items()}
        session.commit()
    print("  Done\n")

    print("Phase 3: Embedding and storing documents...")
    co = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    from pinecone import Pinecone
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

    print("\nDone!")


if __name__ == "__main__":
    seed()
