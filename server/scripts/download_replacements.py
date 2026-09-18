"""Download replacement documents."""
import httpx
import os

DOCS = [
    {"title": "State of Nevada Employee Handbook", "url": "https://nvjobs.nv.gov/uploadedFiles/hrnvgov/Content/Resources/Publications/Employee_Handbook.pdf", "source": "policy", "account_id": "state_gov", "department": "human_resources", "access_level": 0},
    {"title": "Mississippi State Employee Handbook (2024)", "url": "https://www.eab.ms.gov/sites/eab/files/EAB-pdfs/FY%202025%20Employee%20Handbook%20with%20cover.pdf", "source": "policy", "account_id": "state_gov", "department": "human_resources", "access_level": 0},
    {"title": "Howard County Employee Handbook (2024)", "url": "https://newtools.cira.state.tx.us/upload/page/0463/2024/3.25.2024_employee_handbook.pdf", "source": "policy", "account_id": "municipal", "department": "human_resources", "access_level": 1},
    {"title": "West Virginia Dept of Administration Employee Handbook", "url": "https://administration.wv.gov/Documents/DOAEmployeeHandbook_Final.pdf", "source": "policy", "account_id": "state_gov", "department": "human_resources", "access_level": 0},
]

os.makedirs("downloads", exist_ok=True)
for i, d in enumerate(DOCS):
    idx = 10 + i
    fname = f"downloads/doc_{idx}.pdf"
    print(f"[{i+1}/4] {d['title']}...", end=" ", flush=True)
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            r = client.get(d["url"])
            r.raise_for_status()
            with open(fname, "wb") as f:
                f.write(r.content)
            print(f"OK ({len(r.content):,} bytes)")
    except Exception as e:
        print(f"FAIL: {e}")

# Verify
from pypdf import PdfReader
print("\n--- New docs ---")
for idx in [10, 11, 12, 13]:
    fname = f"downloads/doc_{idx}.pdf"
    if not os.path.exists(fname):
        print(f"doc_{idx}.pdf: MISSING")
        continue
    try:
        with open(fname, "rb") as f:
            reader = PdfReader(f)
            print(f"doc_{idx}.pdf: {len(reader.pages)} pages")
    except Exception as e:
        print(f"doc_{idx}.pdf: ERROR: {e}")
