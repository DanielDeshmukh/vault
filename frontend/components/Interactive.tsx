"use client";

import { useEffect, useState } from "react";

const QUERY = "What did we promise Acme Corp in the last renewal call?";

const LINES = [
  { t: "auth", s: "user=j.rivera role=account_manager scope=[acme-corp, globex]" },
  { t: "filter", s: "pinecone.filter { access<=CONFIDENTIAL, account\u2208scope } \u2014 applied PRE-retrieval" },
  { t: "search", s: "hybrid: vector(0.62) + bm25(0.38) \u2192 48 candidates" },
  { t: "rerank", s: "cohere.rerank \u2192 top 5 (max score 0.94)" },
  { t: "blocked", s: "3 chunks excluded: [RESTRICTED] exec_escalation.md, hr_notes.doc, pricing_globex.csv" },
  { t: "generate", s: "command-a-03-2025 @ cohere \u2014 412ms" },
];

const ANSWER =
  "On the Mar 14 renewal call, we committed to (1) a 99.95% uptime SLA upgrade at no cost [1], (2) dedicated Slack Connect channel by Q2 [2], and (3) a 12-month price lock confirmed in Amendment #3 [3].";

const CITES = [
  "[1] gong://calls/acme-renewal-0314 \u00b7 00:14:22",
  "[2] slack://#acme-cs \u00b7 thread 2024-03-15",
  "[3] confluence://contracts/acme/amendment-3 \u00b7 \u00a72.1",
];

