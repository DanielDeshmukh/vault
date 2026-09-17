"use client";

import { useState, useEffect, useCallback } from "react";
import { api, Document } from "@/lib/api";
import { Button } from "@/components/ui/button";

const LEVEL_LABELS = ["Public", "Internal", "Confidential", "Restricted"];
const LEVEL_COLORS = [
  "bg-surface-3 text-ink-muted",
  "bg-blue-500/15 text-blue-400",
  "bg-amber-500/15 text-amber-400",
  "bg-red-500/15 text-red-400",
];

const SOURCE_ICONS: Record<string, string> = {
  pdf: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
  csv: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  txt: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  default: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source", file.name.split(".").pop() || "csv");
      formData.append("account_id", "unknown");
      formData.append("department", "general");
      formData.append("access_level", "0");
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { Authorization: `Bearer ${api.getToken()}` },
        body: formData,
      });
      if (!response.ok) throw new Error("Upload failed");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handlePreview = useCallback(async (doc: Document) => {
    if (doc.can_access === false) {
      setPreviewDoc(doc);
      setPreviewError("Access denied — your role does not have permission to view this document.");
      setPreviewLoading(false);
      return;
    }
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-muted">
        Loading documents...
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold font-display">Documents</h1>
          <p className="text-sm text-ink-muted mt-1">Manage ingested documents</p>
        </div>
        <div className="flex-shrink-0">
          <input type="file" id="file-upload" className="hidden" accept=".csv,.pdf,.docx,.txt" onChange={handleUpload} />
          <Button asChild disabled={uploading} size="sm">
            <label htmlFor="file-upload" className="cursor-pointer">
              {uploading ? "Uploading..." : "Upload"}
            </label>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {documents.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface-1 p-12 text-center">
          <p className="text-ink-muted mb-2">No documents yet</p>
          <p className="text-sm text-ink-tertiary">Upload a CSV, PDF, or text file to get started</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="rounded-lg border border-border bg-surface-1 p-4 hover:border-border/80 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0">
                  {doc.can_access === false ? (
                    <svg className="w-4 h-4 text-ink-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4 text-ink-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={SOURCE_ICONS[doc.source] || SOURCE_ICONS.default} />
                    </svg>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-medium text-sm truncate">{doc.title}</p>
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${LEVEL_COLORS[doc.access_level] || LEVEL_COLORS[0]}`}>
                      {LEVEL_LABELS[doc.access_level] || "Unknown"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-ink-tertiary">
                    <span>{doc.source.toUpperCase()}</span>
                    {doc.department && (
                      <>
                        <span className="text-border">|</span>
                        <span>{doc.department}</span>
                      </>
                    )}
                    {doc.account_id && doc.account_id !== "unknown" && (
                      <>
                        <span className="text-border">|</span>
                        <span>{doc.account_id}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
                {doc.can_access === false ? (
                  <span className="h-7 flex items-center gap-1 text-xs text-ink-tertiary px-2">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                    Access denied
                  </span>
                ) : (
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
                )}
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
                  <span className={`ml-2 px-1.5 py-0.5 rounded ${LEVEL_COLORS[previewDoc.access_level] || LEVEL_COLORS[0]}`}>
                    {LEVEL_LABELS[previewDoc.access_level]}
                  </span>
                </p>
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
                <pre className="text-sm text-ink-muted whitespace-pre-wrap font-sans leading-relaxed">{previewDoc.content}</pre>
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
