import { Terminal, Pipeline, PermissionSim } from "./components/Interactive";

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
    d: "Vector similarity catches meaning (“billing complaint” ≈ “invoice discrepancy”). BM25 catches exact strings: ticket IDs, error codes, proper nouns.",
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
  { who: "Customer Support", q: "What's the SLA for this customer's enterprise tier?", src: "contract · support history · SLA policy" },
  { who: "Account Management", q: "What did we promise in the last renewal call?", src: "call transcript · follow-up email · amendment" },
  { who: "Engineering Handoff", q: "What was the root cause of the outage affecting Acme Corp?", src: "incident report · slack thread · post-mortem" },
  { who: "Compliance Audit", q: "Show me all references to data retention policies.", src: "policy docs · support scripts · training material" },
];

const METRICS = [
  { v: "0.0", l: "Unauthorized leakage rate", s: "Non-negotiable. Exactly zero." },
  { v: "50", l: "Golden-set questions", s: "Lookups, synthesis, conflicts, stale data, refusals, adversarial." },
  { v: "7", l: "Source connectors", s: "One unified permission model." },
  { v: "4", l: "Access tiers", s: "Public → Internal → Confidential → Restricted." },
];

const TECH = ["Groq · Llama 3 70B", "Groq Embeddings", "Cohere Rerank", "Qdrant", "PostgreSQL", "FastAPI", "BM25", "Python 3.12", "MIT License"];

const MARQUEE = ["PERMISSION BEFORE RETRIEVAL", "CITED OR REFUSED", "LEAKAGE = 0.0", "HYBRID SEARCH", "FULL AUDIT TRAIL", "PRE-RETRIEVAL FILTERING"];

function Section({ id, label, children, className = "" }: { id?: string; label: string; children: React.ReactNode; className?: string }) {
  return (
    <section id={id} className={`b-divider relative px-6 md:px-12 py-20 md:py-28 ${className}`}>
      <span className="b-corner top-3 left-6">{label}</span>
      <span className="b-corner top-3 right-6">§</span>
      <div className="max-w-7xl mx-auto">{children}</div>
    </section>
  );
}

