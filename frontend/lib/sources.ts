// Source-kind metadata shared by the documents list, the document preview
// and the chunk preview: one mapping, one link resolver, no divergence.

// Sources are stored as "kind:path" (e.g. "gitlab-handbook:product/ux/_index.md").
// The UI labels and iconifies by kind only -- the raw stored path is an
// implementation detail and is kept as a hover tooltip, never shown inline.
export const SOURCE_META: Record<string, { label: string; icon: string }> = {
  "gitlab-handbook": {
    label: "GitLab Handbook",
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  },
  cuad: {
    label: "CUAD Contracts",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  "sec-edgar": {
    label: "SEC EDGAR",
    icon: "M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3",
  },
  https: {
    label: "Web",
    icon: "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9",
  },
  default: {
    label: "Document",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
};

export const SOURCE_UNKNOWN = SOURCE_META.default;

export function sourceInfo(source?: string) {
  const head = (source ?? "").split(":")[0].trim().toLowerCase();
  return SOURCE_META[head] ?? SOURCE_UNKNOWN;
}

// Links inside the corpus are written for the document's original site.
// Rendered unchanged they resolve against the Vault origin, so a handbook
// href such as "../../upstream-studios/" becomes /upstream-studios and 404s.
// Resolve relative hrefs against the source's real home instead; anything
// that cannot be placed confidently stays plain text rather than a dead link.
export const SOURCE_BASES: Record<string, string> = {
  "gitlab-handbook": "https://handbook.gitlab.com/handbook/",
};

// "gitlab-handbook:product/ux/_index.md" -> the page's URL on the source site.
// Handbook pages are directory-style (".../product/ux/"), so a filename becomes
// a directory and "_index.md" becomes its parent.
export function sourcePageUrl(source?: string): string | null {
  if (!source) return null;
  const cut = source.indexOf(":");
  const kind = cut === -1 ? source : source.slice(0, cut);
  const path = cut === -1 ? "" : source.slice(cut + 1);
  const base = SOURCE_BASES[kind];
  if (!base) return null;
  if (!path) return base;

  const rel = path.replace(/\\/g, "/").replace(/^\/+/, "");
  const url = rel.endsWith("_index.md")
    ? rel.slice(0, -"_index.md".length)
    : rel.endsWith(".md")
      ? `${rel.slice(0, -3)}/`
      : rel.endsWith("/")
        ? rel
        : `${rel}/`;
  try {
    return new URL(url, base).toString();
  } catch {
    return null;
  }
}
