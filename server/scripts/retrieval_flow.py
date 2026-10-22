"""Checkpoint 3 retrieval flow demo (corpus rebuild plan, Phase 3).

Runs the REAL HybridSearch.search() over local v2 dry-run records with:
  - a fake Pinecone that applies the real RBAC filter dict
    (allowed_roles $in user_roles) and lexical top-50 scoring as a
    network-free stand-in for vector retrieval,
  - the REAL expander / safety net / content_hash dedupe / rerank / top-k cut.

Prints the candidate-count flow: 50 -> filtered -> deduped -> reranked -> top-k.

Usage (cwd = server/):
  python scripts/retrieval_flow.py [query]
"""
import asyncio
import json
import re
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent
RECORDS = REPO_ROOT / "corpus" / "v2_dryrun" / "records.jsonl"
sys.path.insert(0, str(SERVER_DIR))

USER_ROLES = ["employee", "engineer"]  # non-admin
TOP_K = 6

import app.retrieval.reranker as reranker_mod  # noqa: E402
from app.retrieval.search import CANDIDATE_WIDTH, HybridSearch  # noqa: E402


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class CorpusRecord:
    __slots__ = ("id", "text", "hash", "roles", "doc_id", "department", "heading", "tokens")

    def __init__(self, rid, md):
        self.id = rid
        self.text = md.get("text_md") or ""
        self.hash = md.get("content_hash") or ""
        self.roles = set(md.get("allowed_roles") or [])
        self.doc_id = md.get("doc_id") or rid
        self.department = md.get("department") or "unknown"
        self.heading = md.get("heading_path") or md.get("doc_title") or ""
        self.tokens = tokenize(self.text)


def load_corpus() -> list[CorpusRecord]:
    corpus = []
    with RECORDS.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            corpus.append(CorpusRecord(rec.get("id", ""), rec.get("metadata") or {}))
    return corpus


class FakePinecone:
    """Applies the real RBAC filter dict; lexical stand-in for vector search."""

    def __init__(self, corpus, roles, variant_tokens):
        self.eligible = [
            r for r in corpus if r.roles and r.roles.intersection(roles)
        ]
        self.blocked = len(corpus) - len(self.eligible)
        self.corpus_size = len(corpus)
        self.variant_tokens = variant_tokens

    async def query_vectors(self, *, vector, top_k, filter, include_metadata):
        assert filter == {"allowed_roles": {"$in": USER_ROLES}}, filter
        variant_tokens = self.variant_tokens.get(int(round(vector[0])), set())
        scored = []
        for idx, rec in enumerate(self.eligible):
            if not variant_tokens:
                score = 0.0
            else:
                overlap = len(variant_tokens & rec.tokens)
                score = overlap / len(variant_tokens)
            scored.append((-score, idx))
        scored.sort()
        matches = []
        for neg_score, idx in scored[:top_k]:
            rec = self.eligible[idx]
            matches.append({
                "id": rec.id,
                "score": -neg_score,
                "metadata": {
                    "text": rec.text,
                    "content_hash": rec.hash,
                    "doc_id": rec.doc_id,
                    "source_title": rec.doc_id,
                    "department": rec.department,
                    "heading_path": rec.heading,
                },
            })
        return matches


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "employee leave policies"
    from app.retrieval.search import expand_query

    variants = expand_query(query)
    corpus = load_corpus()

    fake_pc = FakePinecone(
        corpus, USER_ROLES, {i: tokenize(v) for i, v in enumerate(variants)}
    )

    hs = HybridSearch()
    hs.pinecone = fake_pc

    async def fake_filter(user):
        return {"allowed_roles": {"$in": USER_ROLES}}

    async def fake_embed(texts):
        # Vector encodes the variant index; no network.
        return [[float(i)] + [0.0] * 7 for i in range(len(texts))]

    hs._get_filter = fake_filter
    hs._get_embeddings = fake_embed

    # Track the REAL reranker: model, full input size, fallback flag.
    real_cls = reranker_mod.CohereReranker
    created = []

    class Tracked(real_cls):
        def __init__(self):
            super().__init__()
            created.append(self)

    reranker_mod.CohereReranker = Tracked

    results = asyncio.run(hs.search(query, user=object(), top_k=TOP_K))
    flow = hs.last_flow
    rr = created[0]

    out = []
    out.append(f"Query: {query!r}")
    out.append(f"Variants ({len(variants)}):")
    for v in variants:
        out.append(f"  - {v!r}")
    out.append("")
    out.append(f"RBAC filter: {flow['rbac_filter']}")
    out.append(
        f"Corpus records: {fake_pc.corpus_size} | RBAC-eligible pool: "
        f"{len(fake_pc.eligible)} | blocked by RBAC: {fake_pc.blocked}"
    )
    out.append("")
    out.append("Flow (candidates):")
    out.append(f"  fetched (top {CANDIDATE_WIDTH} x {flow['variants']} variant(s)): {flow['fetched']}")
    out.append(f"  merged by id:                        {flow['merged_by_id']}")
    out.append(f"  after safety net (<50c/<5w dropped): {flow['after_safety_net']}")
    out.append(f"  after content_hash dedupe:           {flow['after_dedupe']}")
    out.append(
        f"  reranked ({rr.model}, fallback={rr.used_fallback}): "
        f"{flow['after_dedupe']} -> top-{TOP_K}"
    )
    out.append(f"  final top-k:                         {flow['final']}")
    out.append("")
    out.append(f"Final top {TOP_K}:")
    for i, r in enumerate(results, 1):
        md = r.metadata
        snippet = " ".join(r.content.split())[:110]
        out.append(
            f"  {i}. {md.get('doc_id', r.id)}  score={r.score:.4f}  "
            f"[{md.get('department', '?')}] {md.get('heading_path', '')}"
        )
        out.append(f"     {snippet}")

    report = "\n".join(out)
    report_path = REPO_ROOT / "corpus" / "v2_dryrun" / "retrieval_flow_report.txt"
    report_path.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\n[report written to {report_path}]")


if __name__ == "__main__":
    main()
