"use client";

import { useMemo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

import { sourcePageUrl } from "@/lib/sources";

const H1 = "text-2xl font-semibold text-foreground mt-6 mb-3 first:mt-0";
const H2 = "text-xl font-semibold text-foreground mt-6 mb-3 first:mt-0";
const H3 = "text-lg font-semibold text-foreground mt-5 mb-2 first:mt-0";
const H4 = "text-base font-semibold text-foreground mt-4 mb-2 first:mt-0";
const BODY = "text-sm leading-7 text-ink-muted my-3";
const ITEM = "text-sm leading-7 text-ink-muted";
const INLINE_CODE = "font-mono text-xs bg-surface-2 rounded px-1 py-0.5";
const BLOCK_CODE =
  "font-mono text-xs bg-surface-2 border border-border rounded p-3 overflow-x-auto my-3 whitespace-pre";

type Block =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "item"; text: string };

// Scored rather than a single pattern: one signal is a coincidence (a
// contract can contain "**" or a "- " line), two is a document written as
// markdown. Handbooks carry "# " headings, which alone clears the bar.
const MARKDOWN_SIGNALS: Array<[RegExp, number]> = [
  [/^#{1,6} \S.*$/m, 2],
  [/^ {0,3}```/m, 2],
  [/\[[^\]\n]+\]\([^)\n]+\)/, 2],
  [/\*\*[^*\n]+\*\*/, 1],
  [/^\s*[-*+] \S.*$/m, 1],
];

function looksLikeMarkdown(text: string): boolean {
  let score = 0;
  for (const [pattern, weight] of MARKDOWN_SIGNALS) {
    if (pattern.test(text)) score += weight;
    if (score >= 2) return true;
  }
  return false;
}

// Imported pages carry authoring artefacts: markdownlint comments, stray
// <br>/<p>/<span> tags and numeric entities. React deliberately does not
// render raw HTML, so without this pass readers see the tags themselves.
// A closed whitelist is used rather than "<[^>]+>" -- an unrestricted
// pattern would eat genuine prose such as "to < 100 GB for GitLab.com".
const HTML_COMMENT = /<!--[\s\S]*?-->/g;
// Formatting tags that are used bare ("<b>", "<br/>"): attributes are refused
// outright, so prose like "a<b when b>0" cannot be mistaken for a tag.
const BARE_TAGS = /<\/?(?:b|i|u|s|em|strong|br|hr)\s*\/?>/gi;
// Tags that legitimately carry attributes must actually have them, so an
// unmatched "<" in running text still cannot be swallowed.
const ATTR_TAGS =
  /<\/?(?:p|div|span|a|img|h[1-6]|ul|ol|li|table|thead|tbody|tfoot|tr|td|th|section|article|figure|figcaption|blockquote|code|pre|sub|sup|kbd|abbr)(?:\s+[a-z-]+(?::[a-z-]+)?\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']+))*\s*\/?>/gi;

const ENTITIES: Record<string, string> = {
  nbsp: " ",
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  "#39": "'",
  "#x27": "'",
  rsquo: "’",
  lsquo: "‘",
  rdquo: "”",
  ldquo: "“",
  mdash: "—",
  ndash: "–",
  hellip: "…",
};

function normalizeContent(text: string): string {
  let out = text.replace(HTML_COMMENT, "");
  // Breaks must become newlines rather than disappear with the tag.
  out = out.replace(/<\s*br\s*\/?\s*>/gi, "\n");
  out = out.replace(/<\s*\/\s*p\s*>/gi, "\n\n");
  out = out.replace(BARE_TAGS, "").replace(ATTR_TAGS, "");
  // Decoded last so "&lt;b&gt;" cannot become a tag that then gets stripped.
  return out.replace(/&([a-z#][a-z0-9]{1,8});/gi, (whole, name) => {
    const key = String(name).toLowerCase();
    return key in ENTITIES ? ENTITIES[key] : whole;
  });
}

// Top-level clause ("12. DEFINITIONS."). Deliberately requires whitespace
// after the number so sub-clauses ("12.1 The Company shall ...") stay body
// text instead of becoming headings. Length-capped so a clause whose first
// line runs on is not mistaken for a title.
const NUMBERED_HEADING = /^\s{0,4}\d{1,3}\.\s+\S.{0,88}$/;
const SECTION_HEADING =
  /^\s{0,4}(§|section|chapter|article|part|schedule|exhibit|appendix|item)\s*[:.]?\s*[\divxlc]+/i;
const CAPS_HEADING = /^\s{0,4}[A-Z0-9][A-Z0-9 ,.'&()/+-]{5,70}$/;
const BULLET = /^\s*(?:[-*•▪]|\d{1,3}[.)])\s+(.+)$/;

function parsePlainText(text: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flush = () => {
    if (paragraph.length) {
      blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  };

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    if (
      NUMBERED_HEADING.test(raw) ||
      SECTION_HEADING.test(raw) ||
      CAPS_HEADING.test(raw)
    ) {
      flush();
      blocks.push({ kind: "heading", text: line });
      continue;
    }
    const bullet = raw.match(BULLET);
    if (bullet) {
      flush();
      blocks.push({ kind: "item", text: bullet[1].trim() });
      continue;
    }
    paragraph.push(line);
  }
  flush();
  return blocks;
}

function renderBlocks(blocks: Block[]): ReactNode[] {
  const out: ReactNode[] = [];
  const list: string[] = [];

  const flushList = () => {
    if (!list.length) return;
    out.push(
      <ul key={`ul-${out.length}`} className="list-disc pl-5 my-3">
        {list.map((text, i) => (
          <li key={i} className={ITEM}>
            {text}
          </li>
        ))}
      </ul>
    );
    list.length = 0;
  };

  blocks.forEach((block, i) => {
    if (block.kind === "item") {
      list.push(block.text);
      return;
    }
    flushList();
    if (block.kind === "heading") {
      out.push(
        <h3 key={i} className={H3}>
          {block.text}
        </h3>
      );
    } else {
      out.push(
        <p key={i} className={BODY}>
          {block.text}
        </p>
      );
    }
  });
  flushList();
  return out;
}

interface MdProps {
  children?: ReactNode;
  href?: string;
}

function safeHref(href?: string, source?: string): string | null {
  const h = href?.trim();
  if (!h) return null;
  // In-page anchors do nothing outside the original page.
  if (h.startsWith("#")) return null;
  if (h.startsWith("//")) return h;
  // Absolute: keep http(s), drop javascript:/data:/file: etc.
  if (/^[a-z][a-z0-9+.-]*:/i.test(h)) return /^https?:/i.test(h) ? h : null;

  const base = sourcePageUrl(source);
  if (!base) return null;
  try {
    return new URL(h, base).toString();
  } catch {
    return null;
  }
}

// Fenced code arrives as a <code> with a language class; the languageless
// fence and inline code are told apart by content -- a fence's body always
// contains a newline, inline code never does.
function childText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(childText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return childText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function markdownComponents(source?: string) {
  return {
    h1: ({ children }: MdProps) => <h1 className={H1}>{children}</h1>,
    h2: ({ children }: MdProps) => <h2 className={H2}>{children}</h2>,
    h3: ({ children }: MdProps) => <h3 className={H3}>{children}</h3>,
    h4: ({ children }: MdProps) => <h4 className={H4}>{children}</h4>,
    h5: ({ children }: MdProps) => (
      <h5 className="text-sm font-semibold text-foreground mt-4 mb-2 first:mt-0">{children}</h5>
    ),
    h6: ({ children }: MdProps) => (
      <h6 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mt-4 mb-2 first:mt-0">{children}</h6>
    ),
    p: ({ children }: MdProps) => <p className={BODY}>{children}</p>,
    ul: ({ children }: MdProps) => (
      <ul className="list-disc pl-5 my-3">{children}</ul>
    ),
    ol: ({ children }: MdProps) => (
      <ol className="list-decimal pl-5 my-3">{children}</ol>
    ),
    li: ({ children }: MdProps) => <li className={ITEM}>{children}</li>,
    a: ({ children, href }: MdProps) => {
      const target = safeHref(href, source);
      if (!target) return <>{children}</>;
      return (
        <a
          href={target}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline underline-offset-2"
        >
          {children}
        </a>
      );
    },
    strong: ({ children }: MdProps) => (
      <strong className="font-semibold text-foreground">{children}</strong>
    ),
    em: ({ children }: MdProps) => <em className="italic">{children}</em>,
    code: ({ children, className }: MdProps & { className?: string }) => {
      const isBlock =
        Boolean(className?.includes("language-")) || /\n/.test(childText(children));
      if (isBlock) {
        // The surrounding <pre> carries the block chrome; a chip here would
        // paint one rounded blob across the whole fenced body.
        return (
          <code className={className ? `${className} text-inherit` : undefined}>
            {children}
          </code>
        );
      }
      return <code className={INLINE_CODE}>{children}</code>;
    },
    pre: ({ children }: MdProps) => <pre className={BLOCK_CODE}>{children}</pre>,
    // GFM tables (plan Phase 4): scrollable wrapper, bordered cells, sticky
    // header. The wrapper is also the vertical scroller (max-h), which is
    // what makes position:sticky on <th> actually engage.
    table: ({ children }: MdProps) => (
      <div className="my-3 max-h-[60vh] overflow-auto rounded border border-border">
        <table className="min-w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    th: ({ children }: MdProps) => (
      <th className="sticky top-0 z-10 border border-border bg-surface-2 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {children}
      </th>
    ),
    td: ({ children }: MdProps) => (
      <td className="border border-border px-3 py-2 align-top text-ink-muted">
        {children}
      </td>
    ),
    blockquote: ({ children }: MdProps) => (
      <blockquote className="border-l-2 border-border pl-3 my-3 italic">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="border-border my-4" />,
  };
}

export function DocumentPreview({
  content,
  source,
  markdown,
}: {
  content: string;
  source?: string;
  // Force the Markdown path (chunk previews always carry text_md). Without
  // it the heuristic scores signals and a pure GFM table chunk -- no
  // headings, fences or links -- would be misclassified as plain text.
  markdown?: boolean;
}) {
  const normalized = useMemo(() => normalizeContent(content), [content]);
  const renderMarkdown = useMemo(
    () => markdown ?? looksLikeMarkdown(normalized),
    [markdown, normalized]
  );
  const blocks = useMemo(
    () => (renderMarkdown ? [] : parsePlainText(normalized)),
    [normalized, renderMarkdown]
  );
  const components = useMemo(() => markdownComponents(source), [source]);

  if (renderMarkdown) {
    return (
      <div>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSanitize]}
          components={components}
        >
          {normalized}
        </ReactMarkdown>
      </div>
    );
  }
  return <div>{renderBlocks(blocks)}</div>;
}
