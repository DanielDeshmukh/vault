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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
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
    { text: "What are the drug-free workplace policies?", label: "Workplace Policy" },
    { text: "What is the NIST Cybersecurity Framework?", label: "NIST CSF" },
    { text: "What are the employee leave policies?", label: "Leave Policy" },
    { text: "What are the remote work guidelines?", label: "Remote Work" },
    { text: "What benefits are offered to employees?", label: "Benefits" },
    { text: "What are the code of conduct rules?", label: "Code of Conduct" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Query Input */}
      <div className="border-b border-border p-6">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your documents..."
              className="flex-1 h-11"
              disabled={loading}
            />
            <Button type="submit" disabled={loading || !question.trim()} className="h-11 px-6">
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Searching...
                </span>
              ) : "Ask"}
            </Button>
          </div>
        </form>
      </div>

      {/* Results Area */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {!response && !loading && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-center mb-12">
                <h1 className="text-3xl font-bold font-display mb-3 text-foreground">
                  {mounted ? getGreeting() : "Hello"}
                </h1>
                <p className="text-ink-muted">
                  Search across all your authorized documents
                </p>
              </div>

              <div className="w-full max-w-2xl">
                <p className="text-xs font-semibold uppercase tracking-wider text-ink-tertiary mb-4 text-center">
                  Suggested queries
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {suggestedQueries.map((query, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setQuestion(query.text);
                        handleSubmit(new Event("submit") as any);
                      }}
                      className="flex items-center gap-3 p-4 rounded-lg bg-surface-1 border border-border hover:border-border-strong hover:bg-surface-2 transition-colors text-left"
                    >
                      <span className="flex-shrink-0 text-xs font-mono text-ink-tertiary bg-surface-3 px-2 py-1 rounded">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="text-sm text-ink-muted">{query.text}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center py-20">
              <svg className="animate-spin h-8 w-8 text-primary" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <p className="mt-4 text-sm text-ink-muted">Searching documents...</p>
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
                  <CardTitle className="text-base">Answer</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-foreground whitespace-pre-wrap leading-relaxed">
                    {response.answer}
                  </div>
                </CardContent>
              </Card>

              {/* Citations */}
              {response.citations.length > 0 && (
                <Card className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">
                      Sources ({response.citations.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {response.citations.map((citation, i) => (
                        <CitationCard key={i} citation={citation} index={i + 1} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Trace Info */}
              <div className="flex items-center justify-between text-xs text-ink-tertiary pt-4 border-t border-border">
                <span>Trace: {response.trace_id.slice(0, 8)}</span>
                <span>{response.citations.length} sources cited</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg border border-border bg-surface-1">
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-surface-3 flex items-center justify-center text-xs font-medium text-ink-muted">
        {index}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground truncate">{citation.title}</p>
        <div className="flex items-center gap-3 mt-1 text-xs text-ink-muted">
          <span className="capitalize px-1.5 py-0.5 rounded bg-surface-3 text-ink-subtle">{citation.source}</span>
          <span>{(citation.score * 100).toFixed(0)}% match</span>
        </div>
      </div>
    </div>
  );
}
