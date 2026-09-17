"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="font-bold font-display text-xl tracking-tight">Vault</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">Sign In</Button>
            </Link>
            <Link href="/register">
              <Button size="sm">Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border text-xs text-ink-muted mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-success" />
          Permission-aware RAG system
        </div>
        <h1 className="text-5xl md:text-6xl font-bold font-display tracking-tight mb-6 text-foreground leading-tight">
          Enterprise Knowledge,<br />Secured by Role
        </h1>
        <p className="text-lg text-ink-muted max-w-2xl mx-auto mb-10 leading-relaxed">
          Ask questions across your organization's documents. Vault filters results by
          your role before the AI even sees them — unauthorized content is never loaded.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/register">
            <Button size="lg" className="px-8">Create Account</Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg" className="px-8">Sign In</Button>
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border bg-surface-1">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-2xl font-bold font-display text-center mb-12">How It Works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <Step number="01" title="Register" description="Sign up with your department and designation. An admin reviews and assigns your role." />
            <Step number="02" title="Ask" description="Type a question in natural language. Ctrl+K to focus anywhere." />
            <Step number="03" title="Get Cited Answers" description="Receive answers with source citations — from documents your role is authorized to access." />
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-2xl font-bold font-display text-center mb-12">Built for Enterprise</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <Feature
              title="Pre-Retrieval Filtering"
              description="Permission checks happen at the vector database level. Unauthorized chunks are never sent to the language model."
            />
            <Feature
              title="Hybrid Search"
              description="Combines vector similarity with keyword matching for precise retrieval across large document collections."
            />
            <Feature
              title="Multi-Source Ingestion"
              description="Connect to Zendesk, Jira, Slack, Confluence, PDFs, and more. One pipeline handles all formats."
            />
            <Feature
              title="Full Audit Trail"
              description="Every query, every retrieval, every answer is logged with trace IDs for compliance and debugging."
            />
          </div>
        </div>
      </section>

      {/* RBAC */}
      <section className="border-t border-border bg-surface-1">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-2xl font-bold font-display text-center mb-4">Role-Based Access Control</h2>
          <p className="text-ink-muted text-center max-w-xl mx-auto mb-12">
            Four permission levels. Admin assigns roles. Users see only what their role allows.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            <RoleCard name="Public" level="0" description="General documents" />
            <RoleCard name="Internal" level="1" description="Company-wide" />
            <RoleCard name="Confidential" level="2" description="Sensitive data" />
            <RoleCard name="Restricted" level="3" description="Limited access" />
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-2xl font-bold font-display text-center mb-12">Stack</h2>
          <div className="flex flex-wrap justify-center gap-3 max-w-3xl mx-auto">
            {["FastAPI", "Next.js", "PostgreSQL", "Pinecone", "Cohere", "SQLAlchemy", "JWT Auth", "Tailwind CSS", "Vercel"].map((tech) => (
              <span key={tech} className="px-4 py-2 rounded-lg bg-surface-2 border border-border text-sm text-ink-muted">
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-8 flex items-center justify-between text-sm text-ink-tertiary">
          <span>Vault</span>
          <span>Enterprise Knowledge Retrieval</span>
        </div>
      </footer>
    </div>
  );
}

function Step({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div className="text-center">
      <div className="w-10 h-10 rounded-lg bg-surface-2 border border-border flex items-center justify-center text-sm font-mono text-primary mx-auto mb-4">
        {number}
      </div>
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
    </div>
  );
}

function Feature({ title, description }: { title: string; description: string }) {
  return (
    <div className="p-6 rounded-lg border border-border bg-surface-1">
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
    </div>
  );
}

function RoleCard({ name, level, description }: { name: string; level: string; description: string }) {
  return (
    <div className="p-4 rounded-lg border border-border bg-surface-1 text-center">
      <div className="text-xs font-mono text-ink-tertiary mb-1">Level {level}</div>
      <div className="font-semibold mb-1">{name}</div>
      <div className="text-xs text-ink-muted">{description}</div>
    </div>
  );
}
