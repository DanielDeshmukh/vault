"use client";

import Link from "next/link";

const CONNECTORS = [
  {
    name: "Zendesk",
    status: "implemented",
    description: "Fetch tickets, comments, and attachments from Zendesk. Supports organization-level filtering.",
    config: ["subdomain", "email", "api_token", "org_id"],
    icon: "Z",
  },
  {
    name: "Jira",
    status: "implemented",
    description: "Pull issues, comments, and linked documentation from Jira projects.",
    config: ["domain", "email", "api_token", "project_key"],
    icon: "J",
  },
  {
    name: "Slack",
    status: "implemented",
    description: "Ingest channel exports, threads, and reactions from Slack workspaces.",
    config: ["bot_token", "workspace_id", "channels"],
    icon: "S",
  },
  {
    name: "Confluence",
    status: "implemented",
    description: "Sync pages, spaces, and embedded documents from Confluence.",
    config: ["base_url", "email", "api_token", "space_key"],
    icon: "C",
  },
  {
    name: "Transcripts",
    status: "implemented",
    description: "Process meeting transcripts from Gong, Chorus, or plain text uploads.",
    config: ["source_type", "api_key"],
    icon: "T",
  },
  {
    name: "CSV Upload",
    status: "implemented",
    description: "Upload CSV files with structured data. Auto-detects columns and maps to metadata.",
    config: ["file"],
    icon: "CSV",
  },
  {
    name: "Policy Docs",
    status: "implemented",
    description: "Ingest PDF, DOCX, and TXT files for policy documents and SOPs.",
    config: ["file"],
    icon: "P",
  },
];

export default function ConnectorsPage() {
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
        <div className="b-label mb-4">Source Connectors</div>
        <h1 className="b-h2 mb-6">7 connectors. One permission model.</h1>
        <p className="text-ink-muted text-lg max-w-2xl mb-16">
          Every connector feeds documents into the same ingestion pipeline. Permission metadata is extracted and enforced at query time, not at import time.
        </p>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {CONNECTORS.map((c) => (
            <div key={c.name} className="b-card">
              <div className="flex items-center justify-between mb-4">
                <span className="mono text-[11px] accent">{c.icon}</span>
                <span className="mono text-[10px] text-ink-tertiary uppercase">{c.status}</span>
              </div>
              <h3 className="font-bold text-xl mb-2">{c.name}</h3>
              <p className="text-ink-subtle text-sm mb-4">{c.description}</p>
              <div className="mono text-[10px] text-ink-tertiary">
                Config: {c.config.join(", ")}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-16 border-t-2 border-border pt-12">
          <h2 className="b-h2 mb-6">Adding a new connector</h2>
          <p className="text-ink-muted mb-6">
            All connectors implement the <code className="mono text-accent">BaseConnector</code> interface. To add a new source:
          </p>
          <div className="b-terminal !shadow-none">
            <div className="b-terminal-bar">
              <span>server/app/ingestion/connectors/</span>
            </div>
            <pre className="p-4 text-[12px] leading-relaxed text-ink-muted overflow-x-auto">{`class YourConnector(BaseConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.YOUR_SOURCE

    async def fetch(self, config: dict) -> AsyncIterator[RawDocument]:
        # Fetch documents from your source
        yield RawDocument(...)

    def extract_metadata(self, doc: RawDocument, config: dict) -> DocumentMetadata:
        # Extract permission metadata
        return DocumentMetadata(...)`}</pre>
          </div>
        </div>
      </main>
    </div>
  );
}
