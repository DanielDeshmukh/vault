# Vault — Interview Intel

**Repo:** `https://github.com/DanielDeshmukh/vault` (public) · **Branch:** `master` @ `c70c545` · **Written:** 2026-10-07
**Secret values:** every secret value below is written `<REDACTED> (len=N)`. No secret, prefix, suffix, or fragment of a secret is reproduced in this document.

**How to read this file**

- Every claim carries a citation in `path/to/file.py:LINE-LINE` form so you can jump straight to it.
- If the repo has no evidence for something, it says `NOT FOUND IN CODE` rather than bluffing. Never claim a feature the citation doesn't support.
- Code blocks are verbatim and capped at ~25 lines; the path sits above each one.
- Spoken answers are written to be said out loud, not read silently. Jargon gets a one-line definition on first use.

**Contents**

1. `### Q1:` Walk me through how Vault enforces permissions end-to-end.
2. `### Q2:` How does the RAG pipeline work, from ingestion to a cited answer?
3. `### Q3:` How do you know it actually works — what's tested, what's evaluated?
4. `### Q4:` What's broken or weak in what you built?
5. `### Q5:` Which parts did AI tools write, and how did you verify them?
6. `## Threat model`
7. `## Honest status`
8. `## AI tooling: which parts, how verified`
9. `## Additional likely questions`
10. `## Weaknesses and honest framing`
11. `## Security findings`

---

### Q1: Walk me through how Vault enforces permissions end-to-end.

There are three gates, at three different layers, and it's worth keeping them separate in your head.

**Gate one — authentication and the approval switch.** Every protected route takes `Depends(get_current_user)` (`server/app/auth/jwt.py:37-65`). It decodes the JWT with the configured secret and algorithm (`jwt.py:47`), loads the user row (`jwt.py:55-58`), then checks three things in order: the account is active (`jwt.py:59-60`), the email inside the token still matches the row (`jwt.py:61-62`), and the account is approved (`jwt.py:63-64`). Because that check lives in the dependency, not in each handler, an unapproved user is rejected before any endpoint body runs. It's re-stated redundantly in the query endpoints (`server/app/api/queries.py:64-68` and `:174-178`).

**Gate two — the question ceiling.** Before retrieval we classify the *question itself*. `get_question_access_level` (`server/app/auth/permissions.py:16-57`) is keyword matching: "board", "payroll", "restricted" ⇒ level 3; "confidential", "customer contract" ⇒ level 2, and so on down to public. We compare that to the user's ceiling — literally `max(Role.access_level)` over their roles, defaulting to public if they have none (`permissions.py:60-68`). If the question outranks the user, we return "Access denied" and never touch the vector store (`server/app/api/queries.py:70-82`, and the streaming twin at `:188-190`).

**Gate three — the pre-filter, which is the real one.** `PermissionFilter.build_filter` (`server/app/retrieval/permission_filter.py:21-33`) produces `{"access_level": {"$lte": max_level}}`; admins get `None`, meaning no filter. That dict is handed to Pinecone *as the query filter* (`server/app/retrieval/search.py:102-111`, `server/app/db/pinecone.py:41-54`), so unauthorised vectors are never returned, never loaded into memory, never placed in the prompt. That's the design claim: filter before retrieval, not after generation.

**Gate four, for the documents UI only.** `server/app/api/documents.py:53-63` filters the list by `Document.access_level`, and `:81-94` returns 403 on a single document.

*Honest caveat to volunteer before they ask:* gate four uses a **different** implementation — `documents.py:39-50` maps role *names* through `ACCESS_LEVEL_MAP`, while gate two uses the `access_level` column. Two sources of truth for the same concept (`server/app/api/documents.py:32-50` vs `server/app/auth/permissions.py:60-68`).

---

### Q2: How does the RAG pipeline work, from ingestion to a cited answer?

RAG is *retrieval-augmented generation* — instead of letting a language model free-associate, you fetch relevant documents first and paste them into the prompt as the only permitted source.

**Write path.** `POST /api/ingest` accepts a file plus `account_id`, `department` and `access_level` straight from the form (`server/app/api/ingestion.py:28-61`), or `POST /api/ingest/direct` takes a JSON body with the same fields (`ingestion.py:80-109`). `IngestionPipeline.ingest_single_document` (`server/app/ingestion/pipeline.py:130-203`) parses the bytes through `ParserRouter`, writes a `Document` row to Postgres (`pipeline.py:156-163` → `_store_document` at `:205-231`), splits it with `SemanticChunker`, then embeds each chunk one at a time with Cohere (`pipeline.py:171-191`, client built at `:13-25`). Each vector's metadata carries `content`, `document_id`, `title`, `source`, `account_id`, `department`, `access_level`, `owner_id` (`pipeline.py:176-189`). Chunks go to Postgres and vectors go to Pinecone (`pipeline.py:193-194`, `:233-251`).

**Read path — hybrid search.** "Hybrid" here means *several vector queries from one question*. `expand_query` (`server/app/retrieval/search.py:52-78`) returns the raw question plus up to three rewrites: a domain expansion from a 30-entry table (`search.py:19-49`) and a stop-word-stripped keyword variant (`search.py:59-75`). All variants embed in one batched Cohere call (`search.py:142-153`) and all fire at Pinecone in parallel with the permission filter (`search.py:96-111`), results are deduped and sorted by score (`search.py:113-128`), then optionally reranked by Cohere (`search.py:130-135`).

**Generation and citations.** `CitationGenerator` builds a system prompt that demands `[document_id]` after every claim (`server/app/retrieval/generator.py:23-33`) plus a user message containing the top 6 sources, each capped at 1000 characters (`generator.py:17-18`, `:87-97`). The model answers through `asyncio.to_thread(self.client.chat, ...)` (`generator.py:52-66`) — `to_thread` runs a blocking call off the main event loop. Citations are then recovered *by regex*, not by the model: `re.findall(r'\[([^\]]+)\]', answer)` matched against the retrieved document ids (`generator.py:102-119`). Anything the model cites that isn't in the retrieved set is silently dropped.

