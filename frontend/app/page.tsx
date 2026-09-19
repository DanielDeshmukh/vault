"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Nav */}
      <header className="border-b border-border/50 sticky top-0 z-50 bg-background/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <span className="font-bold font-display text-lg tracking-tight">Vault</span>
            <span className="hidden sm:inline text-[11px] text-ink-tertiary border border-border rounded px-1.5 py-0.5 font-mono">v0.1</span>
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

      <main className="flex-1">
        {/* Hero */}
        <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 md:pt-28 md:pb-24">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border text-xs text-ink-muted mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              Permission-aware RAG system
            </div>
            <h1 className="text-4xl md:text-[3.5rem] font-bold font-display tracking-tight mb-6 text-foreground leading-[1.1]">
              Enterprise Knowledge,<br />
              <span className="text-primary">Secured by Role</span>
            </h1>
            <p className="text-lg text-ink-muted max-w-xl mb-10 leading-relaxed">
              Ask questions across your organization&apos;s documents. Vault filters results by
              your role before the AI even sees them — unauthorized content is never loaded.
            </p>
            <div className="flex items-center gap-4">
              <Link href="/register">
                <Button size="lg" className="px-7">Create Account</Button>
              </Link>
              <Link href="/login">
                <Button variant="secondary" size="lg" className="px-7">Sign In</Button>
              </Link>
            </div>

            <div className="mt-14 flex items-center gap-8 md:gap-12">
              <div>
                <div className="text-2xl font-bold font-display">4</div>
                <div className="text-xs text-ink-tertiary mt-0.5">Access levels</div>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <div className="text-2xl font-bold font-display">17</div>
                <div className="text-xs text-ink-tertiary mt-0.5">Documents indexed</div>
              </div>
              <div className="w-px h-8 bg-border" />
              <div>
                <div className="text-2xl font-bold font-display">3.5k</div>
                <div className="text-xs text-ink-tertiary mt-0.5">Chunks searchable</div>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="border-t border-border bg-surface-1">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="text-xl font-bold font-display text-center mb-3">How It Works</h2>
            <p className="text-sm text-ink-muted text-center max-w-lg mx-auto mb-12">
              Permission checks happen at the vector database level. Restricted content never reaches the language model.
            </p>
            <div className="grid md:grid-cols-5 gap-3 items-center max-w-4xl mx-auto">
              <StepCard number="1" title="Ask" description="Natural language question" />
              <Arrow />
              <StepCard number="2" title="Filter" description="RBAC filter applied" accent />
              <Arrow />
              <StepCard number="3" title="Answer" description="Cited response generated" />
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="border-t border-border">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="text-xl font-bold font-display text-center mb-12">Built for Enterprise</h2>
            <div className="grid md:grid-cols-2 gap-4 max-w-4xl mx-auto">
              <Feature title="Pre-Retrieval Filtering" description="Permission checks happen at the vector database level. Unauthorized chunks are never sent to the language model." />
              <Feature title="Hybrid Search" description="Combines vector similarity with keyword matching and Cohere reranking for precise retrieval across large document collections." />
              <Feature title="Streaming Citations" description="Real-time streaming responses with inline document citations. Every claim traced back to its source." />
              <Feature title="Full Audit Trail" description="Every query, retrieval, and answer logged with trace IDs for compliance and debugging." />
            </div>
          </div>
        </section>

        {/* RBAC */}
        <section className="border-t border-border bg-surface-1">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="text-xl font-bold font-display text-center mb-3">Role-Based Access Control</h2>
            <p className="text-sm text-ink-muted text-center max-w-md mx-auto mb-12">
              Four permission levels. Admin assigns roles. Users see only what their role allows.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl mx-auto">
              <RoleCard name="Public" level="0" description="General documents" dotColor="bg-blue-400" />
              <RoleCard name="Internal" level="1" description="Company-wide" dotColor="bg-emerald-400" />
              <RoleCard name="Confidential" level="2" description="Sensitive data" dotColor="bg-amber-400" />
              <RoleCard name="Restricted" level="3" description="Limited access" dotColor="bg-rose-400" />
            </div>
          </div>
        </section>

        {/* Stack */}
        <section className="border-t border-border">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
            <h2 className="text-xl font-bold font-display text-center mb-10">Stack</h2>
            <div className="flex flex-wrap justify-center gap-2.5 max-w-3xl mx-auto">
              {["FastAPI", "Next.js", "PostgreSQL", "Pinecone", "Cohere", "SQLAlchemy", "JWT Auth", "Tailwind CSS", "Vercel"].map((tech) => (
                <span key={tech} className="px-3 py-1.5 rounded-md bg-surface-2 border border-border text-sm text-ink-muted hover:border-primary/30 transition-colors">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-border">
          <div className="max-w-6xl mx-auto px-6 py-16 md:py-20 text-center">
            <h2 className="text-2xl font-bold font-display mb-4">Try Vault</h2>
            <p className="text-ink-muted text-sm max-w-md mx-auto mb-8">
              Create an account and explore how permission-aware retrieval works across different access levels.
            </p>
            <div className="flex items-center justify-center gap-3">
              <Link href="/register">
                <Button size="lg" className="px-7">Get Started</Button>
              </Link>
              <Link href="/login">
                <Button variant="secondary" size="lg" className="px-7">Sign In</Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-surface-1">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-8">
            {/* Brand */}
            <div>
              <p className="text-sm font-medium text-foreground mb-1">Daniel Deshmukh</p>
              <p className="text-xs text-ink-tertiary mb-5">Full-Stack Developer</p>
              <div className="flex items-center gap-3">
                <SocialIcon href="https://x.com/DeshmukhDa71837" label="X">
                  <path d="M389.2 48h70.6L305.6 224.2 487 464H345L233.7 318.6 106.5 464H35.8L200.7 275.5 26.8 48H172.4L272.9 180.9 389.2 48zM364.4 421.8h39.1L151.1 88h-42L364.4 421.8z" />
                </SocialIcon>
                <SocialIcon href="https://github.com/DanielDeshmukh" label="GitHub">
                  <path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8z" />
                </SocialIcon>
                <SocialIcon href="https://www.linkedin.com/in/daniel-deshmukh-7b08602b2" label="LinkedIn">
                  <path d="M100.28 448H7.4V148.9h92.88zM53.79 108.1C24.09 108.1 0 83.5 0 53.8a53.79 53.79 0 0 1 107.58 0c0 29.7-24.1 54.3-53.79 54.3zM447.9 448h-92.68V302.4c0-34.7-.7-79.2-48.29-79.2-48.29 0-55.69 37.7-55.69 76.7V448h-92.78V148.9h89.08v40.8h1.3c12.4-23.5 42.69-48.3 87.88-48.3 94 0 111.28 61.9 111.28 142.3V448z" />
                </SocialIcon>
              </div>
            </div>

            {/* Navigation */}
            <div>
              <p className="text-[11px] font-semibold text-ink-tertiary uppercase tracking-widest mb-4">Navigation</p>
              <ul className="space-y-2.5 text-sm text-ink-muted">
                <li><Link href="/#about" className="hover:text-foreground transition-colors">About</Link></li>
                <li><Link href="/#projects" className="hover:text-foreground transition-colors">Projects</Link></li>
                <li><Link href="/#clients" className="hover:text-foreground transition-colors">Clients</Link></li>
                <li><a href="https://danieldeshmukh-portfolio.vercel.app/enquiry" target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">Contact</a></li>
              </ul>
            </div>

            {/* Contact */}
            <div>
              <p className="text-[11px] font-semibold text-ink-tertiary uppercase tracking-widest mb-4">Contact</p>
              <a href="mailto:deshmukhdaniel2005@gmail.com" className="flex items-center gap-2 text-sm text-ink-muted hover:text-foreground transition-colors break-all">
                <svg stroke="currentColor" fill="none" strokeWidth="1.5" viewBox="0 0 24 24" className="shrink-0 text-ink-tertiary" height="16" width="16">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
                </svg>
                deshmukhdaniel2005@gmail.com
              </a>
              <div className="flex items-center gap-2 mt-4">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-xs text-ink-tertiary">Available for projects</span>
              </div>
            </div>

            {/* Based In */}
            <div>
              <p className="text-[11px] font-semibold text-ink-tertiary uppercase tracking-widest mb-4">Based In</p>
              <div className="flex items-center gap-2">
                <svg stroke="currentColor" fill="none" strokeWidth="1.5" viewBox="0 0 24 24" className="text-ink-tertiary shrink-0" height="16" width="16">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                </svg>
                <p className="text-sm text-ink-muted">Mumbai, India</p>
              </div>
              <p className="text-xs text-ink-tertiary mt-2 ml-6">Remote-Friendly</p>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="mt-12 pt-6 border-t border-border/50 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-ink-tertiary">&copy; 2026 Daniel Shashank Deshmukh. All rights reserved.</p>
            <div className="flex items-center gap-4 text-xs text-ink-tertiary">
              <span className="hover:text-ink-muted transition-colors cursor-default">Terms</span>
              <span className="hover:text-ink-muted transition-colors cursor-default">Privacy</span>
              <span className="hover:text-ink-muted transition-colors cursor-default">Refund</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StepCard({ number, title, description, accent }: { number: string; title: string; description: string; accent?: boolean }) {
  return (
    <div className={`text-center p-4 rounded-lg border ${accent ? "border-primary/30 bg-primary/5" : "border-border bg-surface-2"}`}>
      <div className={`w-8 h-8 rounded-md ${accent ? "bg-primary/10 text-primary" : "bg-surface-3 text-ink-subtle"} flex items-center justify-center text-xs font-mono mx-auto mb-3`}>
        {number}
      </div>
      <h3 className="font-semibold text-sm mb-1">{title}</h3>
      <p className="text-xs text-ink-muted leading-relaxed">{description}</p>
    </div>
  );
}

function Arrow() {
  return (
    <div className="hidden md:flex items-center justify-center text-ink-tertiary">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12h14" />
        <path d="m12 5 7 7-7 7" />
      </svg>
    </div>
  );
}

function Feature({ title, description }: { title: string; description: string }) {
  return (
    <div className="p-5 rounded-lg border border-border bg-surface-1 hover:border-border/80 transition-colors">
      <h3 className="font-semibold text-sm mb-2">{title}</h3>
      <p className="text-sm text-ink-muted leading-relaxed">{description}</p>
    </div>
  );
}

function RoleCard({ name, level, description, dotColor }: { name: string; level: string; description: string; dotColor: string }) {
  return (
    <div className="p-4 rounded-lg border border-border bg-surface-2 text-center">
      <div className="flex items-center justify-center gap-1.5 mb-2">
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        <span className="text-xs font-mono text-ink-tertiary">Level {level}</span>
      </div>
      <div className="font-semibold text-sm mb-0.5">{name}</div>
      <div className="text-xs text-ink-muted">{description}</div>
    </div>
  );
}

function SocialIcon({ href, label, children }: { href: string; label: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" aria-label={label} className="w-9 h-9 rounded-full border border-border flex items-center justify-center text-ink-tertiary hover:text-primary hover:border-primary/40 transition-all">
      <svg stroke="currentColor" fill="currentColor" strokeWidth="0" viewBox="0 0 512 512" height="14" width="14">
        {children}
      </svg>
    </a>
  );
}
