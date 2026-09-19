"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import { api, Citation, StreamEvent } from "@/lib/api";
import { useSidebar } from "@/components/layout/sidebar";

interface ConversationTurn {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
  sources: Citation[];
  traceId: string;
  status: "streaming" | "done" | "error";
  error?: string;
}

const MAX_CONVERSATION_CONTEXT_CHARS = 6000;
const TYPING_CHARS_PER_TICK = 8;
const TYPING_TICK_MS = 32;

function buildConversationContext(turns: ConversationTurn[]): string | undefined {
  const completedTurns = turns.filter(turn => turn.status === "done").slice(-3);
  if (completedTurns.length === 0) return undefined;

  const context = completedTurns
    .map(turn => `User: ${turn.question}\nAssistant: ${turn.answer.slice(0, 1800)}`)
    .join("\n\n");

  return context.slice(-MAX_CONVERSATION_CONTEXT_CHARS);
}

export default function QueryPage() {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [firstName, setFirstName] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toggleCollapsed } = useSidebar();
  const turnIdRef = useRef(0);

  useEffect(() => {
    setMounted(true);
    try {
      const stored = localStorage.getItem("vault_user");
      if (stored) {
        const user = JSON.parse(stored);
        if (user.full_name) {
          setFirstName(user.full_name.split(" ")[0]);
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "b") {
        e.preventDefault();
        toggleCollapsed();
      }
      if (e.key === "Escape") {
        inputRef.current?.blur();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [toggleCollapsed]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns]);

  const autoResize = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, []);

  const handleSubmit = useCallback(async (question?: string) => {
    const q = question || input.trim();
    if (!q || isSearching) return;

    const conversationContext = buildConversationContext(turns);

    setInput("");
    setIsSearching(true);

    const turnId = `turn-${++turnIdRef.current}`;
    const newTurn: ConversationTurn = {
      id: turnId,
      question: q,
      answer: "",
      citations: [],
      sources: [],
      traceId: "",
      status: "streaming",
    };
    setTurns(prev => [...prev, newTurn]);

    let typingTimer: number | undefined;
    try {
      let accumulated = "";
      let pendingText = "";
      let streamErrored = false;
      let traceId = "";

      const flushPendingText = () => {
        if (!pendingText) return;
        const nextChunk = pendingText.slice(0, TYPING_CHARS_PER_TICK);
        pendingText = pendingText.slice(TYPING_CHARS_PER_TICK);
        accumulated += nextChunk;
        const snapshot = accumulated;
        setTurns(prev => prev.map(t =>
          t.id === turnId ? { ...t, answer: snapshot } : t
        ));
      };

      typingTimer = window.setInterval(flushPendingText, TYPING_TICK_MS);

      for await (const event of api.queryStream(q, conversationContext)) {
        if (event.type === "sources") {
          setTurns(prev => prev.map(t =>
            t.id === turnId ? { ...t, sources: event.sources } : t
          ));
        } else if (event.type === "delta") {
          pendingText += event.content;
        } else if (event.type === "citations") {
          setTurns(prev => prev.map(t =>
            t.id === turnId ? { ...t, citations: event.citations } : t
          ));
        } else if (event.type === "done") {
          traceId = event.trace_id;
        } else if (event.type === "error") {
          streamErrored = true;
          setTurns(prev => prev.map(t =>
            t.id === turnId ? { ...t, status: "error", error: event.detail } : t
          ));
        }
      }

      while (pendingText) {
        await new Promise(resolve => window.setTimeout(resolve, TYPING_TICK_MS));
      }

      if (!streamErrored) {
        setTurns(prev => prev.map(t =>
          t.id === turnId ? { ...t, traceId, status: "done" } : t
        ));
      }
    } catch (err) {
      setTurns(prev => prev.map(t =>
        t.id === turnId ? { ...t, status: "error", error: err instanceof Error ? err.message : "Query failed" } : t
      ));
    } finally {
      if (typingTimer) window.clearInterval(typingTimer);
      setIsSearching(false);
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
        inputRef.current.focus();
      }
    }
  }, [input, isSearching, turns]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const suggestedQueries = [
    "What are the employee leave policies?",
    "What is the NIST Cybersecurity Framework?",
    "What are the code of conduct rules?",
    "What are the remote work guidelines?",
    "What benefits are offered to employees?",
    "What is the drug-free workplace policy?",
  ];

  const hasConversation = turns.length > 0;

  return (
    <div className="flex flex-col h-full relative">
      {/* Scrollable area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {!hasConversation ? (
          /* Landing / empty state */
          <div className="flex flex-col items-center justify-center min-h-full px-4 pb-32">
            <div className="text-center mb-10">
              <div className="inline-flex items-center justify-center mb-5">
                <img
                  src="/tab-icon.png"
                  alt="Vault"
                  className="w-20 h-20 rounded-3xl"
                />
              </div>
              <h1 className="text-2xl font-semibold text-foreground mb-1.5 font-display">
                {mounted ? getGreeting(firstName) : "Hello"}
              </h1>
              <p className="text-sm text-ink-muted">
                Search across all your authorized documents
              </p>
            </div>

            <div className="w-full max-w-xl">
              <p className="text-[11px] font-medium uppercase tracking-wider text-ink-tertiary mb-3 text-center">
                Try asking
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestedQueries.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleSubmit(q)}
                    className="text-left px-4 py-3 rounded-xl bg-surface-1 border border-border hover:border-border-strong hover:bg-surface-2 transition-all text-sm text-ink-muted hover:text-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Conversation turns */
          <div className="max-w-3xl mx-auto px-4 py-8 pb-40">
            {turns.map((turn) => (
              <TurnView key={turn.id} turn={turn} />
            ))}
            {isSearching && !turns.find(t => t.status === "streaming") && (
              <div className="flex items-center gap-2 text-ink-muted text-sm py-4">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                Searching documents...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input bar - pinned to bottom */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background to-transparent pt-8 pb-4 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative bg-surface-1 border border-border rounded-2xl shadow-lg shadow-black/20 focus-within:border-border-strong transition-colors">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); autoResize(); }}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your documents..."
              rows={1}
              className="w-full resize-none bg-transparent text-foreground placeholder:text-ink-tertiary text-sm leading-relaxed px-4 py-3.5 pr-12 focus:outline-none rounded-2xl"
              disabled={isSearching}
            />
            <button
              onClick={() => handleSubmit()}
              disabled={!input.trim() || isSearching}
              className="absolute right-2.5 bottom-2.5 w-8 h-8 rounded-lg flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed bg-primary text-on-primary hover:bg-primary-hover"
            >
              {isSearching ? (
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" className="opacity-25" />
                  <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" className="opacity-75" />
                </svg>
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </div>
          <p className="text-center text-[11px] text-ink-tertiary mt-2">
            Vault searches your authorized documents. Results may vary.
          </p>
        </div>
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: ConversationTurn }) {
  const answerRef = useRef<HTMLDivElement>(null);
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    if (answerRef.current && turn.status === "streaming") {
      answerRef.current.scrollTop = answerRef.current.scrollHeight;
    }
  }, [turn.answer, turn.status]);

  const renderAnswer = (text: string) => {
    if (!text) return null;
    const markdown = text.replace(/\[([^\]\n]+)\]/g, (match, documentId) => {
      const citation = turn.citations.find(c => c.document_id === documentId);
      if (!citation) return match;
      const index = turn.citations.indexOf(citation) + 1;
      return `[${index}](citation:${encodeURIComponent(documentId)})`;
    });

    return (
      <ReactMarkdown
        urlTransform={(url) => url.startsWith("citation:") ? url : defaultUrlTransform(url)}
        components={{
          h1: ({ children }) => <h1 className="mt-7 mb-3 text-xl font-semibold tracking-tight text-foreground first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-7 mb-3 text-lg font-semibold tracking-tight text-foreground first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-6 mb-2 text-base font-semibold text-foreground first:mt-0">{children}</h3>,
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-4 list-disc space-y-1.5 pl-5 marker:text-ink-muted">{children}</ul>,
          ol: ({ children }) => <ol className="mb-4 list-decimal space-y-1.5 pl-5 marker:text-ink-muted">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
          a: ({ href, children }) => {
            if (href?.startsWith("citation:")) {
              const documentId = decodeURIComponent(href.slice("citation:".length));
              const citation = turn.citations.find(c => c.document_id === documentId);
              return (
                <button
                  type="button"
                  className="mx-0.5 inline-flex align-super text-[10px] font-medium text-primary hover:text-primary-hover"
                  title={citation?.title}
                  onClick={() => setShowSources(true)}
                >
                  [{children}]
                </button>
              );
            }
            return <a href={href} className="text-primary underline underline-offset-2 hover:text-primary-hover" target="_blank" rel="noreferrer">{children}</a>;
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    );
  };

  return (
    <div className="mb-8">
      {/* User question */}
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] bg-surface-2 border border-border rounded-2xl rounded-br-md px-4 py-2.5 text-sm text-foreground">
          {turn.question}
        </div>
      </div>

      {/* Answer */}
      <div className="flex gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 w-7 h-7 rounded-lg overflow-hidden mt-0.5">
          <img src="/tab-icon.png" alt="Vault" className="w-full h-full object-cover" />
        </div>

        <div className="flex-1 min-w-0">
          {turn.status === "error" ? (
            <div className="px-4 py-3 rounded-xl bg-red-500/5 border border-red-500/20 text-red-400 text-sm">
              {turn.error || "Something went wrong"}
            </div>
          ) : (
            <>
              <div
                ref={answerRef}
                className="text-sm text-foreground/90 leading-[1.7]"
              >
                {renderAnswer(turn.answer)}
                {turn.status === "streaming" && (
                  <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" />
                )}
              </div>

              {/* Sources */}
              {turn.sources.length > 0 && (
                <div className="mt-4">
                  <button
                    onClick={() => setShowSources(!showSources)}
                    className="flex items-center gap-1.5 text-xs text-ink-muted hover:text-foreground transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {turn.sources.length} source{turn.sources.length !== 1 ? "s" : ""}
                    <svg className={`w-3 h-3 transition-transform ${showSources ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>

                  {showSources && (
                    <div className="mt-3 space-y-2">
                      {turn.sources.map((src, i) => (
                        <SourceCard key={i} citation={src} index={i + 1} />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Trace */}
              {turn.status === "done" && turn.traceId && (
                <div className="mt-3 text-[11px] text-ink-tertiary">
                  {turn.citations.length} citation{turn.citations.length !== 1 ? "s" : ""} &middot; {turn.traceId.slice(0, 8)}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <div className="flex items-start gap-3 px-3 py-2.5 rounded-lg bg-surface-1 border border-border text-xs">
      <div className="flex-shrink-0 w-5 h-5 rounded bg-surface-3 flex items-center justify-center text-[10px] font-medium text-ink-muted">
        {index}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground truncate text-[13px]">{citation.title}</p>
        <div className="flex items-center gap-2 mt-1 text-ink-muted">
          <span className="capitalize">{citation.source}</span>
          <span className="text-ink-tertiary">&middot;</span>
          <span>{(citation.score * 100).toFixed(0)}% match</span>
        </div>
      </div>
    </div>
  );
}

function getGreeting(name: string) {
  const hour = new Date().getHours();
  const subject = name ? `, ${name}` : "";

  const greetings = hour < 12
    ? [
        `Good morning${subject}`,
        `Welcome back${subject}`,
        `Great to see you${subject}`,
      ]
    : hour < 17
    ? [
        `Good afternoon${subject}`,
        `Welcome back${subject}`,
        `Ready to work${subject}?`,
      ]
    : [
        `Good evening${subject}`,
        `Welcome back${subject}`,
        `Working late${subject}?`,
      ];

  const idx = Math.floor(Math.random() * greetings.length);
  return greetings[idx];
}
