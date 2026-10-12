#!/usr/bin/env python3
"""
Download real public documents for the RBAC RAG project and organize them
into department folders, plus a manifest.jsonl with the ACL overlay.

Usage:
    python fetch_corpus.py --email you@example.com
    python fetch_corpus.py --email you@example.com --only gitlab cuad

Requires: Python 3.9+, git, `pip install requests`.
SEC requires a descriptive User-Agent with a contact email (--email).
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path("corpus")
RAW = ROOT / "_raw"
MANIFEST = ROOT / "manifest.jsonl"

# department -> (classification, allowed_roles)
ACL = {
    "general":     ("internal",   ["intern", "employee", "engineer", "manager", "hr", "legal", "finance", "admin"]),
    "hr":          ("restricted", ["hr", "manager", "admin"]),
    "engineering": ("internal",   ["engineer", "manager", "admin"]),
    "it_security": ("restricted", ["engineer", "admin"]),
    "sales":       ("internal",   ["employee", "manager", "admin"]),
    "legal":       ("restricted", ["legal", "admin"]),
    "finance":     ("restricted", ["finance", "admin"]),
}

# GitLab handbook folder (under content/handbook/) -> department.
GITLAB_MAP = {
    "people-group": "hr",
    "total-rewards": "hr",
    "engineering": "engineering",
    "security": "it_security",
    "sales": "sales",
    "marketing": "sales",
    "finance": "finance",
    "legal": "legal",
}

SEC_COMPANIES = {  # name: CIK
    "apple": 320193,
    "microsoft": 789019,
    "alphabet": 1652044,
    "amazon": 1018724,
    "nvidia": 1045810,
}

DIRECT_FILES = [  # (url, department, filename)
    ("https://www.indiacode.nic.in/bitstream/123456789/15793/1/aA2019-29.pdf",
     "hr", "india_code_on_wages_2019.pdf"),
    # Add the other three labour codes from https://www.indiacode.nic.in
    # (Industrial Relations Code 2020, Code on Social Security 2020,
    #  OSH & Working Conditions Code 2020) as extra tuples here.
]

CUAD_URL = "https://zenodo.org/api/records/4595826/files/CUAD_v1.zip/content"
GITLAB_REPO = "https://gitlab.com/gitlab-com/content-sites/handbook.git"

# Zenodo and some gov hosts intermittently 504/429 on larger files.
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 3


def log(msg):
    print(f"[fetch] {msg}", flush=True)


def add_manifest(path: Path, dept: str, source: str):
    cls, roles = ACL[dept]
    rec = {
        "path": str(path.relative_to(ROOT)),
        "department": dept,
        "classification": cls,
        "allowed_roles": roles,
        "source": source,
    }
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def download(url: str, dest: Path, headers=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"skip (exists): {dest.name}")
        return

    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log(f"downloading {url}  (attempt {attempt}/{MAX_ATTEMPTS})")
            with requests.get(url, headers=headers, stream=True, timeout=(30, 300)) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                last_report = 0.0
                with dest.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        # report roughly every 10 MB so long downloads visibly move
                        if done - last_report >= 10 << 20:
                            last_report = done
                            if total:
                                log(f"  {dest.name}: {done / (1 << 20):.0f}/{total / (1 << 20):.0f} MB")
                            else:
                                log(f"  {dest.name}: {done / (1 << 20):.0f} MB")
                if total and dest.stat().st_size != total:
                    raise IOError(f"short read: got {dest.stat().st_size} of {total} bytes")
            log(f"  {dest.name}: complete ({dest.stat().st_size / (1 << 20):.1f} MB)")
            return
        except Exception as e:
            last_err = e
            dest.unlink(missing_ok=True)  # drop the partial before retrying
            if attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
            log(f"  retryable failure: {type(e).__name__}: {e}")
            log(f"  retrying in {wait}s ...")
            time.sleep(wait)

    raise RuntimeError(f"download failed after {MAX_ATTEMPTS} attempts: {url}: {last_err}")


# ---------- GitLab handbook ----------
def fetch_gitlab():
    repo = RAW / "gitlab_handbook"
    if not repo.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", GITLAB_REPO, str(repo)], check=True)
    base = repo / "content" / "handbook"
    if not base.exists():
        sys.exit(f"Expected {base} not found; the repo layout may have changed.")
    count = 0
    for md in base.rglob("*.md"):
        rel = md.relative_to(base)
        top = rel.parts[0]
        dept = GITLAB_MAP.get(top, "general")
        # keep a stable, flat-ish path
        out = ROOT / dept / "gitlab_handbook" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, out)
        add_manifest(out, dept, f"gitlab-handbook:{rel.as_posix()}")
        count += 1
    log(f"gitlab: {count} markdown files organized")


# ---------- CUAD ----------
def fetch_cuad():
    zpath = RAW / "CUAD_v1.zip"
    download(CUAD_URL, zpath)
    extract = RAW / "CUAD_v1"
    if not extract.exists():
        with zipfile.ZipFile(zpath) as z:
            z.extractall(extract)
    count = 0
    # Original contracts ship as PDF/TXT under full_contract_pdf / full_contract_txt.
    for p in extract.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt"} and "full_contract" in p.as_posix():
            out = ROOT / "legal" / "cuad" / p.name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)
            add_manifest(out, "legal", f"cuad:{p.name}")
            count += 1
    log(f"cuad: {count} contract files organized")


# ---------- SEC EDGAR ----------
def fetch_sec(email: str):
    headers = {"User-Agent": f"rbac-rag-portfolio {email}"}
    for name, cik in SEC_COMPANIES.items():
        meta = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                            headers=headers, timeout=60)
        meta.raise_for_status()
        recent = meta.json()["filings"]["recent"]
        for i, form in enumerate(recent["form"]):
            if form == "10-K":
                acc = recent["accessionNumber"][i].replace("-", "")
                doc = recent["primaryDocument"][i]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
                out = ROOT / "finance" / "sec_10k" / f"{name}_10k_{recent['reportDate'][i]}.htm"
                download(url, out, headers=headers)
                add_manifest(out, "finance", f"sec-edgar:{url}")
                break
        time.sleep(0.5)  # stay well inside SEC fair-access limits
    log("sec: latest 10-K per company fetched")


# ---------- direct files ----------
def fetch_direct():
    for url, dept, fname in DIRECT_FILES:
        out = ROOT / dept / "direct" / fname
        try:
            download(url, out)
            add_manifest(out, dept, url)
        except Exception as e:  # keep going; some gov sites are flaky
            log(f"FAILED {url}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True, help="contact email for SEC User-Agent")
    ap.add_argument("--only", nargs="*", choices=["gitlab", "cuad", "sec", "direct"])
    args = ap.parse_args()

    ROOT.mkdir(exist_ok=True)
    MANIFEST.write_text("", encoding="utf-8")  # rebuild manifest each run
    todo = set(args.only or ["gitlab", "cuad", "sec", "direct"])

    # One flaky host must not abort the remaining stages.
    failures = []
    stages = [
        ("gitlab", lambda: fetch_gitlab()),
        ("cuad",   lambda: fetch_cuad()),
        ("sec",    lambda: fetch_sec(args.email)),
        ("direct", lambda: fetch_direct()),
    ]
    for name, fn in stages:
        if name not in todo:
            continue
        try:
            fn()
        except Exception as e:
            log(f"STAGE FAILED [{name}]: {type(e).__name__}: {e}")
            failures.append(name)

    lines = sum(1 for _ in MANIFEST.open(encoding="utf-8")) if MANIFEST.exists() else 0
    log(f"done. manifest: {MANIFEST} ({lines} records)")
    if failures:
        log(f"failed stages: {', '.join(failures)} - re-run with --only {sorted(failures)[0]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
