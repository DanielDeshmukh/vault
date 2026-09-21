"use client";

import { useState } from "react";
import Link from "next/link";
import { Terminal, Pipeline, PermissionSim } from "@/components/Interactive";
import { SiGithub, SiX } from "react-icons/si";
import { FaLinkedinIn } from "react-icons/fa";

const SOURCES = [
  { n: "Zendesk", d: "Tickets, comments, attachments, agent notes" },
  { n: "Jira", d: "Issues, comments, linked docs" },
  { n: "Slack", d: "Channel exports, threads, reactions" },
  { n: "Confluence", d: "Pages, spaces, embedded documents" },
  { n: "Transcripts", d: "Gong / Chorus calls, meeting notes" },
  { n: "Policies", d: "Company docs, SOPs, compliance" },
  { n: "CSV Upload", d: "CRM exports, spreadsheets, datasets" },
];

const FEATURES = [
  {
    k: "01",
    t: "Permission-first architecture",
    d: "Not a post-processing filter. RBAC is enforced at the vector store query. The model only ever sees what the caller is authorized to see.",
  },
  {
    k: "02",
    t: "Hybrid search",
    d: "Vector similarity catches meaning (\u201Cbilling complaint\u201D \u2248 \u201Cinvoice discrepancy\u201D). BM25 catches exact strings: ticket IDs, error codes, proper nouns.",
  },
  {
    k: "03",
    t: "Cross-encoder rerank",
    d: "Merged candidates are re-scored by Cohere Rerank so the top-5 is actually the top-5.",
  },
  {
    k: "04",
    t: "Cited generation",
    d: "Every claim links to its source. If authorized evidence is insufficient, Vault refuses instead of hallucinating.",
  },
  {
    k: "05",
    t: "Full trace logging",
    d: "User, scope, chunks with scores, answer, latency. SOC 2 and HIPAA auditors get the whole story.",
  },
  {
    k: "06",
    t: "Account-scoped access",
    d: "Support agents see their assigned customers. Document-level overrides handle the exceptions.",
  },
];

const USECASES = [
  { who: "Customer Support", q: "What\u2019s the SLA for this customer\u2019s enterprise tier?", src: "contract \u00b7 support history \u00b7 SLA policy" },
  { who: "Account Management", q: "What did we promise in the last renewal call?", src: "call transcript \u00b7 follow-up email \u00b7 amendment" },
  { who: "Engineering Handoff", q: "What was the root cause of the outage affecting Acme Corp?", src: "incident report \u00b7 slack thread \u00b7 post-mortem" },
  { who: "Compliance Audit", q: "Show me all references to data retention policies.", src: "policy docs \u00b7 support scripts \u00b7 training material" },
];

const METRICS = [
  { v: "0.0", l: "Unauthorized leakage rate", s: "Non-negotiable. Exactly zero." },
  { v: "50", l: "Golden-set questions", s: "Lookups, synthesis, conflicts, stale data, refusals, adversarial." },
  { v: "7", l: "Source connectors", s: "One unified permission model." },
  { v: "4", l: "Access tiers", s: "Public \u2192 Internal \u2192 Confidential \u2192 Restricted." },
];

const TECH = ["Cohere Command", "Cohere Embeddings", "Cohere Rerank", "Pinecone", "PostgreSQL", "FastAPI", "BM25", "Python 3.12", "MIT License"];

const MARQUEE = ["PERMISSION BEFORE RETRIEVAL", "CITED OR REFUSED", "LEAKAGE = 0.0", "HYBRID SEARCH", "FULL AUDIT TRAIL", "PRE-RETRIEVAL FILTERING"];