export function Terminal() {
  const [typed, setTyped] = useState("");
  const [step, setStep] = useState(0);
  const [answer, setAnswer] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i++;
      setTyped(QUERY.slice(0, i));
      if (i >= QUERY.length) clearInterval(id);
    }, 35);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (typed.length < QUERY.length) return;
    if (step < LINES.length) {
      const id = setTimeout(() => setStep((s) => s + 1), 380);
      return () => clearTimeout(id);
    }
    let i = 0;
    const id = setInterval(() => {
      i += 3;
      setAnswer(ANSWER.slice(0, i));
      if (i >= ANSWER.length) {
        clearInterval(id);
        setDone(true);
      }
    }, 12);
    return () => clearInterval(id);
  }, [typed, step]);

  const color = (t: string) =>
    t === "blocked" ? "#ef4444" : t === "filter" ? "#4a55a0" : "#8a8f98";

  return (
    <div className="b-terminal relative">
      <div className="b-terminal-bar">
        <span>vault &middot; query trace</span>
        <span className="accent">trace_id: 7f3a-c21e</span>
      </div>
      <div className="p-4 space-y-2 min-h-[340px]">
        <div className="text-foreground">
          <span className="accent">&rsaquo; </span>
          {typed}
          {typed.length < QUERY.length && <span className="blink">&#9612;</span>}
        </div>
        {LINES.slice(0, step).map((l) => (
          <div key={l.t} className="fade-up flex gap-3">
            <span style={{ color: color(l.t), minWidth: 70 }} className="uppercase">
              [{l.t}]
            </span>
            <span style={{ color: l.t === "blocked" ? "#62666d" : "#d0d6e0" }}>{l.s}</span>
          </div>
        ))}
        {answer && (
          <div className="fade-up border-t-2 border-border pt-3 mt-3">
            <div className="b-label mb-2" style={{ color: "#4a55a0" }}>
              answer
            </div>
            <p className="text-[13px] leading-relaxed text-foreground">{answer}</p>
          </div>
        )}
        {done && (
          <div className="fade-up space-y-1 pt-2">
            {CITES.map((c) => (
              <div key={c} className="text-ink-subtle">
                {c}
              </div>
            ))}
            <div className="pt-2 text-[10px] tracking-widest uppercase text-ink-tertiary">
              leakage: <span className="accent">0.0</span> &middot; latency: 1.21s &middot; logged &#10003;
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STEPS = [
  { n: "01", name: "Authenticate", d: "Resolve identity, role and account scope from PostgreSQL." },
  { n: "02", name: "Filter", d: "Permission predicate pushed down to the Pinecone query. Before anything is read." },
  { n: "03", name: "Search", d: "Hybrid retrieval: vector similarity + BM25 keyword match." },
  { n: "04", name: "Rerank", d: "Cohere cross-encoder orders candidates by true relevance." },
  { n: "05", name: "Generate", d: "Cohere Command writes a cited answer from authorized chunks only." },
  { n: "06", name: "Log", d: "Full trace persisted: user, scope, chunks, scores, answer, latency." },
];

export function Pipeline() {
  const [active, setActive] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setActive((a) => (a + 1) % STEPS.length), 2200);
    return () => clearInterval(id);
  }, []);
  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {STEPS.map((s, i) => (
          <div
            key={s.n}
            className={`b-step ${i === active ? "active" : ""}`}
            onMouseEnter={() => setActive(i)}
          >
            <div className="b-step-num">{s.n}</div>
            <div className="font-bold text-sm uppercase tracking-wide">{s.name}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 border-2 border-border p-6 min-h-[110px] flex flex-col md:flex-row md:items-center gap-4">
        <div className="mono accent text-4xl font-bold">{STEPS[active].n}</div>
        <div>
          <div className="b-label mb-1">{STEPS[active].name}</div>
          <p className="text-ink-muted text-base md:text-lg">{STEPS[active].d}</p>
        </div>
        {active === 1 && (
          <div className="md:ml-auto b-tag" style={{ borderColor: "#4a55a0", color: "#4a55a0" }}>
            THE CRITICAL STEP
          </div>
        )}
      </div>
    </div>
  );
}

const ROLES = [
  { l: 0, name: "Public", who: "All authenticated users", ex: "Policies, onboarding docs" },
  { l: 1, name: "Internal", who: "Department-scoped", ex: "Team procedures" },
  { l: 2, name: "Confidential", who: "Account-scoped", ex: "Contracts, support history" },
  { l: 3, name: "Restricted", who: "Named-user only", ex: "Executive notes, legal" },
];

const CHUNKS = [
  { name: "onboarding_handbook.pdf", src: "notion", lvl: 0 },
  { name: "data_retention_policy.md", src: "confluence", lvl: 0 },
  { name: "cs_escalation_runbook.md", src: "confluence", lvl: 1 },
  { name: "#eng-incidents thread", src: "slack", lvl: 1 },
  { name: "acme_contract_amendment_3.pdf", src: "gdrive", lvl: 2 },
  { name: "ticket #48213 agent notes", src: "zendesk", lvl: 2 },
  { name: "acme_renewal_call_0314", src: "gong", lvl: 2 },
  { name: "exec_escalation_acme.md", src: "notion", lvl: 3 },
  { name: "legal_hold_2024Q1.doc", src: "gdrive", lvl: 3 },
];

export function PermissionSim() {
  const [role, setRole] = useState(2);
  const allowed = CHUNKS.filter((c) => c.lvl <= role).length;
  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <div>
        <div className="b-label mb-4">01 &mdash; select a caller</div>
        <div className="grid gap-3">
          {ROLES.map((r) => (
            <div
              key={r.l}
              data-level={r.l}
              className={`b-role ${role === r.l ? "selected" : ""}`}
              onClick={() => setRole(r.l)}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold uppercase tracking-wide">
                  <span className="mono text-ink-tertiary mr-3">L{r.l}</span>
                  {r.name}
                </span>
                <span className="mono text-[11px] text-ink-subtle">{r.who}</span>
              </div>
              <div className="text-sm text-ink-tertiary mt-1">{r.ex}</div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="b-label mb-4 flex justify-between">
          <span>02 &mdash; what the model context receives</span>
          <span>
            <span className="accent">{allowed}</span>/{CHUNKS.length} chunks
          </span>
        </div>
        <div className="border-2 border-border p-4 space-y-2">
          <div className="mono text-[10px] text-ink-tertiary pb-2 border-b border-border">
            pinecone.search(filter: access_level &le; {role}, account &isin; scope)
          </div>
          {CHUNKS.map((c) => {
            const ok = c.lvl <= role;
            return (
              <div key={c.name} className={`chunk ${ok ? "allowed" : "blocked"}`}>
                <span>
                  {ok ? "\u2713" : "\u2715"} {c.name}
                </span>
                <span>
                  {c.src} &middot; L{c.lvl}
                </span>
              </div>
            );
          })}
          <div className="pt-3 mono text-[11px] text-ink-subtle">
            {CHUNKS.length - allowed} chunk(s) never loaded. Never embedded in a prompt. Never logged.
          </div>
        </div>
      </div>
    </div>
  );
}
