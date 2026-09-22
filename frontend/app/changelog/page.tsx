"use client";

import { SubPageLayout } from "@/components/SubPageLayout";

const CHANGES = [
  {
    version: "1.0.0",
    date: "2026-09-21",
    changes: [
      { type: "feature", text: "Brutalist landing page with interactive pipeline demo" },
      { type: "feature", text: "7 source connectors: Zendesk, Jira, Slack, Confluence, Transcripts, CSV, Policy docs" },
      { type: "feature", text: "Permission-first architecture with pre-retrieval RBAC filtering" },
      { type: "feature", text: "Hybrid search: vector similarity + BM25 keyword matching" },
      { type: "feature", text: "Cohere cross-encoder reranking" },
      { type: "feature", text: "Cited generation with trace logging" },
      { type: "feature", text: "4-tier access control: Public, Internal, Confidential, Restricted" },
      { type: "feature", text: "Golden set evaluation framework (5 questions x 9 users)" },
      { type: "fix", text: "Permission filter correctly uses access_level instead of non-existent allowed_roles field" },
      { type: "fix", text: "Parallel Pinecone queries for original + expanded search terms" },
      { type: "fix", text: "Asyncio.to_thread wrapping for Cohere SDK calls" },
    ],
  },
  {
    version: "0.1.0",
    date: "2026-09-15",
    changes: [
      { type: "feature", text: "Initial deployment to Vercel" },
      { type: "feature", text: "FastAPI backend with PostgreSQL + Pinecone" },
      { type: "feature", text: "JWT authentication system" },
      { type: "feature", text: "Document ingestion pipeline" },
      { type: "feature", text: "Next.js 14 frontend with shadcn/ui" },
    ],
  },
];

const TYPE_COLORS = {
  feature: "accent",
  fix: "text-emerald-400",
  breaking: "text-rose-400",
};

export default function ChangelogPage() {
  return (
    <SubPageLayout>
        <div className="b-label mb-4">Changelog</div>
        <h1 className="b-h2 mb-16">Release history</h1>

        <div className="space-y-16">
          {CHANGES.map((release) => (
            <div key={release.version}>
              <div className="flex items-center gap-4 mb-6">
                <span className="b-stat-num text-3xl">{release.version}</span>
                <span className="mono text-[11px] text-ink-subtle">{release.date}</span>
              </div>
              <div className="border-t-2 border-border">
                {release.changes.map((change, i) => (
                  <div key={i} className="b-row items-center">
                    <span className={`mono text-[11px] uppercase tracking-widest ${TYPE_COLORS[change.type as keyof typeof TYPE_COLORS]}`}>
                      {change.type}
                    </span>
                    <span className="text-ink-muted">{change.text}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>
    </SubPageLayout>
  );
}
