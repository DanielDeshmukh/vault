"use client";

import { useEffect, useState } from "react";
import { api, type ChunkDetail } from "@/lib/api";
import { sourceInfo, sourcePageUrl } from "@/lib/sources";
import { DocumentPreview } from "@/components/document-preview";

// Badge labels for the v2 source_type column; v1 rows fall through to the
// shared kind-based labels (source_type then holds the document source kind).
const SOURCE_TYPE_LABELS: Record<string, string> = {
  md: "Markdown",
  cuad_txt: "CUAD Contract",
  sec_htm: "SEC Filing",
  pdf: "PDF",
};

// Resolve the value the link resolver understands ("kind:path").
// v1 rows may already be in that form; v2 handbook paths are corpus-relative
// ("general/gitlab_handbook/...") and are mapped to the handbook kind.
// Other v2 sources have no external page to link to -> null (badge only).
function linkSourceFor(chunk: ChunkDetail): string | null {
  const src = chunk.source_path;
  if (!src) return null;
  if (src.includes(":")) return src;
  const marker = "gitlab_handbook/";
  const idx = src.indexOf(marker);
  if (chunk.source_type === "md" && idx !== -1) {
    return `gitlab-handbook:${src.slice(idx + marker.length)}`;
  }
  return null;
}

export function ChunkPreviewModal({
  chunkId,
  onClose,
}: {
  chunkId: string;
  onClose: () => void;
}) {
  const [chunk, setChunk] = useState<ChunkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setChunk(null);
    api
      .getChunk(chunkId)
      .then((detail) => {
        if (!cancelled) setChunk(detail);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load chunk");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chunkId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const linkSource = chunk ? linkSourceFor(chunk) : null;
  const sourceHref = linkSource ? sourcePageUrl(linkSource) : null;
  const typeLabel = chunk
    ? SOURCE_TYPE_LABELS[chunk.source_type ?? ""] ??
      sourceInfo(chunk.source_path ?? chunk.source_type ?? undefined).label
    : "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Chunk preview">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative bg-surface-1 border border-border rounded-lg w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-medium text-sm truncate">{chunk?.title ?? "Chunk preview"}</p>
              <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                {chunk?.department && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/15 text-blue-400">
                    {chunk.department}
                  </span>
                )}
                {typeLabel && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-surface-2 border border-border text-ink-muted">
                    {typeLabel}
                  </span>
                )}
                {sourceHref && (
                  <a
                    href={sourceHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-medium text-primary underline underline-offset-2"
                  >
                    View source
                  </a>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              aria-label="Close chunk preview"
              className="p-1.5 rounded-md text-ink-tertiary hover:text-foreground hover:bg-surface-2 ml-3 flex-shrink-0"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Heading path breadcrumb: sits above the chunk body (plan Phase 4). */}
          {chunk && chunk.heading_path.length > 0 && (
            <nav
              aria-label="Heading path"
              className="flex flex-wrap items-center gap-1 text-[11px] text-ink-tertiary mt-2"
            >
              {chunk.heading_path.map((crumb, i) => (
                <span key={`${i}-${crumb}`} className="flex items-center gap-1">
                  {i > 0 && <span aria-hidden="true">&rsaquo;</span>}
                  <span
                    className={
                      i === chunk.heading_path.length - 1
                        ? "text-ink-muted font-medium"
                        : ""
                    }
                  >
                    {crumb}
                  </span>
                </span>
              ))}
            </nav>
          )}
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-ink-muted text-sm">
              Loading...
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-32 text-destructive text-sm">
              {error}
            </div>
          ) : chunk ? (
            <DocumentPreview
              content={chunk.text_md}
              source={linkSource ?? undefined}
              markdown
            />
          ) : (
            <div className="flex items-center justify-center h-32 text-ink-muted text-sm">
              Chunk not found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