const API_ENDPOINTS = [
  {
    method: "POST",
    path: "/api/query",
    auth: true,
    request: `{
  "question": "What did we promise Acme Corp in the last renewal call?",
  "context": "optional conversation history"
}`,
    response: `{
  "answer": "On the Mar 14 renewal call, we committed to (1) a 99.95% uptime SLA upgrade at no cost [1], (2) dedicated Slack Connect channel by Q2 [2], and (3) a 12-month price lock confirmed in Amendment #3 [3].",
  "citations": [
    {
      "document_id": "doc_8f2a9c1e",
      "title": "acme_renewal_call_0314",
      "source": "gong",
      "score": 0.94
    },
    {
      "document_id": "doc_3b7d4e2f",
      "title": "Acme Amendment #3",
      "source": "confluence",
      "score": 0.91
    }
  ],
  "trace_id": "7f3a-c21e-9b4d"
}`,
  },
  {
    method: "POST",
    path: "/api/auth/register",
    auth: false,
    request: `{
  "email": "j.rivera@globex.com",
  "password": "s3cureP@ss",
  "full_name": "Juan Rivera",
  "department": "Customer Success",
  "designation": "Account Manager"
}`,
    response: `{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": "usr_a1b2c3d4",
    "email": "j.rivera@globex.com",
    "full_name": "Juan Rivera",
    "department": "Customer Success",
    "designation": "Account Manager",
    "is_admin": false,
    "is_approved": false,
    "approval_screen_started_at": "2026-09-21T14:30:00Z"
  }
}`,
  },
  {
    method: "POST",
    path: "/api/auth/login",
    auth: false,
    request: `{
  "email": "j.rivera@globex.com",
  "password": "s3cureP@ss"
}`,
    response: `{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": "usr_a1b2c3d4",
    "email": "j.rivera@globex.com",
    "full_name": "Juan Rivera",
    "department": "Customer Success",
    "designation": "Account Manager",
    "is_admin": false,
    "is_approved": true,
    "approval_screen_started_at": null
  }
}`,
  },
  {
    method: "POST",
    path: "/api/ingest",
    auth: true,
    request: `// multipart/form-data
file: "renewal_policy_q1.pdf"
source: "confluence"
account_id: "acme-corp"
department: "customer-success"
access_level: 2`,
    response: `{
  "documents_processed": 1,
  "chunks_created": 14,
  "errors": []
}`,
  },
  {
    method: "GET",
    path: "/api/documents",
    auth: true,
    request: `// no body required
// Authorization: Bearer <token>`,
    response: `[
  {
    "id": "doc_8f2a9c1e",
    "title": "acme_renewal_call_0314",
    "source": "gong",
    "account_id": "acme-corp",
    "department": "customer-success",
    "access_level": 2,
    "owner_id": "usr_a1b2c3d4",
    "created_at": "2026-03-15T10:00:00Z",
    "can_access": true
  },
  {
    "id": "doc_3b7d4e2f",
    "title": "Data Retention Policy v2.1",
    "source": "confluence",
    "account_id": null,
    "department": "compliance",
    "access_level": 0,
    "owner_id": "usr_sarah_chen",
    "created_at": "2026-01-10T08:30:00Z",
    "can_access": true
  }
]`,
  },
  {
    method: "GET",
    path: "/api/documents/{id}",
    auth: true,
    request: `// no body required
// Authorization: Bearer <token>`,
    response: `{
  "id": "doc_8f2a9c1e",
  "title": "acme_renewal_call_0314",
  "source": "gong",
  "account_id": "acme-corp",
  "department": "customer-success",
  "access_level": 2,
  "owner_id": "usr_a1b2c3d4",
  "created_at": "2026-03-15T10:00:00Z",
  "content": "On the Mar 14 renewal call with Acme Corp, the following commitments were made: 1) 99.95% uptime SLA upgrade at no additional cost...",
  "can_access": true
}`,
  },
  {
    method: "GET",
    path: "/health",
    auth: false,
    request: `// no body required`,
    response: `{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "pinecone": "connected"
}`,
  },
];

function Section({ id, label, children, className = "" }: { id?: string; label: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`b-divider relative px-6 md:px-12 py-20 md:py-28 ${className}`}>
      <span className="b-corner top-3 left-6">{label}</span>
      <span className="b-corner top-3 right-6">&sect;</span>
      <div className="max-w-7xl mx-auto">{children}</div>
    </section>
  );
}

