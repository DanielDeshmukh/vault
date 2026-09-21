"use client";

import Link from "next/link";

export default function AuditPage() {
  return (
    <div className="brutalist min-h-screen">
      <header className="sticky top-0 z-50 bg-background border-b-2 border-foreground">
        <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <span className="w-8 h-8 bg-foreground flex items-center justify-center text-background font-bold text-lg">V</span>
            <span className="font-bold tracking-tight text-lg">VAULT</span>
          </Link>
          <Link href="/" className="b-btn !py-2 !px-4 text-[11px]">Back to Home</Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 md:px-12 py-20">
        <div className="b-label mb-4">Compliance / Audit Logging</div>
        <h1 className="b-h2 mb-6">Audit Logging</h1>
        <p className="text-ink-muted text-lg max-w-2xl mb-16">
          Every query, retrieval, and answer is logged with full context for compliance, debugging, and security investigation.
        </p>

        <div className="mb-16">
          <h2 className="b-h2 mb-8">What gets logged</h2>
          <div className="border-t-2 border-foreground">
            <div className="b-row grid-cols-12 b-label !py-3 border-b-2 !border-foreground">
              <div className="col-span-3">Field</div>
              <div className="col-span-5">Description</div>
              <div className="col-span-4">Example</div>
            </div>
            {[
              { field: "trace_id", desc: "Unique identifier for the query", example: "7f3a-c21e" },
              { field: "user_id", desc: "Authenticated user ID", example: "usr_abc123" },
              { field: "email", desc: "User email address", example: "engineer@vaultdemo.com" },
              { field: "role", desc: "Assigned role name", example: "Internal" },
              { field: "access_level", desc: "Numeric access tier (0-3)", example: "1" },
              { field: "question", desc: "Original query text", example: "What is our SLA policy?" },
              { field: "chunks_retrieved", desc: "Number of chunks passed to LLM", example: "5" },
              { field: "chunks_blocked", desc: "Number of chunks filtered out", example: "3" },
              { field: "citations", desc: "Source references in the answer", example: "[{source, chunk_id, score}]" },
              { field: "latency_ms", desc: "Total query processing time", example: "1210" },
              { field: "timestamp", desc: "ISO 8601 timestamp", example: "2026-09-21T12:00:00Z" },
            ].map((row) => (
              <div key={row.field} className="b-row grid-cols-12 items-center">
                <div className="col-span-12 md:col-span-3 mono text-[11px] accent">{row.field}</div>
                <div className="col-span-12 md:col-span-5 text-ink-muted text-sm">{row.desc}</div>
                <div className="col-span-12 md:col-span-4 mono text-[11px] text-ink-subtle">{row.example}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-16">
          <h2 className="b-h2 mb-8">Sample trace log</h2>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>trace output</span>
            </div>
            <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`{
  "trace_id": "7f3a-c21e",
  "user_id": "usr_abc123",
  "email": "engineer@vaultdemo.com",
  "role": "Internal",
  "access_level": 1,
  "question": "What is our SLA policy?",
  "chunks_retrieved": 5,
  "chunks_blocked": 3,
  "citations": [
    {
      "source": "confluence://policies/sla",
      "chunk_id": "chunk_456",
      "score": 0.94
    },
    {
      "source": "zendesk://tickets/12345",
      "chunk_id": "chunk_789",
      "score": 0.87
    }
  ],
  "latency_ms": 1210,
  "timestamp": "2026-09-21T12:00:00Z"
}`}</pre>
          </div>
        </div>

        <div className="border-t-2 border-border pt-12">
          <h2 className="b-h2 mb-6">Querying traces</h2>
          <p className="text-ink-muted mb-6">
            Traces are stored in PostgreSQL and can be queried for compliance reporting, security investigation, and performance analysis.
          </p>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>sql</span>
            </div>
            <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`-- Find all queries by a user
SELECT * FROM query_traces
WHERE user_id = 'usr_abc123'
ORDER BY timestamp DESC;

-- Count blocked chunks per role
SELECT role, SUM(chunks_blocked) as total_blocked
FROM query_traces
GROUP BY role;

-- Average latency by access level
SELECT access_level, AVG(latency_ms) as avg_latency
FROM query_traces
GROUP BY access_level;`}</pre>
          </div>
        </div>
      </main>
    </div>
  );
}
