"""
Seed real-world public enterprise documents into Vault.
Fetches actual government handbooks, NIST frameworks, and CISA guides.
"""
import asyncio
import io
import re
from datetime import datetime
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
    {
        "email": "admin@vaultdemo.com",
        "password": "demo1234",
        "full_name": "Sarah Chen",
        "department": "engineering",
        "is_admin": True,
        "roles": ["Confidential"],
    },
    {
        "email": "engineer@vaultdemo.com",
        "password": "demo1234",
        "full_name": "Marcus Johnson",
        "department": "engineering",
        "is_admin": False,
        "roles": ["Internal"],
    },
    {
        "email": "hr@vaultdemo.com",
        "password": "demo1234",
        "full_name": "Priya Sharma",
        "department": "human_resources",
        "is_admin": False,
        "roles": ["Confidential"],
    },
    {
        "email": "intern@vaultdemo.com",
        "password": "demo1234",
        "full_name": "Alex Kim",
        "department": "marketing",
        "is_admin": False,
        "roles": ["Public"],
    },
]

# Real-world public documents with their URLs and metadata
REAL_DOCUMENTS = [
    {
        "title": "City of Ankeny Employee Handbook (2025)",
        "url": "https://ankenyiowa.gov/DocumentCenter/View/403/Employee-Handbook-PDF",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 0,  # PUBLIC - government handbook
        "owner_email": "hr@vaultdemo.com",
        "description": "Official employee handbook for the City of Ankeny, Iowa. Covers employment policies, benefits, conduct standards, and workplace safety.",
    },
    {
        "title": "City of Jonesboro Employee Handbook (2025)",
        "url": "https://www.jonesboroar.gov/DocumentCenter/View/10316/2025-Employee-Handbook-PDF",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 0,  # PUBLIC
        "owner_email": "hr@vaultdemo.com",
        "description": "Employee handbook for the City of Jonesboro, Arkansas. Includes drug-free workplace policies, attendance, and benefits.",
    },
    {
        "title": "City of Perrysburg Employee Handbook (EHOPP)",
        "url": "https://perrysburgoh.gov/DocumentCenter/View/268/Employee-Handbook-EHOPP-Revised-12312025-PDF",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 1,  # INTERNAL
        "owner_email": "hr@vaultdemo.com",
        "description": "Comprehensive personnel policies for the City of Perrysburg, Ohio. Covers employment terms, workplace conduct, and benefits administration.",
    },
    {
        "title": "City of Georgetown Employee Handbook (2025)",
        "url": "https://www.georgetownky.gov/DocumentCenter/View/3212/Employee-Handbook---Revised-July-2025-PDF",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 1,  # INTERNAL
        "owner_email": "hr@vaultdemo.com",
        "description": "Employee handbook for Georgetown, Kentucky. Details city government organization, employment policies, and core values.",
    },
    {
        "title": "City of South Burlington Employee Handbook (2025)",
        "url": "https://www.southburlingtonvt.gov/AgendaCenter/ViewFile/Item/4742?fileID=6624",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 1,  # INTERNAL
        "owner_email": "hr@vaultdemo.com",
        "description": "Employee handbook for South Burlington, Vermont. Covers fair employment practices, anti-discrimination policies, and employee rights.",
    },
    {
        "title": "City of Union City Employee Handbook (2022)",
        "url": "https://www.unioncityga.gov/files/assets/city/v/1/hr/documents/employee-handbook.pdf",
        "source": "policy",
        "account_id": "municipal",
        "department": "human_resources",
        "access_level": 1,  # INTERNAL
        "owner_email": "hr@vaultdemo.com",
        "description": "Employee handbook for Union City, Georgia. Includes privacy policies, smoking policies, and recognition programs.",
    },
    {
        "title": "NIST Cybersecurity Framework 2.0",
        "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        "source": "compliance",
        "account_id": "security",
        "department": "engineering",
        "access_level": 2,  # CONFIDENTIAL
        "owner_email": "admin@vaultdemo.com",
        "description": "NIST Cybersecurity Framework version 2.0. Provides guidance for managing cybersecurity risks across govern, identify, protect, detect, respond, and recover functions.",
    },
    {
        "title": "CISA Incident Response Plan Basics",
        "url": "https://www.cisa.gov/sites/default/files/publications/Incident-Response-Plan-Basics_508c.pdf",
        "source": "security",
        "account_id": "security",
        "department": "engineering",
        "access_level": 2,  # CONFIDENTIAL
        "owner_email": "admin@vaultdemo.com",
        "description": "CISA guide on incident response planning. Covers before, during, and after cybersecurity incidents with practical recommendations.",
    },
    {
        "title": "NIST SP 800-61 Rev.3 Incident Response Guide",
        "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        "source": "compliance",
        "account_id": "security",
        "department": "engineering",
        "access_level": 3,  # RESTRICTED
        "owner_email": "admin@vaultdemo.com",
        "description": "NIST Special Publication 800-61 Revision 3. Detailed incident response recommendations and considerations for cybersecurity risk management.",
    },
    {
        "title": "CISA Federal Cybersecurity Incident Response Playbook",
        "url": "https://www.cisa.gov/sites/default/files/publications/NCIRP-Summary_508.pdf",
        "source": "security",
        "account_id": "security",
        "department": "engineering",
        "access_level": 3,  # RESTRICTED
        "owner_email": "admin@vaultdemo.com",
        "description": "National Cyber Incident Response Plan summary. Describes the national approach to dealing with cyber incidents involving federal agencies.",
    },
]


