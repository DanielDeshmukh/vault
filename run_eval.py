#!/usr/bin/env python3
"""Run the Vault evaluation against the live API.

Usage:
    # Quick eval: 3 questions per role (1 easy, 1 tricky, 1 out-of-scope)
    # Runs all 8 roles by default, ~24 queries total (~2-3 minutes)
    python run_eval.py --quick

    # Full eval: all 30 questions × all 8 roles = 240 queries
    python run_eval.py --full

    # Quick eval for specific roles only
    python run_eval.py --quick --roles admin intern engineer

    # Full eval for a single role
    python run_eval.py --full --roles admin

    # Custom base URL (local dev):
    python run_eval.py --quick --base-url http://localhost:8000

    # Save report to custom path:
    python run_eval.py --quick --output my_report.md

    # Limit concurrency (rate limiting):
    python run_eval.py --quick --concurrency 2

    # Filter by category:
    python run_eval.py --full --categories easy_lookup edge_case

Flags:
    --quick       Run 3 questions per role (1 easy passing, 1 tricky passing,
                  1 out-of-scope/failing). All 8 roles by default.
                  ~24 queries, ~2-3 minutes.
    --full        Run all 30 questions per role. All 8 roles by default.
                  ~240 queries, ~20-30 minutes.
    --roles       Space-separated list of roles to evaluate.
                  Default: all 8 demo roles (admin, intern, employee, engineer,
                  manager, hr, legal, finance).
    --categories  Filter by question category: easy_lookup, cross_doc_synthesis,
                  permission_boundary, edge_case.
    --base-url    API base URL (default: live Vercel deployment).
    --concurrency Max concurrent API calls (default: 3, reduce if rate-limited).
    --output      Markdown report output path (default: eval_report.md).
    --json-output JSON results output path (default: eval_results.json).

Requirements:
    pip install httpx

This script queries the live Vault API — it does NOT import Pinecone, Cohere,
or any internal app modules. Running it only generates normal query traffic.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

# Add repo root to path so `eval.` imports work when run from repo root
sys.path.insert(0, "")

from eval.api_evaluator import APIEvaluator, print_evaluation_summary, QueryResult
from eval.golden_set_gitlab import (
    get_golden_set,
    get_golden_set_summary,
    get_quick_select,
    QuestionCategory,
)
from eval.report_generator import generate_report


def print_banner(mode: str):
    print("=" * 70)
    print("  Vault Evaluation Runner")
    print(f"  Mode: {mode}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def print_golden_set_info(questions):
    total = len(questions)
    categories = {}
    for q in questions:
        cat = q.category.value
        categories[cat] = categories.get(cat, 0) + 1
    print(f"Questions: {total}")
    print(f"  By category:")
    for cat, count in sorted(categories.items()):
        print(f"    {cat.replace('_', ' ').title()}: {count}")
    quick_count = sum(1 for q in questions if q.quick_select)
    if quick_count:
        print(f"  Quick select questions: {quick_count}")
    print()


async def main():
    parser = argparse.ArgumentParser(
        description="Vault Evaluation Runner — test RBAC and RAG quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default="https://vault-rbac-rag.vercel.app",
        help="Base URL of the Vault API (default: live deployment)",
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        default=None,
        help="Roles to evaluate (default: all 8 demo roles)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["easy_lookup", "cross_doc_synthesis", "permission_boundary", "edge_case"],
        default=None,
        help="Categories to evaluate (default: all)",
    )
    parser.add_argument(
        "--output",
        default="eval_report.md",
        help="Output report file path (default: eval_report.md)",
    )
    parser.add_argument(
        "--json-output",
        default="eval_results.json",
        help="JSON results file path (default: eval_results.json)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max concurrent API calls (default: 3)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 3 questions per role (1 easy, 1 tricky, 1 out-of-scope). "
        "All 8 roles by default. ~24 queries, ~2-3 minutes.",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="Full mode: all 30 questions per role. All 8 roles by default. "
        "~240 queries, ~20-30 minutes.",
    )
    args = parser.parse_args()

    # Determine mode
    if args.quick:
        mode = "quick"
        questions = get_quick_select()
    elif args.full:
        mode = "full"
        questions = get_golden_set()
    else:
        # Default to quick mode for convenience
        mode = "quick"
        questions = get_quick_select()
        print("Note: No mode specified, defaulting to --quick (3 questions per role).")
        print("      Use --full for all 30 questions per role.\n")

    # Filter questions by category if specified
    if args.categories:
        category_enums = [QuestionCategory(c) for c in args.categories]
        questions = [q for q in questions if q.category in category_enums]

    print_banner(mode)

    # Print config
    print(f"Base URL: {args.base_url}")
    print(f"Roles: {', '.join(args.roles) if args.roles else 'all 8 demo roles'}")
    print(f"Categories: {', '.join(args.categories) if args.categories else 'all'}")
    print(f"Questions per role: {len(questions)}")
    print(f"Concurrency: {args.concurrency}")
    total_queries = len(questions) * (len(args.roles) if args.roles else 8)
    print(f"Total queries: ~{total_queries}")
    print()

    # Initialize evaluator
    evaluator = APIEvaluator(base_url=args.base_url)

    # Login
    print("Logging in as all roles...")
    await evaluator.login_all_roles()
    if args.roles:
        available = [r for r in args.roles if r in evaluator.tokens]
        if not available:
            print("ERROR: No roles could login successfully")
            sys.exit(1)
        eval_roles = available
    else:
        eval_roles = list(evaluator.tokens.keys())
    print(f"Logged in as: {', '.join(eval_roles)}")
    print()

    # Run evaluation with the selected questions
    print("Running evaluation...")
    start_time = time.monotonic()
    results = await evaluator.run_evaluation(
        roles=eval_roles,
        questions=questions,
        max_concurrent=args.concurrency,
    )
    elapsed = time.monotonic() - start_time
    print(f"Completed in {elapsed:.1f}s")
    print()

    # Print summary
    summary = print_evaluation_summary(results)
    print("=" * 70)
    print("  EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total queries:    {summary['total_queries']}")
    print(f"Successful:       {summary['successful']}")
    print(f"Errors:           {summary['errors']}")
    print(f"Refused:          {summary['refused']}")
    print(f"With citations:   {summary['with_citations']}")
    print(f"Avg latency:      {summary['avg_latency_ms']:.0f}ms")
    print(f"Avg relevance:    {summary['avg_relevance']:.2%}")
    print()

    print("By Role:")
    for role, data in summary["by_role"].items():
        print(f"  {role:12s} | {data['total']:3d} queries | "
              f"{data['successful']:3d} success | "
              f"{data['refused']:3d} refused | "
              f"rel={data['avg_relevance']:.2%} | "
              f"lat={data['avg_latency_ms']:.0f}ms")
    print()

    print("By Category:")
    for cat, data in summary["by_category"].items():
        print(f"  {cat:25s} | {data['total']:3d} queries | "
              f"{data['successful']:3d} success | "
              f"rel={data['avg_relevance']:.2%}")
    print()

    # RBAC comparison (admin vs intern)
    if "admin" in summary["by_role"] and "intern" in summary["by_role"]:
        admin_data = summary["by_role"]["admin"]
        intern_data = summary["by_role"]["intern"]
        print("RBAC Comparison (Admin vs Intern):")
        print(f"  Admin relevance:   {admin_data['avg_relevance']:.2%}")
        print(f"  Intern relevance:  {intern_data['avg_relevance']:.2%}")
        admin_citations = sum(
            1 for r in results if r.role == "admin" and r.has_citations
        )
        intern_citations = sum(
            1 for r in results if r.role == "intern" and r.has_citations
        )
        admin_total = len([r for r in results if r.role == "admin"])
        intern_total = len([r for r in results if r.role == "intern"])
        print(f"  Admin with citations: {admin_citations}/{admin_total}")
        print(f"  Intern with citations: {intern_citations}/{intern_total}")
        print()

    # Save JSON results
    json_data = {
        "run_time": datetime.now().isoformat(),
        "mode": mode,
        "elapsed_seconds": elapsed,
        "summary": summary,
        "results": [
            {
                "question_id": r.question_id,
                "question": r.question,
                "category": r.category,
                "role": r.role,
                "answer": r.answer[:1000],  # Truncate for JSON size
                "citations": r.citations,
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp,
                "success": r.success,
                "relevance_score": r.relevance_score,
                "has_citations": r.has_citations,
                "citation_count": r.citation_count,
                "refused": r.refused,
                "error": r.error,
            }
            for r in results
        ],
    }
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"JSON results saved to: {args.json_output}")

    # Generate markdown report
    report = generate_report(results, output_path=args.output)
    print(f"Markdown report saved to: {args.output}")
    print()
    print("=" * 70)
    print("  EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
