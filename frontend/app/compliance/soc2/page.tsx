"use client";

import { SubPageLayout } from "@/components/SubPageLayout";

export default function SOC2Page() {
  return (
    <SubPageLayout>
        <div className="b-label mb-4">Compliance / SOC 2</div>
        <h1 className="b-h2 mb-6">SOC 2 Type II</h1>
        <p className="text-ink-muted text-lg max-w-2xl mb-16">
          Vault is designed to meet SOC 2 Type II requirements for security, availability, and confidentiality.
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Security</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Role-based access control enforced at query time</li>
              <li>JWT authentication with secure token handling</li>
              <li>Password hashing with bcrypt</li>
              <li>CORS configuration for allowed origins</li>
              <li>Pre-commit hooks for credential scanning</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Availability</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Deployed on Vercel with 99.9% uptime SLA</li>
              <li>PostgreSQL on Neon with automatic failover</li>
              <li>Pinecone managed vector database</li>
              <li>Health check endpoint at /health</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Confidentiality</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Permission filtering before retrieval</li>
              <li>Unauthorized content never reaches the LLM</li>
              <li>Full trace logging for audit trails</li>
              <li>Document-level access control</li>
            </ul>
          </div>
          <div className="b-card">
            <h3 className="font-bold text-xl mb-4">Processing Integrity</h3>
            <ul className="space-y-2 text-ink-muted text-sm">
              <li>Cohere reranking for relevance accuracy</li>
              <li>Citation tracking for answer verification</li>
              <li>Golden set evaluation framework</li>
              <li>Keyword recall scoring</li>
            </ul>
          </div>
        </div>

        <div className="border-t-2 border-border pt-12">
          <h2 className="b-h2 mb-6">Audit trail format</h2>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>trace log</span>
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
  "citations": [...],
  "latency_ms": 1210,
  "timestamp": "2026-09-21T12:00:00Z"
}`}</pre>
          </div>
        </div>
    </SubPageLayout>
  );
}