export default function App() {
  return (
    <div className="brutalist min-h-screen">
      {/* NAV */}
      <header className="sticky top-0 z-50 bg-black border-b-2 border-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <a href="#" className="flex items-center gap-3">
            <span className="w-8 h-8 bg-white flex items-center justify-center text-black font-bold text-lg">V</span>
            <span className="font-bold tracking-tight text-lg">VAULT</span>
            <span className="b-label hidden md:inline ml-2">/ v1.0</span>
          </a>
          <nav className="hidden md:flex items-center gap-8 mono text-[11px] uppercase tracking-widest text-[#888]">
            <a href="#how" className="hover:text-white">How</a>
            <a href="#permissions" className="hover:text-white">Permissions</a>
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#eval" className="hover:text-white">Eval</a>
            <a href="#api" className="hover:text-white">API</a>
          </nav>
          <a href="#api" className="b-btn !py-2 !px-4 text-[11px]">Get Started</a>
        </div>
      </header>

      {/* HERO */}
      <section className="b-grid relative px-6 md:px-12 pt-20 pb-24 noise">
        <span className="b-corner top-4 left-6">000 — HERO</span>
        <span className="b-corner top-4 right-6">52.5200° N, 13.4050° E</span>
        <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7">
            <div className="flex items-center gap-3 mb-8">
              <span className="w-2 h-2 bg-accent blink" />
              <span className="b-label !text-white">Permission-aware enterprise knowledge system</span>
            </div>
            <h1 className="b-headline">
              Ask anything.
              <br />
              See only what
              <br />
              you're <span className="accent">allowed</span> to.
            </h1>
            <p className="mt-8 max-w-xl text-lg md:text-xl text-[#d0d6e0] leading-relaxed">
              Vault answers natural-language questions across Zendesk, Jira, Slack, Confluence, call transcripts and policy docs — with citations — while enforcing permission boundaries{" "}
              <span className="text-white font-bold underline decoration-[#BAFF29] decoration-2 underline-offset-4">before</span> anything reaches the language model.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <a href="#api" className="b-btn b-btn-accent">Deploy Vault →</a>
              <a href="#how" className="b-btn b-btn-outline">Read the architecture</a>
            </div>
            <div className="mt-12 grid grid-cols-3 max-w-md border-2 border-[#333] divide-x-2 divide-[#333]">
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
      <div className="b-marquee py-3 bg-white text-black">
        <div className="b-marquee-track mono text-[12px] font-bold tracking-[0.2em]">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i} className="px-8">
              {m} <span className="ml-8">■</span>
            </span>
          ))}
        </div>
      </div>

      {/* PROBLEM */}
      <Section label="001 — THE PROBLEM">
        <div className="grid lg:grid-cols-12 gap-12">
          <div className="lg:col-span-5">
            <div className="b-label mb-4">The problem</div>
            <h2 className="b-h2">
              The answer exists. It's in <span className="accent">three tools</span>, and one of them you shouldn't open.
            </h2>
            <p className="mt-6 text-[#d0d6e0] text-lg leading-relaxed">
              “What did we promise this customer?” lives in a ticket from last quarter, a Slack thread, and a signed amendment. Next to it sits an HR note, an executive escalation, and another account's pricing.
            </p>
            <p className="mt-4 text-white font-bold text-lg">Vault solves both problems simultaneously.</p>
          </div>
          <div className="lg:col-span-7 grid sm:grid-cols-2 gap-3">
            {SOURCES.map((s, i) => (
              <div key={s.n} className="b-card">
                <span className="b-corner top-2 right-3">0{i + 1}</span>
                <div className="font-bold text-xl uppercase tracking-tight">{s.n}</div>
                <div className="mono text-[11px] text-[#888] mt-2">{s.d}</div>
              </div>
            ))}
            <div className="b-card !border-[#BAFF29] bg-accent !text-black flex flex-col justify-between">
              <div className="mono text-[10px] tracking-widest uppercase">Unified into</div>
              <div className="font-bold text-2xl leading-none mt-6">ONE PERMISSION MODEL</div>
            </div>
          </div>
        </div>
      </Section>

      {/* HOW IT WORKS */}
      <Section id="how" label="002 — PIPELINE">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div>
            <div className="b-label mb-4">How it works</div>
            <h2 className="b-h2">Six steps. Filtering is step two, not step seven.</h2>
          </div>
          <p className="mono text-[11px] text-[#888] max-w-sm">
            Unauthorized content never enters the context window. It is never loaded into memory, never sent to the model, never in the logs.
          </p>
        </div>
        <Pipeline />
      </Section>

      {/* PERMISSIONS */}
      <Section id="permissions" label="003 — ACCESS CONTROL" className="bg-[#050505]">
        <div className="mb-12">
          <div className="b-label mb-4">Security model</div>
          <h2 className="b-h2">
            Four tiers. <span className="accent">Zero</span> leaks.
          </h2>
          <p className="mt-4 text-[#d0d6e0] text-lg max-w-2xl">
            Select a role and watch the retrieval set change. The blocked rows aren't hidden from a result list — they were never retrieved.
          </p>
        </div>
        <PermissionSim />
      </Section>

      {/* FEATURES */}
      <Section id="features" label="004 — FEATURES">
        <div className="b-label mb-4">Key features</div>
        <h2 className="b-h2 mb-12">Built like infrastructure, not a chatbot.</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 border-t-2 border-l-2 border-[#333]">
          {FEATURES.map((f) => (
            <div key={f.k} className="border-r-2 border-b-2 border-[#333] p-8 hover:bg-[#0a0a0a] group">
              <div className="mono text-[11px] accent mb-6">{f.k}</div>
              <h3 className="font-bold text-xl leading-tight mb-3 group-hover:underline decoration-[#BAFF29] decoration-2 underline-offset-4">{f.t}</h3>
              <p className="text-[#8a8f98] text-sm leading-relaxed">{f.d}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* USE CASES */}
      <Section label="005 — USE CASES">
        <div className="b-label mb-4">Use cases</div>
        <h2 className="b-h2 mb-12">Real questions. Cited answers.</h2>
        <div>
          <div className="b-row grid-cols-12 b-label !py-3 border-b-2 !border-white">
            <div className="col-span-3">Team</div>
            <div className="col-span-6">Question</div>
            <div className="col-span-3 hidden md:block">Synthesized from</div>
          </div>
          {USECASES.map((u) => (
            <div key={u.who} className="b-row grid-cols-12 items-center">
              <div className="col-span-12 md:col-span-3 mono text-[11px] uppercase tracking-widest accent">{u.who}</div>
              <div className="col-span-12 md:col-span-6 text-xl md:text-2xl font-bold tracking-tight">“{u.q}”</div>
              <div className="col-span-12 md:col-span-3 mono text-[11px] text-[#888]">{u.src}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* EVAL */}
      <Section id="eval" label="006 — EVALUATION" className="bg-[#050505]">
        <div className="grid lg:grid-cols-12 gap-12">
          <div className="lg:col-span-4">
            <div className="b-label mb-4">Evaluation framework</div>
            <h2 className="b-h2">Measured. Not vibes.</h2>
            <p className="mt-6 text-[#d0d6e0]">Retrieval quality is scored independently of generation. Security metrics are pass/fail.</p>
            <div className="mt-8 space-y-4">
              {[
                ["Retrieval", "Precision@5 · Recall@k · MRR"],
                ["Generation", "Faithfulness · Relevance · Citation accuracy"],
                ["Security", "Leakage rate · Boundary accuracy"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-[#333] pb-2">
                  <span className="font-bold uppercase text-sm">{k}</span>
                  <span className="mono text-[11px] text-[#888]">{v}</span>
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
                  <div className="mono text-[11px] text-[#888] mt-1">{m.s}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* API + TECH */}
      <Section id="api" label="007 — API / STACK">
        <div className="grid lg:grid-cols-2 gap-12">
          <div>
            <div className="b-label mb-4">API reference</div>
            <h2 className="b-h2 mb-8">One endpoint that matters.</h2>
            <div className="b-terminal !shadow-none">
              <div className="b-terminal-bar">
                <span>POST /api/query</span>
                <span>Authorization: Bearer ‹token›</span>
              </div>
              <pre className="p-4 text-[12px] leading-relaxed text-[#d0d6e0] overflow-x-auto">{`// request
{ "question": "string", "context": "optional" }

// response
{
  "answer":    "string",
  "citations": [ { "source": "...", "chunk_id": "...", "score": 0.94 } ],
  "trace_id":  "string"
}`}</pre>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 mono text-[11px]">
              {[
                "POST /api/auth/register",
                "POST /api/auth/login",
                "POST /api/documents/ingest",
                "GET  /api/documents/{id}",
                "DELETE /api/documents/{id}",
                "GET  /health",
              ].map((e) => (
                <div key={e} className="border border-[#333] px-3 py-2 text-[#ccc] hover:border-[#BAFF29] whitespace-pre">
                  {e}
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
            <div className="space-y-0 border-t-2 border-[#333]">
              {[
                ["Groq · Llama 3 70B", "Language model inference"],
                ["Groq Embeddings", "Vector representations"],
                ["Cohere Rerank", "Cross-encoder relevance"],
                ["Qdrant", "Vector DB with metadata filtering"],
                ["PostgreSQL", "Users, roles, permissions"],
                ["FastAPI", "Async API layer"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between py-3 border-b-2 border-[#333]">
                  <span className="font-bold">{k}</span>
                  <span className="mono text-[11px] text-[#888]">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* CTA */}
      <section className="b-divider relative bg-accent text-black px-6 md:px-12 py-24">
        <span className="b-corner top-3 left-6 !text-black/50">008 — CTA</span>
        <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-end justify-between gap-10">
          <h2 className="b-headline !text-black">
            Stop leaking.
            <br />
            Start answering.
          </h2>
          <div className="flex flex-wrap gap-4">
            <a href="#" className="b-btn !bg-black !border-black !text-white hover:!bg-white hover:!text-black hover:!border-white">
              git clone vault
            </a>
            <a href="#" className="b-btn !bg-transparent !border-black !text-black hover:!bg-black hover:!text-white">
              Read the docs
            </a>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t-2 border-white px-6 md:px-12 py-16">
        <div className="max-w-7xl mx-auto grid md:grid-cols-12 gap-10">
          <div className="md:col-span-5">
            <div className="flex items-center gap-3 mb-4">
              <span className="w-8 h-8 bg-white flex items-center justify-center text-black font-bold text-lg">V</span>
              <span className="font-bold tracking-tight text-lg">VAULT</span>
            </div>
            <p className="text-[#888] text-sm max-w-sm">Permission-aware enterprise knowledge system. Permission filtering happens before retrieval, not after generation.</p>
            <div className="flex gap-2 mt-6">
              {["GH", "X", "IN"].map((s) => (
                <a key={s} href="#" className="b-social mono text-[10px]">{s}</a>
              ))}
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
            <a href="#">Connectors</a>
            <a href="#">Golden set</a>
            <a href="#">Changelog</a>
          </div>
          <div className="b-footer-col md:col-span-3">
            <h4>Compliance</h4>
            <a href="#">SOC 2</a>
            <a href="#">HIPAA</a>
            <a href="#">Audit logging</a>
            <a href="#">MIT License</a>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-16 pt-6 border-t border-[#333] flex flex-col md:flex-row justify-between gap-2 mono text-[10px] tracking-widest uppercase text-[#555]">
          <span>© 2026 Vault. MIT License.</span>
          <span>unauthorized_leakage_rate = 0.0</span>
        </div>
      </footer>
    </div>
  );
}
