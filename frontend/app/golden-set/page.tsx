"use client";

import { SubPageLayout } from "@/components/SubPageLayout";

const QUESTIONS = [
  {
    q: "Can I take time off after my kid is born?",
    keywords: ["parental", "maternity", "paternity", "birth", "adoption"],
    category: "Leave Policy",
  },
  {
    q: "What happens if I get hurt at work?",
    keywords: ["report", "incident", "accident", "injury", "procedure"],
    category: "Workplace Safety",
  },
  {
    q: "Am I allowed to work from home?",
    keywords: ["telework", "telecommute", "eligible", "requirements", "agreement"],
    category: "Remote Work",
  },
  {
    q: "Can I bring my gun to the office?",
    keywords: ["weapons", "firearms", "prohibited", "campus", "possession"],
    category: "Workplace Safety",
  },
  {
    q: "How do I quit my job here?",
    keywords: ["resignation", "voluntary", "notice", "two weeks", "exit"],
    category: "Offboarding",
  },
];

const USERS = [
  { email: "admin@vaultdemo.com", role: "Admin", level: 99, access: "All documents" },
  { email: "hr@vaultdemo.com", role: "Confidential", level: 2, access: "Public + Internal + Confidential" },
  { email: "engineer@vaultdemo.com", role: "Internal", level: 1, access: "Public + Internal" },
  { email: "public.role.test@vault.local", role: "Public", level: 0, access: "Public only" },
];

export default function GoldenSetPage() {
  return (
    <SubPageLayout>
        <div className="b-label mb-4">Golden Set</div>
        <h1 className="b-h2 mb-6">50 questions. Measured, not vibes.</h1>
        <p className="text-ink-muted text-lg max-w-2xl mb-16">
          Natural, ambiguous questions that test retrieval quality across access levels. Each question is scored on keyword recall, citation count, and relevance.
        </p>

        <div className="mb-16">
          <h2 className="b-h2 mb-8">Evaluation Questions</h2>
          <div className="border-t-2 border-foreground">
            <div className="b-row grid-cols-12 b-label !py-3 border-b-2 !border-foreground">
              <div className="col-span-2">Category</div>
              <div className="col-span-6">Question</div>
              <div className="col-span-4">Expected Keywords</div>
            </div>
            {QUESTIONS.map((item, i) => (
              <div key={i} className="b-row grid-cols-12 items-center">
                <div className="col-span-12 md:col-span-2 mono text-[11px] uppercase tracking-widest accent">{item.category}</div>
                <div className="col-span-12 md:col-span-6 text-lg font-bold tracking-tight">&ldquo;{item.q}&rdquo;</div>
                <div className="col-span-12 md:col-span-4 mono text-[11px] text-ink-subtle">{item.keywords.join(", ")}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-16">
          <h2 className="b-h2 mb-8">Test Users</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {USERS.map((u) => (
              <div key={u.email} className="b-card">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold">{u.role}</span>
                  <span className="mono text-[11px] accent">Level {u.level}</span>
                </div>
                <div className="mono text-[11px] text-ink-subtle mb-2">{u.email}</div>
                <div className="text-sm text-ink-muted">Access: {u.access}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t-2 border-border pt-12">
          <h2 className="b-h2 mb-6">Running the evaluation</h2>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>terminal</span>
            </div>
            <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`cd server
export VAULT_DEMO_PASSWORD="your_password"
export VAULT_DANIEL_PASSWORD="your_password"
python -m scripts.evaluate_ambiguous`}</pre>
          </div>
        </div>
      </main>
    </SubPageLayout>
  );
}
