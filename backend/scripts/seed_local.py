"""
Local seed script for Vault.
Run: cd backend && python -m scripts.seed_local

Downloads real-world public enterprise documents, embeds them, and seeds the DB.
Data persists in Neon DB across Vercel deployments.
"""
import asyncio
import io
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.db.sessions import async_session, engine, Base
from app.db.models import User, Role, UserRole, Document, DocumentChunk
from app.db.pinecone import pinecone_client
from app.auth.jwt import get_password_hash
from app.config import settings
import httpx
import cohere


ROLES = [
    {"name": "Public", "description": "All authenticated users", "access_level": 0},
    {"name": "Internal", "description": "Department-scoped access", "access_level": 1},
    {"name": "Confidential", "description": "Account-scoped access", "access_level": 2},
    {"name": "Restricted", "description": "Named-user only access", "access_level": 3},
]

USERS = [
    {"email": "admin@vaultdemo.com", "password": "demo1234", "full_name": "Sarah Chen", "department": "engineering", "is_admin": True, "roles": ["Confidential"]},
    {"email": "engineer@vaultdemo.com", "password": "demo1234", "full_name": "Marcus Johnson", "department": "engineering", "is_admin": False, "roles": ["Internal"]},
    {"email": "hr@vaultdemo.com", "password": "demo1234", "full_name": "Priya Sharma", "department": "human_resources", "is_admin": False, "roles": ["Confidential"]},
    {"email": "intern@vaultdemo.com", "password": "demo1234", "full_name": "Alex Kim", "department": "marketing", "is_admin": False, "roles": ["Public"]},
]

REAL_DOCUMENTS = [
    {"title": "City of Ankeny Employee Handbook (2025)", "url": "https://ankenyiowa.gov/DocumentCenter/View/403/Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Jonesboro Employee Handbook (2025)", "url": "https://www.jonesboroar.gov/DocumentCenter/View/10316/2025-Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Perrysburg Employee Handbook (EHOPP)", "url": "https://perrysburgoh.gov/DocumentCenter/View/268/Employee-Handbook-EHOPP-Revised-12312025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Georgetown Employee Handbook (2025)", "url": "https://www.georgetownky.gov/DocumentCenter/View/3212/Employee-Handbook---Revised-July-2025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of South Burlington Employee Handbook (2025)", "url": "https://www.southburlingtonvt.gov/AgendaCenter/ViewFile/Item/4742?fileID=6624", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Union City Employee Handbook (2022)", "url": "https://www.unioncityga.gov/files/assets/city/v/1/hr/documents/employee-handbook.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "NIST Cybersecurity Framework 2.0", "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2, "owner_email": "admin@vaultdemo.com"},
    {"title": "CISA Incident Response Plan Basics", "url": "https://www.cisa.gov/sites/default/files/publications/Incident-Response-Plan-Basics_508c.pdf", "source": "security", "account_id": "security", "department": "engineering", "access_level": 2, "owner_email": "admin@vaultdemo.com"},
    {"title": "CISA Federal Cybersecurity Incident Response Playbook", "url": "https://www.cisa.gov/sites/default/files/publications/NCIRP-Summary_508.pdf", "source": "security", "account_id": "security", "department": "engineering", "access_level": 3, "owner_email": "admin@vaultdemo.com"},
    {"title": "City of New Ulm Personnel Policy Manual", "url": "https://www.newulmmn.gov/DocumentCenter/View/203/Personnel-Policy-Manual-PDF?bidId", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
]


async def _get_embedding(text: str) -> list[float]:
    client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    response = client.embed(texts=[text], model=settings.COHERE_EMBED_MODEL, input_type="search_document")
    return response.embeddings.float[0]


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"  PDF error: {e}")
        return ""


def _clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        result = await session.execute(select(func.count(Document.id)))
        if result.scalar() and result.scalar() >= 5:
            print("Already seeded. Skipping.")
            return

        print("Seeding real-world enterprise documents...")

        role_map = {}
        for r in ROLES:
            result = await session.execute(select(Role).where(Role.name == r["name"]))
            role = result.scalar_one_or_none()
            if not role:
                role = Role(**r)
                session.add(role)
                await session.flush()
            role_map[role.name] = role

        user_map = {}
        for u in USERS:
            result = await session.execute(select(User).where(User.email == u["email"]))
            user = result.scalar_one_or_none()
            if not user:
                user = User(email=u["email"], hashed_password=get_password_hash(u["password"]), full_name=u["full_name"], department=u["department"], is_admin=u["is_admin"])
                session.add(user)
                await session.flush()
                for rn in u["roles"]:
                    if rn in role_map:
                        session.add(UserRole(user_id=user.id, role_id=role_map[rn].id))
            user_map[u["email"]] = user

        for doc_info in REAL_DOCUMENTS:
            result = await session.execute(select(Document).where(Document.title == doc_info["title"]))
            if result.scalar_one_or_none():
                print(f"  Skip (exists): {doc_info['title']}")
                continue

            print(f"  Fetching: {doc_info['title']}...")
            try:
                async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                    resp = await client.get(doc_info["url"])
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "")
                    if "pdf" in ct or doc_info["url"].endswith(".pdf"):
                        content = _extract_text_from_pdf(resp.content)
                    else:
                        text = resp.text
                        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        content = re.sub(r'\s+', ' ', text).strip()

                if not content or len(content) < 100:
                    print(f"    Too short ({len(content)} chars), skipping")
                    continue
                content = _clean_text(content[:50000])

                owner = user_map.get(doc_info["owner_email"])
                owner_id = str(owner.id) if owner else str(list(user_map.values())[0].id)

                doc = Document(title=doc_info["title"], content=content, source=doc_info["source"], account_id=doc_info["account_id"], department=doc_info["department"], access_level=doc_info["access_level"], owner_id=owner_id, doc_metadata={"tags": [], "allowed_roles": [], "allowed_users": []})
                session.add(doc)
                await session.flush()

                from app.ingestion.chunker import SemanticChunker
                chunks = SemanticChunker().chunk(content=content, document_id=str(doc.id))

                vectors = []
                for i, chunk in enumerate(chunks):
                    try:
                        emb = await _get_embedding(chunk.content)
                        vectors.append({"id": f"{doc.id}-chunk-{i}", "values": emb, "metadata": {"content": chunk.content[:500], "document_id": str(doc.id), "title": doc_info["title"], "source": doc_info["source"], "account_id": doc_info["account_id"], "department": doc_info["department"], "access_level": doc_info["access_level"], "owner_id": owner_id}})
                    except Exception as e:
                        print(f"    Embed error: {e}")

                for i, chunk in enumerate(chunks):
                    session.add(DocumentChunk(document_id=doc.id, content=chunk.content, chunk_index=i))

                if vectors:
                    await pinecone_client.upsert_vectors(vectors=vectors)

                print(f"    OK: {len(chunks)} chunks, {len(vectors)} vectors")
            except Exception as e:
                print(f"    Error: {e}")

        await session.commit()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(seed())
