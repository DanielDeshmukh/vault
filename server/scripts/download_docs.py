"""Download new documents for expanded corpus."""
import httpx
import os
import io
from pypdf import PdfReader

DOCS = [
    {"title": "County of Powhatan Employee Handbook (2024)", "url": "https://www.powhatanva.gov/DocumentCenter/View/8334/Employee-Handbook---Effective-May-1-2024", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1},
    {"title": "City of Sammamish Employee Handbook (2024)", "url": "https://mrsc.org/getmedia/d2dec8e7-c174-42aa-ab9a-27e34b5ffb36/s35employeehandbk.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1},
    {"title": "Des Moines Public Schools Employee Handbook (2025)", "url": "https://www.dmschools.org/wp-content/uploads/2025/10/Employee-Information-Handbook-2025-2026-Revised.pdf", "source": "policy", "account_id": "education", "department": "human_resources", "access_level": 0},
    {"title": "Grapevine-Colleyville ISD Employee Handbook (2025)", "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/3776/Gcisd/21ce14f7-5019-4f71-bfe5-920bab2fe395/25-26-Employee-Handbook.pdf?disposition=inline", "source": "policy", "account_id": "education", "department": "human_resources", "access_level": 0},
    {"title": "Plaza Healthcare Employee Handbook (2024)", "url": "https://irp.cdn-website.com/0d2ad0a4/files/uploaded/Handbook_2025+Final.pdf", "source": "policy", "account_id": "healthcare", "department": "human_resources", "access_level": 1},
    {"title": "HF Foods Group Employee Handbook (2024)", "url": "https://portal.hffoodsgroup.com/wp-content/uploads/2024/03/HF-Employee-Handbook_2024-FINAL.pdf", "source": "policy", "account_id": "corporate", "department": "human_resources", "access_level": 1},
    {"title": "GreenWaste Employee Handbook (2024)", "url": "https://www.greenwaste.com/wp-content/uploads/GreenWaste-2024-Employee-Handbook.pdf", "source": "policy", "account_id": "corporate", "department": "human_resources", "access_level": 0},
    {"title": "Metro Atlanta Chamber Employee Handbook (2024)", "url": "https://www.metroatlantachamber.com/wp-content/uploads/2024/05/Employee-Handbook-2024-FINAL-5.14.24.pdf", "source": "policy", "account_id": "corporate", "department": "human_resources", "access_level": 1},
    {"title": "Arizona Information Security Policy", "url": "https://www.azed.gov/sites/default/files/2023/03/09.%20Template%20Information-Security-Policy.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2},
    {"title": "NIST CSF Policy Template Guide (2024)", "url": "https://www.cisecurity.org/-/media/project/cisecurity/cisecurity/data/media/files/uploads/2024/08/cis-ms-isac-nist-cybersecurity-framework-policy-template-guide-2024.pdf", "source": "compliance", "account_id": "security", "department": "engineering", "access_level": 2},
]

os.makedirs("downloads", exist_ok=True)

for i, d in enumerate(DOCS):
    fname = f"downloads/doc_{i}.pdf"
    print(f"[{i+1}/10] {d['title']}...", end=" ", flush=True)
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            r = client.get(d["url"])
            r.raise_for_status()
            with open(fname, "wb") as f:
                f.write(r.content)
            ct = r.headers.get("content-type", "")
            size = len(r.content)
            print(f"OK ({size:,} bytes)")
    except Exception as e:
        print(f"FAIL: {e}")

# Verify PDFs are readable
print("\n--- Verification ---")
for i in range(10):
    fname = f"downloads/doc_{i}.pdf"
    if not os.path.exists(fname):
        print(f"doc_{i}.pdf: MISSING")
        continue
    try:
        with open(fname, "rb") as f:
            reader = PdfReader(f)
            pages = len(reader.pages)
            text = "\n".join(p.extract_text() or "" for p in reader.pages[:3])
            print(f"doc_{i}.pdf: {pages} pages, {len(text)} chars preview")
    except Exception as e:
        print(f"doc_{i}.pdf: ERROR: {e}")