The streaming endpoint does the same thing chunk by chunk (`server/app/api/queries.py:166-238`), and the browser consumes it as SSE (`frontend/lib/api.ts:132-176`, used at `frontend/app/dashboard/page.tsx:130`).

*Two caveats to volunteer:* metadata `content` is truncated to 500 chars at write time (`pipeline.py:105`, `:180`), so the generator's `MAX_SOURCE_CHARS = 1000` (`generator.py:18`) can never actually see 1000 characters. And there is **no lexical index** — `git grep 'tsvector|to_tsquery|ILIKE'` over `server/app` returns nothing, so the "BM25 keyword search" in `README.md:77` and `PLAN.md:259` is `NOT FOUND IN CODE`.

---

### Q3: How do you know it actually works — what's tested, what's evaluated?

Short version: I ran them. Unit tests pass, the rest needs live services, CI has never run, and one of the two security metrics is structurally incapable of failing.

**What I verified myself just now.** From the repo root, `pytest tests/unit` gives **50 passed** — but only with `PYTHONPATH=server` and a `DATABASE_URL` set. Without `PYTHONPATH=server` you get `ModuleNotFoundError: No module named 'app'` on all three files, because the package lives in `server/app` and nothing adds it to the path. And without a `DATABASE_URL` you don't even get to the tests: `server/tests/conftest.py:5` imports `app.db.sessions`, which builds the engine at import time (`server/app/db/sessions.py:26`) and raises `ArgumentError: Could not parse SQLAlchemy URL` on an empty string.

**Two committed tests fail.** `server/tests/test_search.py:7` asserts `expand_query` returns `"...time off absence absence"`; it actually returns `["What are the employee leave policies?", "employee leave"]`. `server/tests/test_conversation_context.py:20` asserts `"CONVERSATION CONTEXT"` is in the prompt; the code emits `"Previous conversation context:"` (`server/app/retrieval/generator.py:40`). Both run as **2 failed**.

**What the suites cover.** `tests/unit/test_auth.py` (129 lines) covers bcrypt hashing and JWT create/decode/expiry/tampering (`:25`, `:86`, `:166`). `tests/unit/test_permissions.py` (156 lines) covers the access-level enum, `build_pinecone_filter`, `get_question_access_level`, and `PermissionFilter.build_filter` against fakes (`:10`, `:27`, `:80`, `:105`). `tests/unit/test_chunker.py` (132 lines) covers chunking boundaries. `tests/integration/test_registration.py` (345 lines) drives the real FastAPI app through `ASGITransport` (`:15-20`) against a real database, with per-run unique emails and session teardown cleanup (`:23-27`, `:41-53`) — **17 tests**, covering registration, login, token rejection, the unapproved gate, and `/me`.

**The security suite is 11 tests** and splits cleanly. Three are pure logic (`tests/security/test_permission_leakage.py:104-152`) plus golden-set shape checks (`:343-378`, asserting exactly 50 questions and ≥10 permission-boundary ones). Three more use fakes (`:155-192`). The remaining five — `:199-228`, `:231-263`, `:294-340` — instantiate `Evaluator`, which means a real Postgres, a real Pinecone and a real Cohere key. They collect (28 integration+security tests total collect cleanly) but I did not execute them; there's no seeded live corpus in this environment.

**The uncomfortable part.** `_calculate_security_metrics` (`eval/evaluator.py:347-365`) never writes `total_leaks`. It only ever sets `total_refusals_*` and `permission_boundary_accuracy`. The field defaults to `0` (`eval/metrics.py:45`), the aggregate sums it (`eval/evaluator.py:387`), and `unauthorized_leakage_rate` divides it out (`eval/evaluator.py:423`). So **the headline "0.0 leakage" number is a tautology** — the loop that computes it cannot produce anything else. `TestZeroLeakage` (`test_permission_leakage.py:336`) asserts `total_leaks == 0` and will pass forever; to its credit, the same test does assert there were no infrastructure errors first (`:330-333`), so it at least forces retrieval and generation to actually run. The real signal lives elsewhere: `:226-228` checks refusal-or-authorised-source, and `:261-263` checks the restricted document id never appears in a citation.

Two more metric problems: `calculate_faithfulness` is a hardcoded ladder returning 0.9 for short answers and 0.7 + 0.1×n otherwise (`eval/metrics.py:143-166`), and `calculate_relevance` returns a flat 0.8 (`eval/metrics.py:193-196`). And `retrieved_sources` is `metadata["source"]` — values like `"policy"`/`"csv"` (`eval/evaluator.py:152-154`) — compared against expectations like `["crm", "account"]` (`eval/golden_set.py:54`), so precision/recall are measuring source *types*, not whether the right document was found.

**CI has never run.** `.github/workflows/ci.yml:5,7` triggers on `main` and `develop`; the repo's branch is `master`. The backend jobs use `working-directory: backend` (`:22`, `:59`) — that folder was renamed to `server/` in commit `b8d025f` — and `pytest tests/unit/` (`:102`) would resolve to `backend/tests/unit`, which doesn't exist either. The workflow also defines Trivy and TruffleHog secret scanning that has never executed.

---

### Q4: What's broken or weak in what you built?

I'd group it into four buckets, and I'd lead with the one I'm least comfortable with.

**One — the authorization model is narrower than it looks.** The only thing the production filter actually enforces is `access_level` (`server/app/retrieval/permission_filter.py:21-33`). Three things exist and are never consulted: `get_user_allowed_account_ids` is imported at `permission_filter.py:6` and then never referenced; `build_pinecone_filter` (`server/app/auth/permissions.py:96-130`) — the function that *does* add account and role conditions — is only called from `server/scripts/role_access_eval.py:16,53`, i.e. an eval script; and `can_access_document` (`permissions.py:133-171`) plus its twin `PermissionFilter.can_access_document` (`permission_filter.py:35-62`) have no callers. Concretely: the `DocumentAccess` per-user ACL table and `Document.allowed_roles` are written (`server/app/ingestion/pipeline.py:223-227`) but never read on the search path, and `allowed_roles` is never even copied into Pinecone metadata (`pipeline.py:176-189`). So "account-scoped access" (`README.md:53`) and "document-level overrides" are `NOT FOUND IN CODE` in the serving path.