async def _get_embedding(text: str) -> list[float]:
    """Get Cohere embedding for text."""
    client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    response = client.embed(
        texts=[text],
        model=settings.COHERE_EMBED_MODEL,
        input_type="search_document",
    )
    return response.embeddings.float[0]


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"  PDF extraction error: {e}")
        return ""


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    # Remove common PDF artifacts
    text = re.sub(r'\x00', '', text)
    return text.strip()


async def _fetch_document(url: str, timeout: float = 30.0) -> str:
    """Fetch document content from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        
        if "pdf" in content_type or url.endswith(".pdf"):
            return _extract_text_from_pdf(response.content)
        elif "html" in content_type:
            # Basic HTML text extraction
            text = response.text
            # Remove script and style elements
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        else:
            return response.text


async def seed_real_data():
    """Seed real-world public documents."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(func.count(Document.id)))
        doc_count = result.scalar()
        if doc_count and doc_count >= 5:
            print(f"Already seeded ({doc_count} documents). Skipping.")
            return False

        print("Seeding real-world enterprise documents...")

        # 1. Create roles
        role_map = {}
        for role_data in ROLES:
            result = await session.execute(
                select(Role).where(Role.name == role_data["name"])
            )
            role = result.scalar_one_or_none()
            if not role:
                role = Role(**role_data)
                session.add(role)
                await session.flush()
            role_map[role.name] = role
        print(f"  Roles: {len(role_map)} created/found")

        # 2. Create users
        user_map = {}
        for user_data in USERS:
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    full_name=user_data["full_name"],
                    department=user_data["department"],
                    is_admin=user_data["is_admin"],
                )
                session.add(user)
                await session.flush()

                # Assign roles
                for role_name in user_data["roles"]:
                    if role_name in role_map:
                        user_role = UserRole(user_id=user.id, role_id=role_map[role_name].id)
                        session.add(user_role)

            user_map[user_data["email"]] = user
        print(f"  Users: {len(user_map)} created/found")

        # 3. Fetch and seed real-world documents
        docs_created = 0
        for doc_info in REAL_DOCUMENTS:
            # Skip if document already exists
            result = await session.execute(
                select(Document).where(Document.title == doc_info["title"])
            )
            if result.scalar_one_or_none():
                print(f"  Skipping (exists): {doc_info['title']}")
                continue

            print(f"  Fetching: {doc_info['title']}...")
            try:
                content = await _fetch_document(doc_info["url"])
                if not content or len(content) < 100:
                    print(f"    Warning: Content too short ({len(content)} chars), skipping")
                    continue
                
                # Truncate very long documents
                if len(content) > 50000:
                    content = content[:50000]
                    print(f"    Truncated to 50,000 chars")

                content = _clean_text(content)
                owner = user_map.get(doc_info["owner_email"])
                owner_id = str(owner.id) if owner else str(list(user_map.values())[0].id)

                doc = Document(
                    title=doc_info["title"],
                    content=content,
                    source=doc_info["source"],
                    account_id=doc_info["account_id"],
                    department=doc_info["department"],
                    access_level=doc_info["access_level"],
                    owner_id=owner_id,
                    doc_metadata={
                        "description": doc_info["description"],
                        "url": doc_info["url"],
                        "tags": [],
                        "allowed_roles": [],
                        "allowed_users": [],
                    },
                )
                session.add(doc)
                await session.flush()

                # Chunk document
                from app.ingestion.chunker import SemanticChunker
                chunker = SemanticChunker()
                chunks = chunker.chunk(content=content, document_id=str(doc.id))

                # Embed and store chunks
                pinecone_vectors = []
                for i, chunk in enumerate(chunks):
                    try:
                        embedding = await _get_embedding(chunk.content)
                        pinecone_vectors.append({
                            "id": f"{doc.id}-chunk-{i}",
                            "values": embedding,
                            "metadata": {
                                "content": chunk.content[:500],
                                "document_id": str(doc.id),
                                "title": doc_info["title"],
                                "source": doc_info["source"],
                                "account_id": doc_info["account_id"],
                                "department": doc_info["department"],
                                "access_level": doc_info["access_level"],
                                "owner_id": owner_id,
                            },
                        })
                    except Exception as e:
                        print(f"    Embedding error: {e}")

                # Store chunks in DB
                for i, chunk in enumerate(chunks):
                    doc_chunk = DocumentChunk(
                        document_id=doc.id,
                        content=chunk.content,
                        chunk_index=i,
                    )
                    session.add(doc_chunk)

                # Upsert to Pinecone
                if pinecone_vectors:
                    await pinecone_client.upsert_vectors(vectors=pinecone_vectors)

                docs_created += 1
                print(f"    OK: {len(chunks)} chunks, {len(pinecone_vectors)} vectors")

            except Exception as e:
                print(f"    Error: {e}")

        await session.commit()
        print(f"\nSeed complete: {docs_created} real-world documents ingested")
        return True


if __name__ == "__main__":
    asyncio.run(seed_real_data())
