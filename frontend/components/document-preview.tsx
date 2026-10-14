"use client";

import { useMemo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";

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

const MARKDOWN_COMPONENTS = {
  h1: ({ children }: MdProps) => <h1 className={H1}>{children}</h1>,
  h2: ({ children }: MdProps) => <h2 className={H2}>{children}</h2>,
  h3: ({ children }: MdProps) => <h3 className={H3}>{children}</h3>,
  h4: ({ children }: MdProps) => <h4 className={H4}>{children}</h4>,
  p: ({ children }: MdProps) => <p className={BODY}>{children}</p>,
  ul: ({ children }: MdProps) => (
    <ul className="list-disc pl-5 my-3">{children}</ul>
  ),
  ol: ({ children }: MdProps) => (
    <ol className="list-decimal pl-5 my-3">{children}</ol>
  ),
  li: ({ children }: MdProps) => <li className={ITEM}>{children}</li>,
  a: ({ children, href }: MdProps) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline underline-offset-2"
    >
      {children}
    </a>
  ),
  strong: ({ children }: MdProps) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: MdProps) => <em className="italic">{children}</em>,
  code: ({ children }: MdProps) => <code className={INLINE_CODE}>{children}</code>,
  pre: ({ children }: MdProps) => <pre className={BLOCK_CODE}>{children}</pre>,
  blockquote: ({ children }: MdProps) => (
    <blockquote className="border-l-2 border-border pl-3 my-3 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-border my-4" />,
};

export function DocumentPreview({ content }: { content: string }) {
  const markdown = useMemo(() => looksLikeMarkdown(content), [content]);
  const blocks = useMemo(
    () => (markdown ? [] : parsePlainText(content)),
    [content, markdown]
  );

  if (markdown) {
    return (
      <div>
        <ReactMarkdown components={MARKDOWN_COMPONENTS}>
          {content}
        </ReactMarkdown>
      </div>
    );
  }
  return <div>{renderBlocks(blocks)}</div>;
}
