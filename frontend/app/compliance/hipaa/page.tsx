"use client";

import Link from "next/link";

export default function HIPAAPage() {
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
        <div className="b-label mb-4">Compliance / HIPAA</div>
        <h1 className="b-h2 mb-6">HIPAA Compliance</h1>
        <p className="text-ink-muted text-lg max-w-2xl mb-16">
          Vault supports HIPAA compliance requirements for organizations handling protected health information (PHI).
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Access Controls</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Unique user identification with JWT tokens</li>
              <li>Role-based access control (4 tiers)</li>
              <li>Emergency access procedures via admin override</li>
              <li>Automatic session expiration</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Audit Controls</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Full trace logging for every query</li>
              <li>User, scope, chunks, scores, answer, latency</li>
              <li>Immutable audit trail</li>
              <li>Trace IDs for incident investigation</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Integrity Controls</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Permission filtering before retrieval</li>
              <li>PHI never exposed to unauthorized roles</li>
              <li>Cited answers with source verification</li>
              <li>Refusal when evidence is insufficient</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Transmission Security</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>HTTPS enforced in production</li>
              <li>SSL for PostgreSQL connections</li>
              <li>Secure cookie handling</li>
              <li>CORS restricted to allowed origins</li>
            </ul>
          </div>
        </div>

        <div className="border-t-2 border-border pt-12">
          <h2 className="b-h2 mb-6">PHI handling</h2>
          <p className="text-ink-muted mb-6">
            When processing documents containing PHI, Vault ensures that only users with the appropriate access level can retrieve and view the content. The permission check happens at the vector database query level, meaning unauthorized content is never loaded into memory, never sent to the language model, and never appears in logs.
          </p>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>permission flow</span>
            </div>
            <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`User authenticates
  -> JWT token issued with user_id
  -> Role resolved from PostgreSQL
  -> Access level determined (0-3)

Query arrives
  -> Permission filter applied to Pinecone query
  -> Only chunks with access_level <= user_level returned
  -> Restricted chunks never enter context window

Answer generated
  -> Only from authorized chunks
  -> Citations point to accessible sources
  -> Full trace logged for audit`}</pre>
          </div>
        </div>
      </main>
    </div>
  );
}