**Two — deletion doesn't reach the vector store.** `DELETE /api/documents/{id}` removes `DocumentChunk` rows and the `Document` row (`server/app/api/documents.py:109-132`) and never calls Pinecone. `delete_vectors` and `delete_by_filter` are defined (`server/app/db/pinecone.py:56-60`) with zero callers. Deleted content stays retrievable by any user whose access level still covers it.

**Three — the write path is open to any approved user.** `access_level` is client-supplied on both ingest endpoints (`server/app/api/ingestion.py:34` and `:25`), and neither endpoint requires `is_admin`. Any approved account can inject content at any classification. The enricher that would reclassify by keywords (`server/app/ingestion/metadata.py:63-82`) only runs inside `ingest_from_connector` (`pipeline.py:76`), which nothing calls — `ingest_single_document` skips it entirely (`pipeline.py:141-163`). So it's dead code on the path the API actually uses.

**Four — correctness and honesty problems.** The question ceiling is keyword-based and trivially bypassed by rephrasing (`permissions.py:16-57`). `GET /api/query/trace/{trace_id}` returns any trace to any authenticated user — no ownership check (`server/app/api/queries.py:241-251`) — and the trace store is an unbounded in-memory list on a singleton (`server/app/tracing/logger.py:33-34`, `:47`, `:99`), so it's both an IDOR and an unbounded-memory risk that vanishes on restart. Both Pinecone methods and the streaming generator do blocking network I/O inside `async def` with no `to_thread` (`db/pinecone.py:38-60`, `retrieval/generator.py:75-85`), so a stream freezes the event loop for every other request. Error handlers echo raw exception text to clients (`queries.py:160-163`, `:226-228`). There is no rate limiting anywhere — `git grep 'rate_limit|slowapi|limiter'` over `server/app` returns nothing: `NOT FOUND IN CODE`. And CORS lists a literal `"https://*.vercel.app"` in `allow_origins` (`server/app/main.py:20-23`) with no `allow_origin_regex`, so the glob doesn't glob.

---

### Q5: Which parts did AI tools write, and how did you verify them?

