# Vault Evaluation Guide

Quick-start guide for running the automated evaluation system. Tests RBAC (role-based access control) and RAG (retrieval-augmented generation) quality against the live API.

---

## Prerequisites

```bash
pip install httpx
```

That's the only dependency. The eval treats the live API as a black box — no Pinecone, Cohere, or database access needed.

---

## Quick Start

### 1. Run a Quick Eval (Recommended)

Tests **3 questions per role** across all 8 roles (~24 queries, ~2–3 minutes):

```bash
python run_eval.py --quick
```

**What it does:**
- **1 easy question** — straightforward factual query about the GitLab handbook corpus
- **1 tricky question** — cross-document synthesis requiring deeper reasoning
- **1 out-of-scope question** — irrelevant query that should be refused by the system

### 2. Run a Full Eval

Tests **all 30 questions per role** across all 8 roles (~240 queries, ~20–30 minutes):

```bash
python run_eval.py --full
```

---

## Common Commands

### Quick eval for specific roles

```bash
# Admin vs Intern comparison (most common)
python run_eval.py --quick --roles admin intern

# All engineering roles
python run_eval.py --quick --roles admin engineer manager
```

### Full eval for a single role

```bash
# Deep dive on admin only
python run_eval.py --full --roles admin
```

### Reduce concurrency (if rate-limited)

```bash
python run_eval.py --quick --concurrency 2
```

### Filter by question category

```bash
# Only easy lookup questions
python run_eval.py --full --categories easy_lookup

# Edge cases only
python run_eval.py --quick --categories edge_case
```

### Custom output paths

```bash
python run_eval.py --quick --output my_report.md --json-output my_results.json
```

### Local development

```bash
python run_eval.py --quick --base-url http://localhost:8000
```

---

## All Command-Line Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--quick` | 3 questions per role (1 easy, 1 tricky, 1 out-of-scope) | All 8 roles |
| `--full` | All 30 questions per role | All 8 roles |
| `--roles` | Space-separated roles to test | All 8 demo roles |
| `--categories` | Filter by category | All categories |
| `--base-url` | API base URL | Live Vercel deployment |
| `--concurrency` | Max concurrent API calls | 3 |
| `--output` | Markdown report path | `eval_report.md` |
| `--json-output` | JSON results path | `eval_results.json` |

**Note:** `--quick` and `--full` are mutually exclusive. If neither is specified, the eval defaults to `--quick`.

---

## Available Roles

| Role | Documents Visible | Use Case |
|------|-------------------|----------|
| `admin` | 4,879 | Full access baseline |
| `manager` | 3,397 | Mid-level access |
| `engineer` | 3,099 | Technical docs |
| `legal` | 2,661 | Legal/policy docs |
| `employee` | 2,076 | General staff |
| `hr` | 1,648 | HR documents |
| `finance` | 1,619 | Financial docs |
| `intern` | 1,556 | Restricted access |

All roles log in with password `Vault2026!`.

---

## Question Categories

| Category | Description | Count |
|----------|-------------|-------|
| `easy_lookup` | Single-source factual questions | 15 |
| `cross_doc_synthesis` | Multi-document synthesis | 5 |
| `permission_boundary` | Tests RBAC filtering | 5 |
| `edge_case` | Out-of-scope / adversarial | 5 |

---

## Output Files

### eval_report.md

Human-readable markdown report with:
- Per-question results (query, answer, citations, latency)
- Relevance scores per role
- RBAC comparison (admin vs intern)
- Error summary

### eval_results.json

Machine-readable JSON with:
- All query results
- Timing data
- Mode and configuration used
- Per-question metadata

---

## Understanding the Output

### Console Output

```
======================================================================
  Vault Evaluation Runner
  Mode: quick
  Started: 2026-11-10 23:00:00
======================================================================

Base URL: https://vault-rbac-rag.vercel.app
Roles: all 8 demo roles
Questions per role: 3
Total queries: ~24

Running evaluation...
  Progress: 10/24 queries completed
  Progress: 20/24 queries completed
Completed in 45.2s

======================================================================
  EVALUATION SUMMARY
======================================================================
Total queries:    24
Successful:       22
Errors:            2
Refused:           8
With citations:   14
Avg latency:      21000ms
Avg relevance:    65.00%

By Role:
  admin        |   3 queries |   3 success |   1 refused | rel=66.67% | lat=20000ms
  intern       |   3 queries |   3 success |   1 refused | rel=63.33% | lat=22000ms
```

### Key Metrics

- **Relevance (%)** — How well the answer matches the expected topic (keyword-based scoring)
- **Refused** — Queries correctly refused when out of scope (higher is better for edge cases)
- **With citations** — Queries that returned source document references
- **Latency** — End-to-end query time in milliseconds

---

## Troubleshooting

### Rate Limiting (429 errors)

If you see many errors, reduce concurrency:

```bash
python run_eval.py --quick --concurrency 1
```

### Login Failures

Ensure the live deployment is accessible:

```bash
curl -s https://vault-rbac-rag.vercel.app/api/health
```

Expected: `{"status":"healthy"}`

### No Results

Check that `httpx` is installed:

```bash
pip install httpx
```

---

## File Structure

```
run_eval.py              # Main entry point
eval/
├── golden_set_gitlab.py # 30 questions targeting GitLab handbook
├── api_evaluator.py     # API client and relevance scoring
└── report_generator.py  # Markdown report generator
```

---

## For the Interview

**Recommended demo flow:**

1. Run quick eval: `python run_eval.py --quick --roles admin intern`
2. Show the console output — highlight RBAC differences
3. Open `eval_report.md` — walk through per-question results
4. Point out that out-of-scope queries are correctly refused
5. Show that admin gets more citations than intern (more document access)
