"use client";

import Link from "next/link";

export default function Home() {
  return (
    <div className="brutalist min-h-screen flex flex-col">
      {/* ─── NAV ─── */}
      <nav className="border-b-2 border-[#222] sticky top-0 z-50 bg-black">
        <div className="max-w-[1400px] mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs tracking-[0.2em] uppercase text-[#555]">SYS</span>
            <span className="text-white font-bold text-lg tracking-tight">VAULT</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/login" className="font-mono text-xs uppercase text-[#888] hover:text-white tracking-wider transition-colors">
              Sign In
            </Link>
            <Link href="/register" className="font-mono text-xs uppercase text-black bg-white px-4 py-1.5 hover:bg-[#BAFF29] transition-colors tracking-wider">
              Register
            </Link>
          </div>
        </div>
      </nav>

      <main className="flex-1">
        {/* ─── HERO ─── */}
        <section className="border-b-2 border-[#222]">
          <div className="max-w-[1400px] mx-auto px-6 py-16 md:py-24">
            <div className="grid md:grid-cols-[1fr_340px] gap-12 md:gap-16 items-start">
              <div>
                <div className="font-mono text-[10px] tracking-[0.25em] uppercase text-[#555] mb-6">
                  Permission-Aware RAG / v0.1
                </div>
                <h1 className="b-headline mb-8">
                  Enterprise<br />
                  Knowledge,<br />
                  <span className="text-[#BAFF29]">Secured by<br />Role</span>
                </h1>
                <p className="text-[#999] text-base max-w-md leading-relaxed mb-10">
                  Ask questions across your organization&apos;s documents. Vault filters
                  results by your role before the AI even sees them.
                </p>
                <div className="flex items-center gap-3">
                  <Link href="/register" className="b-btn">
                    Create Account
                  </Link>
                  <Link href="/login" className="b-btn b-btn-outline">
                    Sign In
                  </Link>
                </div>
              </div>

              {/* Stats panel */}
              <div className="border-2 border-[#333] p-6">
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-5">
                  System Status
                </div>
                <div className="space-y-5">
                  <div className="flex items-baseline justify-between border-b border-[#222] pb-4">
                    <span className="font-mono text-xs text-[#666] uppercase">Access Levels</span>
                    <span className="b-stat-num !text-3xl">4</span>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-[#222] pb-4">
                    <span className="font-mono text-xs text-[#666] uppercase">Documents</span>
                    <span className="b-stat-num !text-3xl">17</span>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-[#222] pb-4">
                    <span className="font-mono text-xs text-[#666] uppercase">Chunks</span>
                    <span className="b-stat-num !text-3xl">3.5k</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-xs text-[#666] uppercase">Status</span>
                    <span className="font-mono text-xs text-[#BAFF29]">OPERATIONAL</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── PIPELINE ─── */}
        <section className="border-b-2 border-[#222]">
          <div className="max-w-[1400px] mx-auto px-6 py-14 md:py-20">
            <div className="grid md:grid-cols-[200px_1fr] gap-8">
              <div>
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-3">
                  Architecture
                </div>
                <h2 className="text-xl font-bold">Pipeline</h2>
              </div>
              <div>
                <p className="text-[#888] text-sm max-w-lg mb-10 leading-relaxed">
                  Permission checks happen at the vector database level. Restricted content
                  never reaches the language model. No post-retrieval filtering. No侥幸.
                </p>
                <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] gap-0 items-stretch">
                  <div className="b-step">
                    <div className="b-step-num">01</div>
                    <div className="font-bold text-sm mb-1">Query</div>
                    <div className="text-[11px] text-[#666]">Natural language input</div>
                  </div>
                  <div className="b-arrow px-2">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </div>
                  <div className="b-step active">
                    <div className="b-step-num">02</div>
                    <div className="font-bold text-sm mb-1">RBAC Filter</div>
                    <div className="text-[11px] text-[#666]">Pre-retrieval enforcement</div>
                  </div>
                  <div className="b-arrow px-2">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </div>
                  <div className="b-step">
                    <div className="b-step-num">03</div>
                    <div className="font-bold text-sm mb-1">Generate</div>
                    <div className="text-[11px] text-[#666]">Cited response via LLM</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── FEATURES ─── */}
        <section className="border-b-2 border-[#222]">
          <div className="max-w-[1400px] mx-auto px-6 py-14 md:py-20">
            <div className="grid md:grid-cols-[200px_1fr] gap-8">
              <div>
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-3">
                  Capabilities
                </div>
                <h2 className="text-xl font-bold">Features</h2>
              </div>
              <div className="grid md:grid-cols-2 gap-0">
                <div className="b-card border-r-0 border-b-0 md:border-b-2">
                  <div className="font-mono text-[10px] text-[#BAFF29] mb-2 tracking-wider">01</div>
                  <h3 className="font-bold text-sm mb-2">Pre-Retrieval Filtering</h3>
                  <p className="text-[13px] text-[#888] leading-relaxed">
                    Permission checks at the vector database level. Unauthorized chunks
                    never sent to the language model.
                  </p>
                </div>
                <div className="b-card border-b-0 md:border-b-2">
                  <div className="font-mono text-[10px] text-[#BAFF29] mb-2 tracking-wider">02</div>
                  <h3 className="font-bold text-sm mb-2">Hybrid Search</h3>
                  <p className="text-[13px] text-[#888] leading-relaxed">
                    Vector similarity + keyword matching + Cohere reranking.
                    Precise retrieval across large document collections.
                  </p>
                </div>
                <div className="b-card border-r-0">
                  <div className="font-mono text-[10px] text-[#BAFF29] mb-2 tracking-wider">03</div>
                  <h3 className="font-bold text-sm mb-2">Streaming Citations</h3>
                  <p className="text-[13px] text-[#888] leading-relaxed">
                    Real-time streaming responses with inline document citations.
                    Every claim traced to its source.
                  </p>
                </div>
                <div className="b-card">
                  <div className="font-mono text-[10px] text-[#BAFF29] mb-2 tracking-wider">04</div>
                  <h3 className="font-bold text-sm mb-2">Audit Trail</h3>
                  <p className="text-[13px] text-[#888] leading-relaxed">
                    Every query, retrieval, and answer logged with trace IDs
                    for compliance and debugging.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── RBAC ─── */}
        <section className="border-b-2 border-[#222]">
          <div className="max-w-[1400px] mx-auto px-6 py-14 md:py-20">
            <div className="grid md:grid-cols-[200px_1fr] gap-8">
              <div>
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-3">
                  Security Model
                </div>
                <h2 className="text-xl font-bold">RBAC</h2>
              </div>
              <div>
                <p className="text-[#888] text-sm max-w-lg mb-10 leading-relaxed">
                  Four permission levels. Admin assigns roles. Users see only what their
                  role allows. Documents classified by access level. Filter enforced at
                  query time.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
                  <div className="b-role border-r-0 md:border-r-2" data-level="0">
                    <div className="font-mono text-[10px] text-[#555] mb-1">LEVEL 0</div>
                    <div className="font-bold text-sm mb-0.5">Public</div>
                    <div className="text-[11px] text-[#666]">General documents</div>
                  </div>
                  <div className="b-role border-r-0 md:border-r-2" data-level="1">
                    <div className="font-mono text-[10px] text-[#555] mb-1">LEVEL 1</div>
                    <div className="font-bold text-sm mb-0.5">Internal</div>
                    <div className="text-[11px] text-[#666]">Company-wide</div>
                  </div>
                  <div className="b-role border-r-0 md:border-r-2" data-level="2">
                    <div className="font-mono text-[10px] text-[#555] mb-1">LEVEL 2</div>
                    <div className="font-bold text-sm mb-0.5">Confidential</div>
                    <div className="text-[11px] text-[#666]">Sensitive data</div>
                  </div>
                  <div className="b-role" data-level="3">
                    <div className="font-mono text-[10px] text-[#555] mb-1">LEVEL 3</div>
                    <div className="font-bold text-sm mb-0.5">Restricted</div>
                    <div className="text-[11px] text-[#666]">Limited access</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── STACK ─── */}
        <section className="border-b-2 border-[#222]">
          <div className="max-w-[1400px] mx-auto px-6 py-14 md:py-20">
            <div className="grid md:grid-cols-[200px_1fr] gap-8">
              <div>
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-3">
                  Infrastructure
                </div>
                <h2 className="text-xl font-bold">Stack</h2>
              </div>
              <div className="flex flex-wrap gap-0">
                {["FastAPI", "Next.js 14", "PostgreSQL", "Pinecone", "Cohere", "SQLAlchemy", "JWT Auth", "Tailwind", "Vercel"].map((tech) => (
                  <span key={tech} className="b-tag">{tech}</span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ─── CTA ─── */}
        <section>
          <div className="max-w-[1400px] mx-auto px-6 py-14 md:py-20">
            <div className="grid md:grid-cols-[200px_1fr] gap-8">
              <div>
                <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#555] mb-3">
                  Get Started
                </div>
                <h2 className="text-xl font-bold">Try Vault</h2>
              </div>
              <div>
                <p className="text-[#888] text-sm max-w-lg mb-8 leading-relaxed">
                  Create an account and explore how permission-aware retrieval works
                  across different access levels. Public users see public docs. Internal
                  users see more. Admins see everything.
                </p>
                <div className="flex items-center gap-3">
                  <Link href="/register" className="b-btn">
                    Create Account
                  </Link>
                  <Link href="/login" className="b-btn b-btn-outline">
                    Sign In
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ─── FOOTER ─── */}
      <footer className="border-t-2 border-[#222] bg-black">
        <div className="max-w-[1400px] mx-auto px-6 py-12">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-8">
            {/* Brand */}
            <div>
              <p className="text-sm font-bold text-white mb-1">Daniel Deshmukh</p>
              <p className="font-mono text-[10px] text-[#555] uppercase tracking-wider mb-5">Full-Stack Developer</p>
              <div className="flex items-center gap-2">
                <a href="https://x.com/DeshmukhDa71837" target="_blank" rel="noreferrer" aria-label="X" className="b-social">
                  <svg stroke="currentColor" fill="currentColor" strokeWidth="0" viewBox="0 0 512 512" height="13" width="13">
                    <path d="M389.2 48h70.6L305.6 224.2 487 464H345L233.7 318.6 106.5 464H35.8L200.7 275.5 26.8 48H172.4L272.9 180.9 389.2 48zM364.4 421.8h39.1L151.1 88h-42L364.4 421.8z" />
                  </svg>
                </a>
                <a href="https://github.com/DanielDeshmukh" target="_blank" rel="noreferrer" aria-label="GitHub" className="b-social">
                  <svg stroke="currentColor" fill="currentColor" strokeWidth="0" viewBox="0 0 496 512" height="14" width="14">
                    <path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8z" />
                  </svg>
                </a>
                <a href="https://www.linkedin.com/in/daniel-deshmukh-7b08602b2" target="_blank" rel="noreferrer" aria-label="LinkedIn" className="b-social">
                  <svg stroke="currentColor" fill="currentColor" strokeWidth="0" viewBox="0 0 448 512" height="13" width="13">
                    <path d="M100.28 448H7.4V148.9h92.88zM53.79 108.1C24.09 108.1 0 83.5 0 53.8a53.79 53.79 0 0 1 107.58 0c0 29.7-24.1 54.3-53.79 54.3zM447.9 448h-92.68V302.4c0-34.7-.7-79.2-48.29-79.2-48.29 0-55.69 37.7-55.69 76.7V448h-92.78V148.9h89.08v40.8h1.3c12.4-23.5 42.69-48.3 87.88-48.3 94 0 111.28 61.9 111.28 142.3V448z" />
                  </svg>
                </a>
              </div>
            </div>

            {/* Navigation */}
            <div className="b-footer-col">
              <h4>Navigation</h4>
              <ul className="space-y-2 text-sm text-[#888]">
                <li><Link href="/#about" className="hover:text-white transition-colors">About</Link></li>
                <li><Link href="/#projects" className="hover:text-white transition-colors">Projects</Link></li>
                <li><Link href="/#clients" className="hover:text-white transition-colors">Clients</Link></li>
                <li><a href="https://danieldeshmukh-portfolio.vercel.app/enquiry" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>

            {/* Contact */}
            <div className="b-footer-col">
              <h4>Contact</h4>
              <a href="mailto:deshmukhdaniel2005@gmail.com" className="flex items-center gap-2 text-sm text-[#888] hover:text-white transition-colors break-all">
                <svg stroke="currentColor" fill="none" strokeWidth="1.5" viewBox="0 0 24 24" className="shrink-0 text-[#555]" height="14" width="14">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
                </svg>
                deshmukhdaniel2005@gmail.com
              </a>
              <div className="flex items-center gap-2 mt-4">
                <span className="w-2 h-2 rounded-none bg-[#BAFF29]" />
                <span className="font-mono text-[10px] text-[#555] uppercase tracking-wider">Available for projects</span>
              </div>
            </div>

            {/* Based In */}
            <div className="b-footer-col">
              <h4>Based In</h4>
              <div className="flex items-center gap-2">
                <svg stroke="currentColor" fill="none" strokeWidth="1.5" viewBox="0 0 24 24" className="text-[#555] shrink-0" height="14" width="14">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
                </svg>
                <p className="text-sm text-[#888]">Mumbai, India</p>
              </div>
              <p className="font-mono text-[10px] text-[#444] mt-2 ml-5 uppercase tracking-wider">Remote-Friendly</p>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="mt-12 pt-5 border-t border-[#222] flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="font-mono text-[10px] text-[#444] tracking-wider">
              &copy; 2026 DANIEL SHASHANK DESHMUKH. ALL RIGHTS RESERVED.
            </p>
            <div className="flex items-center gap-5 font-mono text-[10px] text-[#444] tracking-wider uppercase">
              <span className="hover:text-[#888] transition-colors cursor-default">Terms</span>
              <span className="hover:text-[#888] transition-colors cursor-default">Privacy</span>
              <span className="hover:text-[#888] transition-colors cursor-default">Refund</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
