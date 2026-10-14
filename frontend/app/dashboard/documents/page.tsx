"use client";

import { useState, useEffect, useCallback } from "react";
import { api, Classification, Document } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DocumentPreview } from "@/components/document-preview";

const SOURCE_ICONS: Record<string, string> = {
  pdf: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
  csv: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  txt: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  default: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
};

const MAX_ROLE_PILLS = 3;
const INITIAL_LIMIT = 10;
const PAGE_LIMIT = 50;
const SEARCH_DEBOUNCE_MS = 250;

type Filter = "all" | Classification;

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "internal", label: "Internal" },
  { value: "restricted", label: "Restricted" },
];

function RolePills({ roles }: { roles?: string[] }) {
  if (!roles || roles.length === 0) {
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/15 text-red-400 flex-shrink-0">
        no roles
      </span>
    );
  }
  const shown = roles.slice(0, MAX_ROLE_PILLS);
  return (
    <span className="flex items-center gap-1 flex-shrink-0">
      {shown.map((r) => (
        <span
          key={r}
          className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/15 text-blue-400 capitalize"
        >
          {r}
        </span>
      ))}
      {roles.length > shown.length && (
        <span className="text-[10px] text-ink-tertiary">+{roles.length - shown.length}</span>
      )}
    </span>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  const classification = filter === "all" ? undefined : filter;

  // Debounced so a keystroke does not fire a query per character. Setting the
  // same value back is a no-op, so this does not double-fetch on mount.
  useEffect(() => {
    const timer = setTimeout(
      () => setQuery(searchInput.trim()),
      SEARCH_DEBOUNCE_MS
    );
    return () => clearTimeout(timer);
  }, [searchInput]);

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.listDocuments({
        limit: INITIAL_LIMIT,
        offset: 0,
        classification,
        q: query || undefined,
      });
      setDocuments(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [classification, query]);

  useEffect(() => {
    loadFirstPage();
  }, [loadFirstPage]);

  const loadMore = async () => {
    setLoadingMore(true);
    setError("");
    try {
      const res = await api.listDocuments({
        limit: PAGE_LIMIT,
        offset: documents.length,
        classification,
        q: query || undefined,
      });
      setDocuments((prev) => [...prev, ...res.items]);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoadingMore(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handlePreview = useCallback(async (doc: Document) => {
    setPreviewDoc(doc);
    setPreviewLoading(true);
    setPreviewError("");
    try {
      const full = await api.getDocument(doc.id);
      setPreviewDoc(full);
    } catch (err: any) {
      const msg = err?.message || "Access denied";
      setPreviewError(msg.includes("403") || msg.includes("Access denied") || msg.includes("Insufficient")
        ? "Access denied — your role does not have permission to view this document."
        : msg);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const filtered = filter !== "all" || query.length > 0;

  return (
    <div className="p-4 md:p-6 space-y-4 w-full overflow-hidden">
      <div>
        <h1 className="text-xl md:text-2xl font-bold font-display">Documents</h1>
        <p className="text-sm text-ink-muted mt-1">
          {total > 0 ? `${total.toLocaleString()} documents` : "Manage ingested documents"}
        </p>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-3">
        <div className="relative w-full md:w-80">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-tertiary pointer-events-none"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
            />
          </svg>
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search titles and contents…"
            aria-label="Search documents"
            className="w-full h-9 rounded-md border border-border bg-surface-1 pl-9 pr-3 text-sm text-foreground placeholder:text-ink-tertiary focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>

        <div className="flex items-center gap-2">
          {FILTERS.map((f) => {
            const active = filter === f.value;
            return (
              <button
                key={f.value}
                type="button"
                onClick={() => setFilter(f.value)}
                aria-pressed={active}
                className={
                  active
                    ? "h-8 px-3 rounded-md text-xs font-medium bg-primary text-primary-foreground"
                    : "h-8 px-3 rounded-md text-xs font-medium border border-border text-ink-muted hover:text-foreground hover:bg-surface-1"
                }
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40 text-ink-muted text-sm">
          Loading documents...
        </div>
      ) : documents.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface-1 p-12 text-center">
          <p className="text-ink-muted mb-2">
            {filtered ? "No documents match your search" : "No documents yet"}
          </p>
          <p className="text-sm text-ink-tertiary">
            {filtered
              ? "Try a different term or clear the filters."
              : "Documents are ingested by an administrator."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="rounded-lg border border-border bg-surface-1 p-4 hover:border-border/80 transition-colors overflow-hidden"
              >
                <div className="flex items-start gap-3 overflow-hidden">
                  <div className="w-9 h-9 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-ink-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={SOURCE_ICONS[doc.source] || SOURCE_ICONS.default} />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm truncate">{doc.title}</p>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <RolePills roles={doc.allowed_roles} />
                      <div className="flex items-center gap-1.5 text-[11px] text-ink-tertiary truncate">
                        <span>{doc.source.toUpperCase()}</span>
                        {doc.department && (
                          <>
                            <span className="text-border">|</span>
                            <span className="truncate">{doc.department}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handlePreview(doc)}
                    className="h-7 text-xs px-2 text-ink-muted hover:text-foreground"
                  >
                    <svg className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Read
                  </Button>
                  <div className="flex-1" />
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(doc.id)}
                    className="h-7 text-xs px-2 text-ink-tertiary hover:text-destructive"
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col items-center gap-2 pt-1">
            <span className="text-xs text-ink-tertiary">
              Showing {documents.length.toLocaleString()} of {total.toLocaleString()}
            </span>
            {documents.length < total && (
              <Button variant="outline" size="sm" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading…" : "Show more"}
              </Button>
            )}
          </div>
        </>
      )}

      {/* Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70" onClick={() => setPreviewDoc(null)} />
          <div className="relative bg-surface-1 border border-border rounded-lg w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <div className="min-w-0">
                <p className="font-medium text-sm truncate">{previewDoc.title}</p>
                <p className="text-xs text-ink-tertiary mt-0.5">
                  {previewDoc.source.toUpperCase()}
                  {previewDoc.department && ` — ${previewDoc.department}`}
                </p>
                <div className="mt-1">
                  <RolePills roles={previewDoc.allowed_roles} />
                </div>
              </div>
              <button onClick={() => setPreviewDoc(null)} className="p-1.5 rounded-md text-ink-tertiary hover:text-foreground hover:bg-surface-2 ml-3">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {previewLoading ? (
                <div className="flex items-center justify-center h-32 text-ink-muted text-sm">Loading...</div>
              ) : previewError ? (
                <div className="flex flex-col items-center justify-center h-32 text-center">
                  <svg className="w-10 h-10 text-destructive mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                  <p className="text-sm text-destructive font-medium">{previewError}</p>
                </div>
              ) : previewDoc.content ? (
                <DocumentPreview content={previewDoc.content} />
              ) : (
                <div className="flex items-center justify-center h-32 text-ink-muted text-sm">No content available</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
