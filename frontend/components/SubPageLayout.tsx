"use client";

import Link from "next/link";

export function SubPageLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="brutalist min-h-screen">
      <header className="sticky top-0 z-50 bg-background border-b-2 border-foreground">
        <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <img src="/tab-icon.png" alt="Vault" className="w-8 h-8 rounded" />
            <span className="font-bold tracking-tight text-lg">VAULT</span>
          </Link>
          <Link href="/" className="b-btn !py-2 !px-4 text-[11px]">Back to Home</Link>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 md:px-12 py-20">
        {children}
      </main>
    </div>
  );
}
