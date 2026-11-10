#!/usr/bin/env python3
"""Run the Vault evaluation against the live API.

Usage:
    # Full eval (all roles, all questions):
    python run_eval.py

    # Quick eval (admin + intern only):
    python run_eval.py --roles admin intern

    # Single role:
    python run_eval.py --roles admin

    # Custom base URL (local dev):
    python run_eval.py --base-url http://localhost:8000

    # Save report to custom path:
    python run_eval.py --output my_report.md

    # Limit concurrency (rate limiting):
    python run_eval.py --concurrency 2

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
from eval.golden_set_gitlab import get_golden_set_summary, QuestionCategory
from eval.report_generator import generate_report


def print_banner():
    print("=" * 70)
    print("  Vault Evaluation Runner")
    print(f"  Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()


def print_golden_set_info():
    summary = get_golden_set_summary()
    print(f"Golden Set: {summary['total']} questions")
    print(f"  By category:")
    for cat, count in summary["by_category"].items():
        print(f"    {cat.replace('_', ' ').title()}: {count}")
    print(f"  By difficulty:")
    for diff, count in summary["by_difficulty"].items():
        print(f"    {diff}: {count}")
    print()


async def main():
    parser = argparse.ArgumentParser(description="Vault Evaluation Runner")
    parser.add_argument(
        "--base-url",
        default="https://vault-rbac-rag.vercel.app",
        help="Base URL of the Vault API (default: live deployment)",
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        default=None,
        help="Roles to evaluate (default: all demo roles)",
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
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: admin + intern only, fewer questions",
    )
    args = parser.parse_args()

    print_banner()

    if args.quick:
        args.roles = ["admin", "intern"]

    # Print config
    print(f"Base URL: {args.base_url}")
    print(f"Roles: {', '.join(args.roles) if args.roles else 'all demo roles'}")
    print(f"Categories: {', '.join(args.categories) if args.categories else 'all'}")
    print(f"Concurrency: {args.concurrency}")
    print()

    print_golden_set_info()

    # Initialize evaluator
    evaluator = APIEvaluator(base_url=args.base_url)

    # Login
    print("Logging in as all roles...")
    await evaluator.login_all_roles()
    if args.roles:
        # Filter to only requested roles
        available = [r for r in args.roles if r in evaluator.tokens]
        if not available:
            print("ERROR: No roles could login successfully")
            sys.exit(1)
        print(f"Logged in as: {', '.join(available)}")
    else:
        print(f"Logged in as: {', '.join(evaluator.tokens.keys())}")
    print()

    # Convert category strings to enums
    categories = None
    if args.categories:
        categories = [QuestionCategory(c) for c in args.categories]

    # Run evaluation
    print("Running evaluation...")
    start_time = time.monotonic()
    results = await evaluator.run_evaluation(
        roles=args.roles,
        categories=categories,
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
        "run_time": datetime.utcnow().isoformat(),
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