> **Read this before answering.** The repo contains **no** `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, or `.github/copilot-instructions.md` — tool usage is `NOT FOUND IN CODE`. Every claim below about *your* process is a `[FILL IN: ...]` placeholder. Do not assert an AI tool the repository can't evidence, and do not claim you didn't use one if you did. The verification claims, by contrast, are all citable.

**The answer (≈210 words, say it out loud):**

"I used AI tools across this project — [FILL IN: which tools, and for roughly what share of the code], and I want to be precise about where I drew the line, because the parts I let stand unverified are exactly the parts I'd flag in review.

The scaffolding and the repetitive bulk — connector classes, parser wrappers, the test fixtures — are where I leaned on generation hardest. The parts I rewrote by hand after reading them were the permission filter and the JWT dependency, because a plausible-looking authorization check is the most dangerous thing a tool can hand you. [FILL IN: one specific line you changed and why].

On verification: everything under `tests/unit` runs green — 50 tests — and I ran it to confirm rather than trusting the CI badge, because CI never actually runs (`.github/workflows/ci.yml:5` triggers on branches this repo doesn't have). The two tests in `server/tests` fail today, and I know exactly which assertions drifted out of sync with the code. For the retrieval path I wrote a role-matrix harness that logs in as five seeded accounts and checks citations against each document's access level. [FILL IN: whether you ran it against the deployed app, and when.]

The thing I'd say honestly is: generation got me speed, review got me correctness, and the gap between them is visible in this codebase."

---

## Threat model

**Assets**

| Asset | Where it lives | Citation |
|---|---|---|
| Document corpus (plaintext + chunks) | Postgres `documents`, `document_chunks` | `server/app/db/pipeline` write path `server/app/ingestion/pipeline.py:205-251` |
| Embeddings + chunk text | Pinecone index `vault`, `metadata.content` | `server/app/ingestion/pipeline.py:176-189`, `server/app/db/pinecone.py:19-22` |
| JWT signing key (HS256) | `settings.JWT_SECRET_KEY` | `server/app/config.py:21-22`, `server/app/auth/jwt.py:33,47` |
| Provider API keys (Cohere, Pinecone) | env / `.env` | `server/app/config.py:8-19` |
| Audit traces (user email, query, answer) | in-memory singleton | `server/app/tracing/logger.py:33-34`, `:99` |
| Deployed-app account passwords | tracked scripts + ignored `.env.example` | see **Security findings** |

**Actors and what they can reach**

| Actor | Reach | Enforced at |
|---|---|---|
| Anonymous internet | `/health`, `/api/auth/register`, `/api/auth/login` only; app is deployed publicly (`vercel.json:16-18` routes `/api/*` to the Python function) | `Depends(get_current_user)` on every other route — see all call sites under `server/app/api/` |
| Authenticated, **unapproved** user | Holds a valid token (issued at `server/app/auth/router.py:82-85`) but every protected handler rejects them | `server/app/auth/jwt.py:63-64` |
| Approved, level-0 user | Public documents only, and only if their question classifies as public | `server/app/retrieval/permission_filter.py:31-33`, `server/app/api/queries.py:70-82` |
| Approved, high-level user | Everything at or below their `max(Role.access_level)` | same as above |
| Admin | No Pinecone filter (`permission_filter.py:28-29`), all documents, all admin routes | `server/app/api/admin.py:36-42` |
| Anyone with repo access | Full git history, because the repo is **public** | repo is `public` (verified via `gh repo view`) |

**Trust boundaries**

```
Browser (localStorage JWT: frontend/lib/api.ts:13-21)
  → Vercel edge (vercel.json:16-18 → api/index.py)
    → FastAPI  (server/app/main.py:30)
      → Postgres (server/app/db/sessions.py:26-33)
      → Pinecone (server/app/db/pinecone.py:41-54)   ← permission filter applied HERE
      → Cohere  (embed / rerank / generate)
```

**Threats, with what's actually mitigated**

| Threat | Status | Evidence |
|---|---|---|
| Horizontal privilege escalation (read another tier's docs) | **Mitigated at the vector store** for the `access_level` dimension | `permission_filter.py:21-33` → `search.py:102-111` → `pinecone.py:41-54` |
| Access via rephrased question bypassing the ceiling | **Weak** — keyword classifier, not semantic | `permissions.py:16-57`; rephrasing avoids the term lists entirely |
| Access via document endpoints instead of query | **Mitigated**, but by a second, divergent implementation | `documents.py:39-50`, `:61`, `:92-94` |
| Access via `DocumentAccess` / `allowed_roles` overrides | **Not applicable — never enforced** | no callers; `permissions.py:96-171` unused on the serving path |
| Reading another user's audit trace | **Not mitigated (IDOR)** | `queries.py:241-251`, no ownership comparison |
| Reading deleted content | **Not mitigated** | `documents.py:109-132` never touches Pinecone |
| Content poisoning / injection into the corpus | **Not mitigated** — `access_level` is client-supplied, no admin gate | `ingestion.py:34`, `:25`, `:83`, `:112` |
| Prompt injection from retrieved documents | **NOT FOUND IN CODE** — retrieved text is interpolated straight into the user message | `generator.py:41-46` |
| Token theft via XSS | Partially mitigated: answer rendered with `react-markdown`, no `dangerouslySetInnerHTML` (grep over `frontend` = `NOT FOUND IN CODE`) | `frontend/app/dashboard/page.tsx:4`, `:312-343` |
| CSRF | Largely N/A: Bearer token in `localStorage`, not cookies | `frontend/lib/api.ts:36-42` |
| Credential stuffing / brute force | **NOT FOUND IN CODE** — no rate limiter anywhere under `server/app` | grep `rate_limit\|slowapi\|limiter` = no matches |
| Secret exposure | **Badly compromised** — see **Security findings** below | see **Security findings** below |
| DoS / resource exhaustion | **Partially unmitigated**: in-memory trace list grows forever (`logger.py:47`), and blocking SDK calls stall the event loop (`pinecone.py:38-60`, `generator.py:75-85`) | as cited |

**Out of scope for this build (say so explicitly):** multi-tenancy isolation beyond the single `account_id` string, key rotation, at-rest encryption, PII redaction, audit-log durability (traces are in-memory only, `logger.py:34`), and supply-chain attestation.

---

## Honest status

**Verified working** (I executed these):

- `pytest tests/unit` from repo root → **50 passed** (with `PYTHONPATH=server` + `DATABASE_URL` set).
- `pytest tests/integration tests/security --collect-only` → **28 tests collected** without import errors.
- Access-level enum, `build_pinecone_filter`, `get_question_access_level`, and `PermissionFilter.build_filter` behaviour are covered by real assertions (`tests/unit/test_permissions.py:10-192`).

**Verified broken** (I executed these):

- `pytest server/tests` → **2 failed**. `server/tests/test_search.py:7` and `server/tests/test_conversation_context.py:20` assert strings the current code no longer produces.
- Collecting from repo root without `PYTHONPATH=server` → `ModuleNotFoundError: No module named 'app'` on all three unit modules.
- Collecting `server/tests` without `DATABASE_URL` → `sqlalchemy.exc.ArgumentError` at `server/app/db/sessions.py:26`.

**Cannot verify here** (state this rather than guessing):

- The 11 security tests and 17 integration tests need a live Postgres with seeded documents plus live Pinecone/Cohere credentials. They collect; I did not run them.
- No end-to-end "ask a question, get a cited answer" run has been reproduced in this session.

**Structurally unsound even when it runs:**

- `unauthorized_leakage_rate` is always `0.0` by construction (`eval/evaluator.py:347-365` never sets `total_leaks`; summed at `:387`, divided at `:423`).
- `run_role_query_eval` (`eval/evaluator.py:245-286`) is pure arithmetic over the constant `ROLE_QUERY_CHECKS` table (`:8-54`). It never invokes the system, so a pass proves the table is internally consistent, not that the software behaves.
- Faithfulness and relevance are hardcoded ladders, not measurements (`eval/metrics.py:143-166`, `:169-196`).

**Measured once, in untracked artifacts** (`server/eval_results_*.json` — no commit provenance, produced by `server/scripts/eval_full*.py` against `https://vault-rbac-rag.vercel.app`, **not reproducible from this checkout**):

- `server/eval_results_full.json`: `role=Internal, access_level=1 → confidential_leaks=1`. Every other role/level records `0`. **One recorded leak exists in an artifact on disk.**
- Positive recall in the same file: Admin `0.92`, Internal `0.92`, Confidential `0.72`, Public `0.08` and `0.0`.
- `server/eval_results_full_v2.json`: all `access_violations=0`, but all `positive_recall=0.0` — which means that run measured nothing useful on the positive side. Treat it as a broken run, not a good score.
- `server/eval_results_recall_v2.json`: `avg_keyword_recall` ranges `0.68`–`0.92` across 9 role rows.

**Build/deploy reality:**

- CI has never executed (`.github/workflows/ci.yml:5,7` on `main`/`develop`; `working-directory: backend` at `:22`,`:59`; folder renamed in `b8d025f`).
- The repo has a `.pre-commit-config.yaml` with TruffleHog, but the *installed* `.git/hooks/pre-commit` is a custom script whose `EXCLUDE_PATTERNS` skips `scripts/check_*`, `scripts/create_*`, `scripts/test_*`, `scripts/evaluate*`, `eval_results`, and every `.json`/`.md` — the exact classes of file where secrets were found.
- Root `pyproject.toml` is 16 lines (ruff only; a 9-line pytest block is **uncommitted**); dependency and pytest config live in `server/pyproject.toml:1-62`. Two pyproject files, split across directories, only one of which is wired to CI.
- `README.md:36,77` and `PLAN.md:259` describe BM25/keyword search and Groq generation; the code uses Cohere (`server/app/retrieval/generator.py:36`, `server/app/config.py:19`) and has no lexical index. `server/pyproject.toml:21,24-26` still declares `groq`, `langchain`, and `sentence-transformers`, which nothing under `server/app` imports (`git grep groq -- server/app` → `config.py:13` env var only, plus a stale docstring at `server/app/api/queries.py:57`).

---

## AI tooling: which parts, how verified

### The five riskiest modules, their failure modes, and how to check them

**1. `server/app/retrieval/search.py` — the permission filter in the hot path.**
*Failure mode:* `build_filter` returning `None` for a non-admin (`server/app/retrieval/permission_filter.py:28-29`) turns off enforcement silently and every query succeeds — no error, just over-broad results. The inverse failure, `get_user_max_access_level` falling back to `PUBLIC` when a user has no roles (`server/app/auth/permissions.py:68`), over-restricts and looks like "search is broken."
*Checklist:* assert `filter_dict is not None` for every non-admin fixture before calling `query_vectors`; keep the fake-DB tests at `tests/unit/test_permissions.py:105-200`; add an end-to-end assertion that a level-0 user's result set contains no vector with `access_level >= 1`; add a regression test pinning `permissions.py:68`'s fallback so a "fix" can't flip it.

**2. `server/app/api/queries.py` — authz, error handling, and the trace endpoint in one file.**
*Failure mode:* three separate issues. The ceiling gate (`:70-82`) is keyword-based and rephrasing-dependent. The exception handlers echo raw exception text to the client (`:160-163`, `:226-228`). `GET /api/query/trace/{trace_id}` (`:241-251`) has no ownership check, so any authenticated user can read any trace including `user_email` and `answer` (`server/app/tracing/logger.py:81-95`).
*Checklist:* run the 17 integration tests (`tests/integration/test_registration.py`); add a trace test that user A fetches user B's trace and must get 403/404; assert responses never contain stack frames or driver strings; fuzz `get_question_access_level` with paraphrases.

**3. `server/app/ingestion/pipeline.py` — dual-write to Postgres and Pinecone.**
*Failure mode:* the two stores diverge. `_store_document` flushes to Postgres (`:229-230`) and `_store_chunks` upserts to Pinecone (`:249-251`) with no shared transaction; a failure between them leaves orphan rows or orphan vectors. Combined with the fact that deletion only touches Postgres (`server/app/api/documents.py:109-132`), the vector store drifts permanently. Also `metadata.content[:500]` (`:105`, `:180`) silently caps context.
*Checklist:* write an ingest → search → delete → search round-trip test that must return zero results after delete; add a reconciliation job comparing `documents.id` against Pinecone ids `{doc.id}-chunk-{i}`; assert every vector's metadata matches its Postgres row.

**4. `server/app/auth/jwt.py` + `server/app/auth/permissions.py` — the identity and ceiling core.**
*Failure mode:* two implementations of "what level is this user?" that can disagree: the `Role.access_level` column (`permissions.py:60-68`) versus role-name matching (`server/app/api/documents.py:39-50`). A role named `Head of Sales` maps to `ACCESS_LEVEL_MAP.get("head of sales", 0)` → 0 in the documents path while carrying level 3 in the query path. Same user, different answers, depending on which endpoint they hit.
*Checklist:* collapse to one function; add a property test asserting both agree for every row in `roles`; add a seed-role fixture covering a name that isn't in `ACCESS_LEVEL_MAP` (`documents.py:32-37`) and assert it doesn't silently degrade to 0.

**5. `server/app/retrieval/generator.py` — untrusted text into the prompt, untrusted text out as citations.**
*Failure mode:* retrieved document content is concatenated into the user message with no delimiters or escaping beyond a `---` separator (`:41-46`), so a document containing instruction-like text is a live prompt-injection vector. Citations are recovered by regex over the model's output and matched against retrieved ids (`:102-119`) — an unknown id yields *no* citation rather than an error, so a fabricated reference disappears instead of raising. The streaming path iterates a blocking SDK call inside an async generator (`:75-85`), freezing the event loop for the whole response.
*Checklist:* add injection canary documents to the golden set and assert the canary never appears in an answer; assert every returned citation's `document_id` exists in the user's permitted set; wrap `chat_stream` in a thread or make the endpoint yield between chunks; assert `sum(citations) > 0` for questions that should cite.

### Spots that look generated (evidence, not accusation)

State these as observations. Style alone proves nothing, and there is no in-repo record of tool usage — `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md` are all `NOT FOUND IN CODE`.

- `PLAN.md:3-56` — a ~50-line ASCII-art architecture diagram, followed by uniform Markdown phase tables (`PLAN.md:218-295`) with the same "Task | Deliverable" shape five times over.
- `server/app/ingestion/connectors/` — five sibling files at a suspiciously even size distribution: `confluence.py` 165 lines, `jira.py` 202, `misc.py` 191, `slack.py` 140, `zendesk.py` 151, each with the same `BaseConnector` subclass shape.
- `eval/evaluator.py:8-61` — `ROLE_QUERY_CHECKS` and `ROLE_LEVEL_REQUIRED` are hand-typed truth tables that mirror each other; `run_role_query_eval` (`:245-286`) then "tests" the table against itself.
- `eval/metrics.py:143-166` — a magic-number ladder (0.7 base, +0.1 per keyword, 0.9 for short answers) whose own docstring says *"In production, use an LLM-based evaluator."* The comment admits it's a placeholder.
- `server/app/retrieval/search.py:19-49` — `QUERY_EXPANSIONS`, 30 hand-written `keyword → expansion` pairs; `server/app/ingestion/metadata.py:12-18,63-79` — the same pattern for departments and access levels.
- Commit subjects: multi-clause conventional-commit messages (`21b9c0a` "Fix streaming: correct delta path event.delta.message.content.text", `fa1193e` "fix: revert streaming thread hack, keep asyncio.to_thread for non-streaming", `89f0756` "fix: permission filter was blocking all non-admin users due to nonexistent allowed_roles field").
- The `.git/hooks/pre-commit` `EXCLUDE_PATTERNS` list (`scripts/check_*`, `scripts/create_*`, `scripts/test_*`, `scripts/evaluate*`, `eval_results`, `*.json`, `*.md`) reads like it was written to let a batch of generated helper scripts through.

### Five "walk me through X()" challenges, with model answers

**① Walk me through `PermissionFilter.build_filter`.**
*Weak answer:* "it builds a Pinecone filter." *Strong answer:* "`server/app/retrieval/permission_filter.py:21-33`. If `user.is_admin` it returns `None` at `:28-29`, meaning no filter at all — that's the admin bypass, and it's the single most dangerous line in the function. Otherwise it calls `get_user_max_access_level` (`:31`), which is `max(Role.access_level)` over the user's roles (`server/app/auth/permissions.py:60-68`), and returns `{"access_level": {"$lte": int(max_level)}}` at `:33`. The dict is consumed by `search.py:102-111` and passed straight to `pinecone.query_vectors(filter=...)` (`server/app/db/pinecone.py:41-54`), so filtering happens inside the vector store, before results exist. What it does *not* do: it imports `get_user_allowed_account_ids` at `:6` and never uses it, and it never emits account or role conditions — those only exist in `build_pinecone_filter` (`permissions.py:96-130`), which no serving code calls."

**② Walk me through `HybridSearch.search`.**
*Strong answer:* "`server/app/retrieval/search.py:86-135`. Step one, `expand_query` (`:93`, defined `:52-78`) turns the question into up to four variants — the original, up to three domain expansions from the table at `:19-49`, and a stop-word-stripped keyword string from `:59-75`. Step two runs two things concurrently with `asyncio.gather` (`:96-99`): building the permission filter and batching the embeddings into one Cohere call (`:142-153`, wrapped in `asyncio.to_thread` at `:147` so it doesn't block). Step three fires one Pinecone query per embedding in parallel with `top_k * 2` (`:102-111`). Step four dedupes by vector id, keeps first-seen, sorts by score descending, truncates to `top_k * 2` (`:113-128`). Step five reranks if enabled and returns `[:top_k]` (`:130-135`). The naming caveat I'd flag: it's called *hybrid* but there's no keyword index — every variant still goes through the vector store."

**③ Walk me through `CitationGenerator.generate`.**
*Strong answer:* "`server/app/retrieval/generator.py:52-66`. It builds messages via `_build_messages` (`:38-50`): a system prompt at `:23-33` that requires `[document_id]` after every claim, and a user message containing a sources block. The sources block comes from `_build_context` (`:87-97`), which takes only the top `MAX_CONTEXT_SOURCES = 6` (`:17`) and slices each to `MAX_SOURCE_CHARS = 1000` (`:18`) — though the content arriving from Pinecone was already cut to 500 chars at ingest (`pipeline.py:105`, `:180`), so the effective cap is 500. The call itself is `await asyncio.to_thread(self.client.chat, ...)` at `:59-63` — Cohere's SDK is synchronous, so without `to_thread` this would stall the event loop. Citations are recovered afterwards by regex at `:102-119`, matched against retrieved ids; a citation that matches nothing is dropped silently."

**④ Walk me through `get_current_user`.**
*Strong answer:* "`server/app/auth/jwt.py:37-65`. It uses `HTTPBearer` (`:15`), decodes with the configured secret and algorithm (`:47`), and requires both `sub` and `email` claims (`:48-51`); a missing claim or a `JWTError` becomes a 401 (`:41-53`). It then hits the database for the user row (`:55-58`) rather than trusting claims — good, because it means revocation works on `is_active`. Then three checks in order: `is_active` → 400 (`:59-60`), `user.email != token_email` → 401 (`:61-62`), and `is_approved` → 403 (`:63-64`). The reason the approval gate holds everywhere is that this is a *dependency*, so it runs before any handler. Two things I'd note: the token has no `is_admin` claim, so admin status is re-read from the DB each request (correct, but it costs a query), and there's no revocation list, so a token stays valid until its `exp` (`:26-34`, default `JWT_EXPIRATION_MINUTES`, `config.py:23`)."

**⑤ Walk me through `ingest_single_document`.**
*Strong answer:* "`server/app/ingestion/pipeline.py:130-203`. It parses through `ParserRouter` (`:143`), builds a `DocumentMetadata` from the caller-supplied dict (`:146-154`) — note it does *not* run `MetadataEnricher`, which only executes inside `ingest_from_connector` at `:76`, so keyword-based access-level inference never happens on this path. It writes the Postgres row via `_store_document` (`:157-163` → `:205-231`, flushed at `:230`), chunks with `SemanticChunker` (`:166-169`), then embeds each chunk in a loop with `await _get_embedding` (`:173-191`). `_get_embedding` (`:13-25`) is declared `async` but calls `client.embed(...)` synchronously at `:19-23`, so it blocks — one blocking HTTP call per chunk. Vectors carry `content[:500]` (`:180`) and the client-supplied `access_level` (`:186`). Everything commits at `:202`, and exceptions are swallowed into `result.errors` at `:199-200`, so a partial failure still returns HTTP 200 with an errors array."

---

## Additional likely questions

**1. Why Pinecone instead of pgvector or Qdrant?**
What the code says: `server/app/db/pinecone.py:1-22` uses the serverless Pinecone client with a `ServerlessSpec(cloud="aws", region=...)` (`:35`), dimension 1024 to match Cohere's `embed-english-v3.0` (`server/app/config.py:14,18`, index creation at `server/app/main.py:49-55`). `PLAN.md:58-77` lists it as "serverless, metadata filtering, zero ops". Honest counter you should pre-empt: a Postgres table already exists for chunks (`server/app/ingestion/pipeline.py:241-247`), so pgvector would have removed an entire consistency surface — and given the delete path never reaches Pinecone (`server/app/api/documents.py:109-132`), that trade-off actually bit.

**2. How would you add true account-level isolation?**
Four steps, all cited: write `account_id` into Pinecone metadata at ingest (already done — `pipeline.py:184`); emit an `account_id in [...]` clause from `build_filter`, reusing `get_user_allowed_account_ids` (`permissions.py:71-83`, currently imported at `permission_filter.py:6` and unused); decide the admin/empty-list semantics (today "empty means no filter", `permissions.py:75` — that's a footgun); then add a test that a user with one account can't retrieve another account's vector.

**3. What happens when Cohere goes down?**
`CohereReranker.rerank_safe` exists as a safe-fallback path (referenced from `search.py:130-135`, class in `server/app/retrieval/reranker.py`). For generation there's no fallback: `generator.py:59-63` raises, `queries.py:147-163` maps it, and Pinecone-specific failures become a 503 with a generic message (`:155-159`) while everything else becomes a 500 that includes `str(e)[:200]` (`:160-163`). Embeddings have no fallback either — `search.py:142-153` will raise and the query fails outright.

**4. How do you prevent prompt injection?**
`NOT FOUND IN CODE`. Retrieved content is interpolated into the user message at `generator.py:41-46` with no "treat the following as data" framing and no delimiter beyond `---` (`:97`). The right answer: delimit and label untrusted content, instruct the model that source text is data not instructions, add injection canaries to the golden set, and never let retrieved text select tools or change the authorization decision — the last part is already safe, because authorization happens before retrieval (`search.py:102-111`).

**5. Is the audit log real?**
Partially. `TraceLogger` records `trace_id`, `user_id`, `user_email`, `query`, retrieved chunks, answer, citations, latency and error (`server/app/tracing/logger.py:9-22`, serialized at `:81-95`). But it's `self.traces: list` on a module-level singleton (`:34`, `:99`) — unbounded, in-memory, lost on restart, per-instance under serverless. `log_permission_filter` (`:50-52`) is never called, so `permission_filter` in every trace is `None`. Nothing is written to Postgres. For a compliance claim, that's not sufficient; say so.

**6. Why is `access_level` an int instead of an enum?**
`AccessLevel(int, Enum)` at `server/app/auth/permissions.py:9-13` — 0/1/2/3 — so it can be compared numerically and used directly in a Pinecone `$lte` filter (`permission_filter.py:33`) and a SQL `<=` (`documents.py:61`). The cost is that integers can be forged: `ingestion.py:34` accepts any `int`, so a client can post `access_level=0` or `access_level=3`.

**7. What's your biggest latency risk?**
Per-chunk synchronous embedding at `pipeline.py:173-191` (one blocking call per chunk, `_get_embedding` at `:13-25`), the blocking Pinecone wrapper (`db/pinecone.py:38-60` — all four methods are `async def` wrapping sync `self.index.*` calls with no `to_thread`), and the streaming generator (`generator.py:75-85`). Note the inconsistency that makes this a good answer: embeddings in search *are* wrapped (`search.py:147`) and non-streaming generation *is* wrapped (`generator.py:59`), so someone consciously fixed two of the four and left the others.

**8. How would you make this production-ready?**
Ordered: rotate and purge the leaked credentials (see **Security findings** below); fix CI (branch `main`→`master`, `backend`→`server`, `pytest` paths at `.github/workflows/ci.yml:5,22,59,102`); make `total_leaks` real (`eval/evaluator.py:347-365`); add the Pinecone delete call to `delete_document`; collapse the two access-level implementations; move traces to Postgres; add rate limiting; replace the keyword question classifier with something semantic or drop it in favour of the filter alone.

**9. What does "zero leakage" mean in your README, and is it true?**
Careful here. `README.md` and `PLAN.md:460` state Unauthorized Leakage Rate = 0.0 as a target. The evaluator's implementation of that metric cannot exceed 0 (`eval/evaluator.py:347-365` + `:387` + `:423`), so the *number* is not evidence. What is evidence: the three genuine checks in `tests/security/test_permission_leakage.py:226-228`, `:261-263`, and the infra-error assertion at `:330-333` — and those require live services I did not run. And one untracked artifact records `confidential_leaks=1` for the Internal role (`server/eval_results_full.json`).

**10. Why are there two `pyproject.toml` files?**
Root `pyproject.toml` is 16 lines of ruff config (plus a 9-line pytest block that is **uncommitted** — `git diff pyproject.toml`). `server/pyproject.toml:1-62` holds the Poetry package, dependencies, mypy strict (`:53-55`), and pytest config with `testpaths = ["tests"]` (`:57-59`). The CI workflow runs `poetry install` from `working-directory: backend` (`.github/workflows/ci.yml:22,59`), so it never reads either one correctly today.

**11. How do you handle concurrent writes?**
Not handled as a design — `pipeline.py:229-230` uses `flush()` then a single `commit()` at `:202`, and `_store_chunks` interleaves Postgres adds with a Pinecone upsert (`:249-251`) outside any transaction boundary. SQLAlchemy's async session is per-request (`server/app/db/sessions.py:46-51`), `pool_pre_ping` and `pool_recycle=300` are set (`:31-32`), but there's no optimistic locking, no idempotency key on ingest — the `/direct` endpoint derives its source id from `hash(request.content)` (`ingestion.py:101`), which is `hash()` and therefore randomized per process in Python 3.13.

**12. What would you test differently with more time?**
A property-based test over `get_question_access_level` (paraphrases must not change the ceiling), a store-reconciliation test (Postgres vs Pinecone), a cross-endpoint equivalence test for the two access-level functions, an injection canary suite, and a `GET /api/query/trace/{id}` ownership test — none of which exist today.

---

## Weaknesses and honest framing

The pattern for all of these: **name it first, say what you'd change, don't over-apologize.**

| Weakness | One-line framing you can say out loud | Evidence |
|---|---|---|
| Only `access_level` is enforced | "The model is real but narrower than the docs imply — account and role overrides are modelled and tested, then not wired into the serving filter. That's a wiring gap, not a design flaw, and it's a two-line fix plus a test." | `permission_filter.py:6,21-33`; `permissions.py:96-130` unused |
| Deleted docs stay searchable | "Delete is a Postgres-only operation. I'd add one call to `delete_vectors` and a reconciliation sweep." | `documents.py:109-132`; `pinecone.py:56-60` (0 callers) |
| Any approved user can ingest at any level | "Authorization covers reading much better than writing. Ingest needs the same `require_admin` gate that admin routes already have." | `ingestion.py:34,25`; compare `admin.py:36-42` |
| Trace IDOR | "I built the trace endpoint for debugging and never added the ownership check. It's a one-line `if trace.user_id != current_user.id`." | `queries.py:241-251` |
| Leakage metric is a tautology | "The metric I advertised is computed by code that can't produce a non-zero value. The underlying tests are real; the number isn't. I'd make `total_leaks` derive from citations checked against `Document.access_level`." | `evaluator.py:347-365,387,423` |
| Two access-level implementations | "Same concept, two functions, two answers. Consolidate on the column, delete the name map." | `permissions.py:60-68` vs `documents.py:39-50` |
| Keyword question ceiling | "It's a cheap guardrail, not security. The Pinecone pre-filter is the actual control; this just short-circuits obvious questions. I'd either make it semantic or stop calling it a security rule." | `permissions.py:16-57` |
| Blocking I/O in async paths | "I fixed the two I could measure (`search.py:147`, `generator.py:59`) and left the Pinecone wrapper and the stream. The stream freezes the event loop for everyone." | `pinecone.py:38-60`; `generator.py:75-85` |
| CI never ran | "The workflow targets a branch and a directory name that don't exist. Nothing in this repo has ever been gated by CI — I found that in the audit, not before." | `.github/workflows/ci.yml:5,7,22,59` |
| Two committed tests fail | "I ran them instead of trusting them. Two assertions drifted after the prompt and expansion logic changed — that's exactly the failure mode of writing tests and code in parallel." | `server/tests/test_search.py:7`, `test_conversation_context.py:20` |
| README/PLAN overclaim | "BM25, Groq, account scoping, document overrides — the docs describe a target state. I'd either implement or annotate each one; right now they're aspirational." | `README.md:36,53,77`; `PLAN.md:259,261` |
| Secrets in a public repo | "That's the finding I'd fix first, before any code. Rotation, then history purge, then the scanner that already exists but is configured to skip the files where the secrets live." | see **Security findings** below |

**What to say if they push on "did you write this yourself?"** Don't litigate authorship. Say: "The repo has no record of which tool produced which line — no `AGENTS.md`, no `CLAUDE.md`, no generated-code markers. What I can show you is the verification: these 50 tests pass, these 2 fail, these 28 need live credentials, and here are the six places where I reviewed generated code and changed the behaviour." Then cite Q3.

---

## Security findings

Twelve findings across 5 Critical, 3 High, 2 Medium and 2 Low, 10 of them present in the working tree at the time of writing. Summary here — **every secret value below is written `<REDACTED> (len=N)`. No secret, prefix, suffix, or fragment of a secret is reproduced in this document.** Lengths are kept because they're enough to identify a credential in rotation logs without disclosing it.

| ID | What | Where | Redacted value | Severity |
|---|---|---|---|---|
| F-01 | Pinecone API key | `server/app/db/pinecone.py:5` (history); `server/.env`, `server/.env.production` (local, ignored) | `<REDACTED> (len=75)` | **Critical** |
| F-02 | Cohere API key | `server/env.production:1`, `server/app/config.py:17` (history); local env files | `<REDACTED> (len=53)` | **Critical** |
| F-03 | Neon Postgres connection string + superuser password | `server/scripts/check_nist.py:2` (**present, untracked, working tree**); multiple history paths | conn `<REDACTED> (len=101)`, pw `<REDACTED> (len=16)` | **Critical** |
| F-04 | JWT HS256 signing secret | `server/env.production:6`, `server/app/config.py:21` (history); local env files | `<REDACTED> (len=86)` | **Critical** |
| F-05 | A real person's account password | `.env.example:17` (**ignored file, working tree**) | `<REDACTED> (len=11)` | **Critical** |
| F-06 | Six deployed-app account passwords (incl. admin) in tracked scripts | `server/scripts/check_access_filter.py`, `create_role_test_users.py`, `role_matrix_runner.py`, `evaluate_users.py`, `evaluate_ambiguous.py` | `<REDACTED>` ×6 (lens 8, 14, 16, 20, 18, 13) | **High** |
| F-07 | Deployed-app password in `server/scripts/debug_nist.py:4` (**untracked**) | working tree | `<REDACTED> (len=13)` | **High** |
| F-08 | Secrets inside a non-standard git ref (`refs/codex/turn-diffs/checkpoints/…`) | reachable git objects | `<REDACTED>` — same two values as F-01 and F-02 | **High** |
| F-09 | Weak default JWT fallback secret | `server/app/config.py:11`, `server/docker-compose.yml:13` (history) | `<REDACTED> (len=17)` | **Medium** |
| F-10 | Vercel OIDC token in `.env.local:2` (ignored) | working tree | `<REDACTED> (len=1260)` | **Medium** |
| F-11 | CI hardcoded test credentials | `.github/workflows/ci.yml:66,81` (**tracked at HEAD**) | `<REDACTED> (len=12)`, `<REDACTED> (len=22)` | **Low** |
| F-12 | Dev docker DB credentials | `server/docker-compose.yml:9,25`, `PLAN.md:475`, `server/.env.example:8`, `.env.example:2` | `<REDACTED> (len=27)`, user `<REDACTED>` | **Low** |

**Additional credential found while writing this document, not in the table above:** `server/scripts/eval_full.py:8-9` and `server/scripts/eval_full_v2.py:8-9` read two account passwords from environment variables, but `server/scripts/eval_full.py:15` hardcodes a third directly in the script — a deployed-app test account password, `<REDACTED> (len=14)`. Both scripts are **untracked** in the working tree, so this one is not yet in git history. Same treatment as F-07: it belongs in the working-tree bucket of the audit.

**Why the scanner didn't stop any of this:** `.pre-commit-config.yaml:60-64` declares TruffleHog, but the *installed* `.git/hooks/pre-commit` is a custom script whose `EXCLUDE_PATTERNS` matches `scripts/check_*`, `scripts/create_*`, `scripts/test_*`, `scripts/evaluate*`, `eval_results`, `.json`, and `.md` — which is precisely the naming pattern of the offending scripts. The GitHub workflow also declares TruffleHog and Trivy (`.github/workflows/ci.yml`, `security` job) but has never executed, because the workflow triggers on branches this repository doesn't have.

**Priority order if asked "what would you do first?":** rotate Pinecone, Cohere, Neon, and the JWT secret; then purge history (including the `refs/codex/` ref); then fix the exclusion list so the scanner actually scans; then fix CI so every future commit is checked.