export default function Home() {
  const [activeEndpoint, setActiveEndpoint] = useState(0);
  const ep = API_ENDPOINTS[activeEndpoint];
  return (
    <div className="brutalist min-h-screen">
      {/* NAV */}
      <header className="sticky top-0 z-50 bg-background border-b-2 border-foreground">
        <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <img src="/tab-icon.png" alt="Vault" className="w-8 h-8 rounded" />
            <span className="font-bold tracking-tight text-lg">VAULT</span>
            <span className="b-label hidden md:inline ml-2">/ v1.0</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8 mono text-[11px] uppercase tracking-widest text-ink-subtle">
            <a href="#how" className="hover:text-foreground">How</a>
            <a href="#permissions" className="hover:text-foreground">Permissions</a>
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#eval" className="hover:text-foreground">Eval</a>
            <a href="#api" className="hover:text-foreground">API</a>
          </nav>
          <Link href="/login" className="b-btn !py-2 !px-4 text-[11px]">Get Started</Link>
        </div>
      </header>

      {/* HERO */}
      <section className="b-grid relative px-6 md:px-12 pt-20 pb-24 noise">
        <span className="b-corner top-4 left-6">000 &mdash; HERO</span>
        <span className="b-corner top-4 right-6">52.5200&deg; N, 13.4050&deg; E</span>
        <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7">
            <div className="flex items-center gap-3 mb-8">
              <span className="w-2 h-2 bg-accent blink" />
              <span className="b-label !text-foreground">Permission-aware enterprise knowledge system</span>
            </div>
            <h1 className="b-headline">
              Ask anything.
              <br />
              See only what
              <br />
              you&apos;re <span className="accent">allowed</span> to.
            </h1>
            <p className="mt-8 max-w-xl text-lg md:text-xl text-ink-muted leading-relaxed">
              Vault answers natural-language questions across Zendesk, Jira, Slack, Confluence, call transcripts and policy docs &mdash; with citations &mdash; while enforcing permission boundaries{" "}
              <span className="text-foreground font-bold underline decoration-primary decoration-2 underline-offset-4">before</span> anything reaches the language model.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link href="/register" className="b-btn b-btn-accent">Deploy Vault &rarr;</Link>
              <a href="#how" className="b-btn b-btn-outline">Read the architecture</a>
            </div>
            <div className="mt-12 grid grid-cols-3 max-w-md border-2 border-border-strong divide-x-2 divide-border-strong">
              {[["0.0", "leakage"], ["7", "sources"], ["MIT", "license"]].map(([v, l]) => (
                <div key={l} className="p-4">
                  <div className="text-2xl font-bold accent">{v}</div>
                  <div className="b-label">{l}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="lg:col-span-5">
            <Terminal />
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="b-marquee py-3 bg-accent text-background" aria-hidden="true">
        <div className="b-marquee-track mono text-[12px] font-bold tracking-[0.2em]">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i} className="px-8">
              {m} <span className="ml-8">&bull;</span>
            </span>
          ))}
        </div>
      </div>

      {/* PROBLEM */}
      <Section label="001 &mdash; THE PROBLEM">
        <div className="grid lg:grid-cols-12 gap-12">
          <div className="lg:col-span-5">
            <div className="b-label mb-4">The problem</div>
            <h2 className="b-h2">
              The answer exists. It&apos;s in <span className="accent">three tools</span>, and one of them you shouldn&apos;t open.
            </h2>
            <p className="mt-6 text-ink-muted text-lg leading-relaxed">
              &ldquo;What did we promise this customer?&rdquo; lives in a ticket from last quarter, a Slack thread, and a signed amendment. Next to it sits an HR note, an executive escalation, and another account&apos;s pricing.
            </p>
            <p className="mt-4 text-foreground font-bold text-lg">Vault solves both problems simultaneously.</p>
          </div>
          <div className="lg:col-span-7 grid sm:grid-cols-2 gap-3">
            {SOURCES.map((s, i) => (
              <div key={s.n} className="b-card">
                <span className="b-corner top-2 right-3">0{i + 1}</span>
                <div className="font-bold text-xl uppercase tracking-tight">{s.n}</div>
                <div className="mono text-[11px] text-ink-subtle mt-2">{s.d}</div>
              </div>
            ))}
            <div className="b-card !border-primary bg-primary !text-primary-foreground flex flex-col justify-between">
              <div className="mono text-[10px] tracking-widest uppercase">Unified into</div>
              <div className="font-bold text-2xl leading-none mt-6">ONE PERMISSION MODEL</div>
            </div>
          </div>
        </div>
      </Section>

      {/* HOW IT WORKS */}
      <Section id="how" label="002 &mdash; PIPELINE">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div>
            <div className="b-label mb-4">How it works</div>
            <h2 className="b-h2">Six steps. Filtering is step two, not step seven.</h2>
          </div>
          <p className="mono text-[11px] text-ink-subtle max-w-sm">
            Unauthorized content never enters the context window. It is never loaded into memory, never sent to the model, never in the logs.
          </p>
        </div>
        <Pipeline />
      </Section>

      {/* PERMISSIONS */}
      <Section id="permissions" label="003 &mdash; ACCESS CONTROL" className="bg-surface-1">
        <div className="mb-12">
          <div className="b-label mb-4">Security model</div>
          <h2 className="b-h2">
            Four tiers. <span className="accent">Zero</span> leaks.
          </h2>
          <p className="mt-4 text-ink-muted text-lg max-w-2xl">
            Select a role and watch the retrieval set change. The blocked rows aren&apos;t hidden from a result list &mdash; they were never retrieved.
          </p>
        </div>
        <PermissionSim />
      </Section>

      {/* FEATURES */}
      <Section id="features" label="004 &mdash; FEATURES">
        <div className="b-label mb-4">Key features</div>
        <h2 className="b-h2 mb-12">Built like infrastructure, not a chatbot.</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 border-t-2 border-l-2 border-border-strong">
          {FEATURES.map((f) => (
            <div key={f.k} className="border-r-2 border-b-2 border-border-strong p-8 hover:bg-surface-1 group">
              <div className="mono text-[11px] accent mb-6">{f.k}</div>
              <h3 className="font-bold text-xl leading-tight mb-3 group-hover:underline decoration-primary decoration-2 underline-offset-4">{f.t}</h3>
              <p className="text-ink-subtle text-sm leading-relaxed">{f.d}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* USE CASES */}
      <Section label="005 &mdash; USE CASES">
        <div className="b-label mb-4">Use cases</div>
        <h2 className="b-h2 mb-12">Real questions. Cited answers.</h2>
        <div>
          <div className="b-row grid-cols-12 b-label !py-3 border-b-2 !border-foreground">
            <div className="col-span-3">Team</div>
            <div className="col-span-6">Question</div>
            <div className="col-span-3 hidden md:block">Synthesized from</div>
          </div>
          {USECASES.map((u) => (
            <div key={u.who} className="b-row grid-cols-12 items-center">
              <div className="col-span-12 md:col-span-3 mono text-[11px] uppercase tracking-widest accent">{u.who}</div>
              <div className="col-span-12 md:col-span-6 text-xl md:text-2xl font-bold tracking-tight">&ldquo;{u.q}&rdquo;</div>
              <div className="col-span-12 md:col-span-3 mono text-[11px] text-ink-subtle">{u.src}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* EVAL */}
      <Section id="eval" label="006 &mdash; EVALUATION" className="bg-surface-1">
        <div className="grid lg:grid-cols-12 gap-12">
          <div className="lg:col-span-4">
            <div className="b-label mb-4">Evaluation framework</div>
            <h2 className="b-h2">Measured. Not vibes.</h2>
            <p className="mt-6 text-ink-muted">Retrieval quality is scored independently of generation. Security metrics are pass/fail.</p>
            <div className="mt-8 space-y-4">
              {[
                ["Retrieval", "Precision@5 \u00b7 Recall@k \u00b7 MRR"],
                ["Generation", "Faithfulness \u00b7 Relevance \u00b7 Citation accuracy"],
                ["Security", "Leakage rate \u00b7 Boundary accuracy"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-border pb-2">
                  <span className="font-bold uppercase text-sm">{k}</span>
                  <span className="mono text-[11px] text-ink-subtle">{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="lg:col-span-8 grid sm:grid-cols-2 gap-3">
            {METRICS.map((m) => (
              <div key={m.l} className="b-card min-h-[200px] flex flex-col justify-between">
                <div className="b-stat-num">{m.v}</div>
                <div>
                  <div className="font-bold uppercase tracking-wide">{m.l}</div>
                  <div className="mono text-[11px] text-ink-subtle mt-1">{m.s}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* API + TECH */}
      <Section id="api" label="007 &mdash; API / STACK">
        <div className="grid lg:grid-cols-2 gap-12">
          <div>
            <div className="b-label mb-4">API reference</div>
            <h2 className="b-h2 mb-8">One endpoint that matters.</h2>
            <div className="b-terminal !shadow-none">
              <div className="b-terminal-bar">
                <span>{ep.method} {ep.path}</span>
                {ep.auth && <span>Authorization: Bearer &lt;token&gt;</span>}
              </div>
              <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`// request\n${ep.request}\n\n// response\n${ep.response}`}</pre>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 mono text-[11px]">
              {API_ENDPOINTS.map((e, i) => (
                <div
                  key={e.path}
                  onClick={() => setActiveEndpoint(i)}
                  className={`border px-3 py-2 whitespace-pre cursor-pointer transition-colors ${
                    i === activeEndpoint
                      ? "border-primary text-foreground bg-surface-1"
                      : "border-border text-ink-muted hover:border-primary"
                  }`}
                >
                  {e.method} {e.path.replace("/api/", "/")}
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="b-label mb-4">Technology</div>
            <h2 className="b-h2 mb-8">Fast, filterable, boring in the right places.</h2>
            <div className="flex flex-wrap gap-2 mb-10">
              {TECH.map((t) => (
                <span key={t} className="b-tag">{t}</span>
              ))}
            </div>
            <div className="space-y-0 border-t-2 border-border-strong">
              {[
                ["Cohere Command", "Language model inference"],
                ["Cohere Embeddings", "Vector representations"],
                ["Cohere Rerank", "Cross-encoder relevance"],
                ["Pinecone", "Vector DB with metadata filtering"],
                ["PostgreSQL", "Users, roles, permissions"],
                ["FastAPI", "Async API layer"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between py-3 border-b-2 border-border-strong">
                  <span className="font-bold">{k}</span>
                  <span className="mono text-[11px] text-ink-subtle">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* CTA */}
      <section className="b-divider relative bg-primary text-primary-foreground px-6 md:px-12 py-24">
        <span className="b-corner top-3 left-6 !text-primary-foreground/50">008 &mdash; CTA</span>
        <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-end justify-between gap-10">
          <h2 className="b-headline !text-primary-foreground">
            Stop leaking.
            <br />
            Start answering.
          </h2>
          <div className="flex flex-wrap gap-4">
            <Link href="/register" className="b-btn !bg-background !border-background !text-foreground hover:!bg-foreground hover:!text-background hover:!border-foreground">
              Create Account
            </Link>
            <a href="#how" className="b-btn !bg-transparent !border-background !text-background hover:!bg-background hover:!text-foreground">
              Read the docs
            </a>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t-2 border-foreground px-6 md:px-12 py-16">
        <div className="max-w-7xl mx-auto grid md:grid-cols-12 gap-10">
          <div className="md:col-span-5">
            <div className="flex items-center gap-3 mb-4">
            <img src="/tab-icon.png" alt="Vault" className="w-8 h-8 rounded" />
              <span className="font-bold tracking-tight text-lg">VAULT</span>
            </div>
            <p className="text-ink-subtle text-sm max-w-sm">Permission-aware enterprise knowledge system. Permission filtering happens before retrieval, not after generation.</p>
            <div className="flex gap-3 mt-6">
              <a href="https://github.com/DanielDeshmukh" target="_blank" rel="noreferrer" className="b-social" aria-label="GitHub"><SiGithub size={16} /></a>
              <a href="https://x.com/DeshmukhDa71837" target="_blank" rel="noreferrer" className="b-social" aria-label="X (Twitter)"><SiX size={16} /></a>
              <a href="https://www.linkedin.com/in/daniel-deshmukh-7b08602b2" target="_blank" rel="noreferrer" className="b-social" aria-label="LinkedIn"><FaLinkedinIn size={16} /></a>
            </div>
          </div>
          <div className="b-footer-col md:col-span-2">
            <h4>Product</h4>
            <a href="#how">Pipeline</a>
            <a href="#permissions">Permissions</a>
            <a href="#features">Features</a>
            <a href="#eval">Evaluation</a>
          </div>
          <div className="b-footer-col md:col-span-2">
            <h4>Developers</h4>
            <a href="#api">API reference</a>
            <Link href="/connectors">Connectors</Link>
            <Link href="/golden-set">Golden set</Link>
            <Link href="/changelog">Changelog</Link>
          </div>
          <div className="b-footer-col md:col-span-3">
            <h4>Compliance</h4>
            <Link href="/compliance/soc2">SOC 2</Link>
            <Link href="/compliance/hipaa">HIPAA</Link>
            <Link href="/compliance/audit">Audit logging</Link>
            <a href="https://github.com/DanielDeshmukh/vault/blob/master/LICENSE" target="_blank" rel="noreferrer">MIT License</a>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-16 pt-6 border-t border-border flex flex-col md:flex-row justify-between gap-2 mono text-[10px] tracking-widest uppercase text-ink-tertiary">
          <span>&copy; 2026 Vault. MIT License.</span>
          <span>unauthorized_leakage_rate = 0.0</span>
        </div>
      </footer>
    </div>
  );
}
