"""
Improved seed: section-aware chunking with keyword extraction.
Run: cd server && python -m scripts.seed_v2
"""
import io
import os
import re
import sys
import math
import httpx
import cohere
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session, sessionmaker
from app.db.models import User, Role, UserRole, Document, DocumentChunk
from app.auth.jwt import get_password_hash
from app.config import settings

# Sync engine (direct Neon, not pooler)
_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").replace("postgres://", "postgresql+psycopg2://")
_db_url = _db_url.replace("-pooler", "")
_sync_engine = create_engine(_db_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_sync_engine)

# ---------- Document registry ----------

ORIGINAL_DOCS = [
    {"title": "City of Ankeny Employee Handbook (2025)", "url": "https://ankenyiowa.gov/DocumentCenter/View/403/Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Jonesboro Employee Handbook (2025)", "url": "https://www.jonesboroar.gov/DocumentCenter/View/10316/2025-Employee-Handbook-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Perrysburg Employee Handbook (EHOPP)", "url": "https://perrysburgoh.gov/DocumentCenter/View/268/Employee-Handbook-EHOPP-Revised-12312025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Georgetown Employee Handbook (2025)", "url": "https://www.georgetownky.gov/DocumentCenter/View/3212/Employee-Handbook---Revised-July-2025-PDF", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of South Burlington Employee Handbook (2025)", "url": "https://www.southburlingtonvt.gov/AgendaCenter/ViewFile/Item/4742?fileID=6624", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "City of Union City Employee Handbook (2022)", "url": "https://www.unioncityga.gov/files/assets/city/v/1/hr/documents/employee-handbook.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "NIST Cybersecurity Framework 2.0", "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2, "owner_email": "admin@vaultdemo.com"},
    {"title": "City of New Ulm Personnel Policy Manual", "url": "https://www.newulmmn.gov/DocumentCenter/View/203/Personnel-Policy-Manual-PDF?bidId", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
]

NEW_DOCS = [
    {"title": "City of Sammamish Employee Handbook (2024)", "file": "downloads/doc_1.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "Grapevine-Colleyville ISD Employee Handbook (2025)", "file": "downloads/doc_3.pdf", "source": "policy", "account_id": "education", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "Plaza Healthcare Employee Handbook (2024)", "file": "downloads/doc_4.pdf", "source": "policy", "account_id": "healthcare", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "HF Foods Group Employee Handbook (2024)", "file": "downloads/doc_5.pdf", "source": "policy", "account_id": "corporate", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "GreenWaste Employee Handbook (2024)", "file": "downloads/doc_6.pdf", "source": "policy", "account_id": "corporate", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "NIST CSF Policy Template Guide (2024)", "file": "downloads/doc_9.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2, "owner_email": "admin@vaultdemo.com"},
    {"title": "Mississippi State Employee Handbook (2024)", "file": "downloads/doc_11.pdf", "source": "policy", "account_id": "state_gov", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
    {"title": "Howard County Employee Handbook (2024)", "file": "downloads/doc_12.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1, "owner_email": "hr@vaultdemo.com"},
    {"title": "West Virginia Dept of Administration Handbook", "file": "downloads/doc_13.pdf", "source": "policy", "account_id": "state_gov", "department": "human_resources", "access_level": 0, "owner_email": "hr@vaultdemo.com"},
]

USERS = [
    {"email": "admin@vaultdemo.com", "password": "demo1234", "full_name": "Sarah Chen", "department": "engineering", "is_admin": True, "roles": ["Confidential"]},
    {"email": "engineer@vaultdemo.com", "password": "demo1234", "full_name": "Marcus Johnson", "department": "engineering", "is_admin": False, "roles": ["Internal"]},
    {"email": "hr@vaultdemo.com", "password": "demo1234", "full_name": "Priya Sharma", "department": "human_resources", "is_admin": False, "roles": ["Confidential"]},
    {"email": "intern@vaultdemo.com", "password": "demo1234", "full_name": "Alex Kim", "department": "marketing", "is_admin": False, "roles": ["Public"]},
]

ROLES = [
    {"name": "Public", "description": "All authenticated users", "access_level": 0},
    {"name": "Internal", "description": "Department-scoped access", "access_level": 1},
    {"name": "Confidential", "description": "Account-scoped access", "access_level": 2},
    {"name": "Restricted", "description": "Named-user only access", "access_level": 3},
]


# ---------- Section-aware chunking ----------

# Patterns that detect section headers in documents
SECTION_PATTERNS = [
    # "Section 1:", "SECTION 1.", "Section I:", "Section 1 -"
    r'^(?:SECTION|Section|section)\s+(?:[IVXLC]+|\d+(?:\.\d+)*)\s*[:.\-\s]',
    # "Chapter 1:", "CHAPTER 2."
    r'^(?:CHAPTER|Chapter|chapter)\s+\d+',
    # "1. Title" or "1.1 Title" at start of line
    r'^\d+(?:\.\d+){0,2}\s+[A-Z]',
    # "ARTICLE I", "ARTICLE 1"
    r'^(?:ARTICLE|Article)\s+(?:[IVXLC]+|\d+)',
    # All-caps lines that look like headers (min 3 words, max 80 chars)
    r'^[A-Z][A-Z\s]{5,80}$',
    # "Part 1:", "PART I:"
    r'^(?:PART|Part)\s+(?:[IVXLC]+|\d+)',
    # Table of Contents style: "Policy Name .......... 12"
    r'^[A-Z][A-Za-z\s&\-]{3,60}\s*\.{2,}',
    # Bullet point sections: "- Leave Policy" or "• Safety"
    r'^[\-\•\●]\s+[A-Z]',
    # "Appendix A"
    r'^APPENDIX\s+[A-Z]',
]

# Topic keywords for cluster routing
TOPIC_KEYWORDS = {
    "leave": ["leave", "vacation", "sick leave", "personal day", "holiday", "absence", "pto", "time off", "fmla", "family medical"],
    "conduct": ["conduct", "ethics", "behavior", "discipline", "termination", "dismissal", "firing", "rules", "standards"],
    "harassment": ["harassment", "discrimination", "retaliation", "hostile", "title ix", "sexual harassment", "equal employment"],
    "safety": ["safety", "security", "emergency", "evacuation", "fire", "hazard", "injury", "accident", "osha", "workplace violence"],
    "benefits": ["benefits", "insurance", "health", "dental", "vision", "retirement", "pension", "401k", "life insurance", "disability"],
    "compensation": ["compensation", "salary", "wage", "overtime", "pay", "payroll", "bonus", "raise", "classification"],
    "remote_work": ["remote", "telework", "telecommute", "work from home", "flexible", "hybrid", "distance"],
    "compliance": ["compliance", "regulation", "policy", "framework", "audit", "nist", "iso", "hipaa", "gdpr", "soc2"],
    "security": ["security", "information security", "cybersecurity", "password", "encryption", "access control", "firewall", "incident"],
    "drugs": ["drug", "alcohol", "substance", "testing", "drug-free", "intoxication", "impairment"],
    "technology": ["computer", "email", "internet", "technology", "software", "hardware", "network", "byod", "social media"],
    "attendance": ["attendance", "punctuality", "tardiness", "absent", "scheduling", "shift", "hours of work"],
    "training": ["training", "orientation", "development", "education", "certification", "professional development"],
    "grievance": ["grievance", "complaint", "appeal", "dispute", "resolution", "whistleblower", "reporting"],
    "onboarding": ["hiring", "onboarding", "orientation", "probation", "employment", "at-will", "classification"],
    "communication": ["communication", "appearance", "dress code", "uniform", "presentation", "public image"],
}


def extract_text_from_pdf(pdf_path: str) -> str:
    from pypdf import PdfReader
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)


def extract_text_from_url(url: str) -> str:
    import httpx as hx
    with hx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "pdf" in ct or url.endswith(".pdf"):
            from pypdf import PdfReader
            return "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
        return re.sub(r'<[^>]+>', ' ', r.text)


def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def is_section_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 120:
        return False
    for pattern in SECTION_PATTERNS:
        if re.match(pattern, line):
            return True
    return False


def extract_keywords(text: str) -> list[str]:
    """Extract topic keywords from text for cluster routing."""
    text_lower = text.lower()
    found = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(topic)
                break
    return found


def extract_section_keywords(title: str, content: str) -> list[str]:
    """Extract specific keyword phrases from section content."""
    keywords = set()
    combined = (title + " " + content).lower()

    # Direct keyword matching
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in combined:
                keywords.add(topic)

    # Extract capitalized terms that appear in the title
    title_words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', title)
    for w in title_words:
        if len(w) > 2:
            keywords.add(w.lower())

    return sorted(keywords)


def section_chunk(text: str, max_chars: int = 1500, overlap: int = 300) -> list[dict]:
    """
    Chunk text by section headers, falling back to paragraph-aware chunking.
    Returns list of {title, content, keywords}.
    """
    lines = text.split('\n')
    sections = []
    current_title = "Introduction"
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if is_section_header(stripped) and len(current_lines) > 2:
            # Save current section
            content = '\n'.join(current_lines).strip()
            if len(content) > 50:
                sections.append({"title": current_title, "content": content})
            current_title = stripped
            current_lines = [stripped]
        else:
            current_lines.append(line)

    # Save last section
    if current_lines:
        content = '\n'.join(current_lines).strip()
        if len(content) > 50:
            sections.append({"title": current_title, "content": content})

    # If no sections found, chunk by paragraphs
    if not sections:
        paragraphs = re.split(r'\n\s*\n', text)
        merged = []
        buf = ""
        for p in paragraphs:
            if len(buf) + len(p) < max_chars:
                buf += "\n\n" + p if buf else p
            else:
                if buf:
                    merged.append(buf)
                buf = p
        if buf:
            merged.append(buf)

        sections = []
        for i, chunk in enumerate(merged):
            sections.append({"title": f"Section {i+1}", "content": chunk})

    # Now split oversized sections
    chunks = []
    for section in sections:
        content = section["content"]
        if len(content) <= max_chars:
            keywords = extract_section_keywords(section["title"], content)
            chunks.append({
                "title": section["title"],
                "content": content,
                "keywords": keywords,
            })
        else:
            # Split by paragraphs within the section
            paragraphs = re.split(r'\n\s*\n', content)
            buf = ""
            part_num = 1
            for p in paragraphs:
                if len(buf) + len(p) < max_chars:
                    buf += "\n\n" + p if buf else p
                else:
                    if buf:
                        # Add overlap from end of previous chunk
                        overlap_text = buf[-overlap:] if len(buf) > overlap else ""
                        keywords = extract_section_keywords(section["title"], buf)
                        chunks.append({
                            "title": f"{section['title']} (part {part_num})" if part_num > 1 else section["title"],
                            "content": buf,
                            "keywords": keywords,
                        })
                        part_num += 1
                        buf = (overlap_text + "\n\n" + p).strip()
                    else:
                        buf = p
            if buf:
                keywords = extract_section_keywords(section["title"], buf)
                chunks.append({
                    "title": f"{section['title']} (part {part_num})" if part_num > 1 else section["title"],
                    "content": buf,
                    "keywords": keywords,
                })

    return chunks


# ---------- Roles & Users ----------

def setup_roles_and_users():
    from app.db.sessions import Base
    Base.metadata.create_all(bind=_sync_engine)

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
                user = User(
                    email=u["email"],
                    hashed_password=get_password_hash(u["password"]),
                    full_name=u["full_name"],
                    department=u["department"],
                    is_admin=u["is_admin"],
                )
                session.add(user)
                session.flush()
                for rn in u["roles"]:
                    if rn in role_map:
                        session.add(UserRole(user_id=user.id, role_id=role_map[rn].id))
            user_map[u["email"]] = user

        user_ids = {email: str(u.id) for email, u in user_map.items()}
        session.commit()
    return user_ids


# ---------- Main seed ----------

def seed():
    from app.db.sessions import Base
    Base.metadata.create_all(bind=_sync_engine)

    print("Setting up roles and users...")
    user_ids = setup_roles_and_users()
    print(f"  {len(user_ids)} users ready\n")

    # Check existing docs
    with SyncSession() as session:
        existing_titles = set(session.scalars(select(Document.title)).all())
        if existing_titles:
            print(f"Found {len(existing_titles)} existing documents. Will skip those.\n")

    co = cohere.ClientV2(api_key=settings.COHERE_API_KEY)
    from pinecone import Pinecone
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    idx = pc.Index("vault", host=settings.PINECONE_INDEX_HOST)

    # Delete existing vectors
    print("Clearing Pinecone index...")
    try:
        idx.delete(delete_all=True)
    except Exception:
        pass

    all_docs = ORIGINAL_DOCS + NEW_DOCS
    total_chunks = 0

    for doc_i, doc_info in enumerate(all_docs):
        is_new = doc_i >= len(ORIGINAL_DOCS)
        label = f"[{doc_i+1}/{len(all_docs)}]"

        # Skip if already seeded
        if doc_info["title"] in existing_titles:
            print(f"{label} {doc_info['title']}... SKIP (already seeded)")
            continue
        print(f"{label} {doc_info['title']}...", end=" ", flush=True)

        try:
            if is_new and "file" in doc_info:
                raw_text = extract_text_from_pdf(doc_info["file"])
            else:
                raw_text = extract_text_from_url(doc_info["url"])

            cleaned = clean_text(raw_text)
            if len(cleaned) < 100:
                print("SKIP (too short)")
                continue
        except Exception as e:
            print(f"FAIL ({e})")
            continue

        # Section-aware chunking
        chunks = section_chunk(cleaned, max_chars=1500, overlap=300)
        if not chunks:
            print("SKIP (no chunks)")
            continue

        owner_id = user_ids.get(doc_info.get("owner_email", ""), list(user_ids.values())[0])

        with SyncSession() as session:
            doc = Document(
                title=doc_info["title"],
                content=cleaned[:15000],
                source=doc_info["source"],
                account_id=doc_info["account_id"],
                department=doc_info["department"],
                access_level=doc_info["access_level"],
                owner_id=owner_id,
                doc_metadata={"tags": [], "chunk_count": len(chunks)},
            )
            session.add(doc)
            session.flush()

            # Batch embed
            vectors = []
            texts_to_embed = [c["content"][:2000] for c in chunks]
            for batch_start in range(0, len(texts_to_embed), 96):
                batch = texts_to_embed[batch_start:batch_start+96]
                r = co.embed(texts=batch, model=settings.COHERE_EMBED_MODEL, input_type="search_document")
                for j, emb in enumerate(r.embeddings.float):
                    ci = batch_start + j
                    chunk = chunks[ci]
                    session.add(DocumentChunk(
                        document_id=doc.id,
                        content=chunk["content"],
                        chunk_index=ci,
                    ))
                    vectors.append({
                        "id": f"{doc.id}-chunk-{ci}",
                        "values": emb,
                        "metadata": {
                            "content": chunk["content"][:1500],
                            "document_id": str(doc.id),
                            "title": doc_info["title"],
                            "source": doc_info["source"],
                            "account_id": doc_info["account_id"],
                            "department": doc_info["department"],
                            "access_level": doc_info["access_level"],
                            "owner_id": owner_id,
                            "section_title": chunk["title"],
                            "keywords": ",".join(chunk["keywords"]),
                        },
                    })

            session.commit()

            if vectors:
                idx.upsert(vectors=vectors)

            total_chunks += len(chunks)
            all_kw = set(kw for c in chunks for kw in c["keywords"])
            print(f" -> {len(chunks)} chunks, keywords: {all_kw}")

    print(f"\nDone! {len(all_docs)} documents, {total_chunks} total chunks")


if __name__ == "__main__":
    seed()
