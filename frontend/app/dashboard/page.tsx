"use client";

import { useState, useEffect } from "react";
import { api, QueryResponse, Citation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [userName, setUserName] = useState("");

  useEffect(() => {
    const user = localStorage.getItem("vault_user");
    if (user) {
      try {
        const parsed = JSON.parse(user);
        setUserName(parsed.full_name?.split(" ")[0] || "there");
      } catch {}
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setResponse(null);

    try {
      const result = await api.query(question);
      setResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const suggestedQueries = [
    { text: "What are the drug-free workplace policies?", icon: "📋" },
    { text: "What is the NIST Cybersecurity Framework?", icon: "🔒" },
    { text: "What are the employee leave policies?", icon: "📅" },
    { text: "What are the remote work guidelines?", icon: "🏠" },
    { text: "What benefits are offered to employees?", icon: "💰" },
    { text: "What are the code of conduct rules?", icon: "⚖️" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Query Input */}
      <div className="border-b border-border p-6">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-ink-tertiary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your documents..."
              className="pl-12 pr-24 py-6 text-base bg-surface-1 border-border focus:border-primary/50 focus:ring-primary/20"
              disabled={loading}
            />
            <div className="absolute inset-y-0 right-0 pr-2 flex items-center">
              <Button
                type="submit"
                disabled={loading || !question.trim()}
                className="px-6 py-2.5"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Searching...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Ask
                    <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/10 text-white/70">
                      ⏎
                    </kbd>
                  </span>
                )}
              </Button>
            </div>
          </div>
        </form>
      </div>

      {/* Results Area */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              {error}
            </div>
          )}

          {!response && !loading && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-center mb-12">
                <h1 className="text-4xl font-bold font-display mb-3 bg-gradient-to-r from-foreground via-ink-muted to-ink-tertiary bg-clip-text text-transparent">
                  Good {getTimeOfDay()}, {userName}
                </h1>
                <p className="text-ink-muted text-lg">
                  Search across all your authorized documents
                </p>
              </div>

              <div className="w-full max-w-2xl">
                <p className="text-xs font-medium text-ink-tertiary uppercase tracking-wider mb-4 text-center">
                  Try asking about
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {suggestedQueries.map((query, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setQuestion(query.text);
                        handleSubmit(new Event("submit") as any);
                      }}
                      className="group flex items-center gap-3 p-4 rounded-xl bg-surface-1 border border-border hover:border-primary/30 hover:bg-surface-2 transition-all duration-200 text-left"
                    >
                      <span className="text-lg flex-shrink-0">{query.icon}</span>
                      <span className="text-sm text-ink-muted group-hover:text-foreground transition-colors">
                        {query.text}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="relative">
                <div className="w-16 h-16 rounded-full border-4 border-surface-2 border-t-primary animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <svg className="w-6 h-6 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                  </svg>
                </div>
              </div>
              <p className="mt-6 text-ink-muted font-medium">Searching documents...</p>
              <p className="mt-1 text-sm text-ink-tertiary">Analyzing permissions and generating answer</p>
            </div>
          )}

          {response && (
            <div className="space-y-6">
              {/* Query Echo */}
              <div className="flex items-center gap-3 text-sm">
                <span className="text-ink-tertiary">Query</span>
                <div className="h-px flex-1 bg-border" />
                <span className="text-foreground font-medium">{question}</span>
              </div>

              {/* Answer */}
              <Card className="border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    Answer
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-invert max-w-none">
                    <p className="text-foreground whitespace-pre-wrap leading-relaxed">
                      {response.answer}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Citations */}
              {response.citations.length > 0 && (
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                        <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                      </div>
                      Sources ({response.citations.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-2">
                      {response.citations.map((citation, i) => (
                        <CitationCard key={i} citation={citation} index={i + 1} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Trace Info */}
              <div className="flex items-center justify-between text-xs text-ink-tertiary pt-4 border-t border-border">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-success" />
                  Trace: {response.trace_id.slice(0, 8)}
                </span>
                <span>{response.citations.length} sources cited</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getTimeOfDay() {
  const hour = new Date().getHours();
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "evening";
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      policy: "border-l-blue-500",
      compliance: "border-l-emerald-500",
      handbook: "border-l-violet-500",
      transcript: "border-l-amber-500",
    };
    return colors[source] || "border-l-gray-500";
  };

  return (
    <div className={`flex items-start gap-4 p-4 rounded-lg border border-border border-l-2 ${getSourceColor(citation.source)} bg-surface-1 hover:bg-surface-2 transition-colors`}>
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-surface-3 flex items-center justify-center text-xs font-medium text-ink-muted">
        {index}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground truncate">{citation.title}</p>
        <div className="flex items-center gap-3 mt-1 text-xs text-ink-muted">
          <span className="capitalize px-1.5 py-0.5 rounded bg-surface-3 text-ink-subtle">{citation.source}</span>
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            {(citation.score * 100).toFixed(0)}% match
          </span>
        </div>
      </div>
    </div>
  );
}
