"use client";

import { useState } from "react";
import { api, QueryResponse, Citation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
    "What is our refund policy?",
    "What did we promise Acme Corp?",
    "What are the SLA response times?",
    "Show me recent support tickets",
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
              className="flex-1"
              disabled={loading}
            />
            <Button type="submit" disabled={loading || !question.trim()}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Searching...
                </span>
              ) : (
                "Ask"
              )}
            </Button>
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
            <div className="text-center py-16">
              <h2 className="text-2xl font-semibold font-display mb-2 text-foreground">
                Ask anything
              </h2>
              <p className="text-ink-muted mb-8">
                Search across all your authorized documents
              </p>
              
              <div className="flex flex-wrap justify-center gap-3 max-w-2xl mx-auto">
                {suggestedQueries.map((query, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuestion(query);
                      handleSubmit(new Event("submit") as any);
                    }}
                    className="px-4 py-2 rounded-lg bg-surface-1 border border-border text-sm text-ink-muted hover:bg-surface-2 hover:text-foreground transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          )}

          {loading && (
            <div className="text-center py-16">
              <div className="inline-flex items-center gap-3 text-ink-muted">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Searching documents and generating answer...</span>
              </div>
            </div>
          )}

          {response && (
            <div className="space-y-6">
              {/* Query Echo */}
              <div className="text-sm text-ink-muted">
                Query: <span className="text-foreground font-medium">{question}</span>
              </div>

              {/* Answer */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
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
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                      Sources ({response.citations.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3">
                      {response.citations.map((citation, i) => (
                        <CitationCard key={i} citation={citation} index={i + 1} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Trace Info */}
              <div className="flex items-center justify-between text-xs text-ink-tertiary pt-4 border-t border-border">
                <span>Trace ID: {response.trace_id}</span>
                <span>{response.citations.length} sources cited</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const getSourceIcon = (source: string) => {
    const icons: Record<string, string> = {
      zendesk: "🎫",
      jira: "📋",
      slack: "💬",
      confluence: "📄",
      transcript: "🎙️",
      policy: "📜",
      csv: "📊",
    };
    return icons[source] || "📄";
  };

  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      zendesk: "border-orange-500/30 bg-orange-500/5",
      jira: "border-blue-500/30 bg-blue-500/5",
      slack: "border-purple-500/30 bg-purple-500/5",
      confluence: "border-blue-400/30 bg-blue-400/5",
      transcript: "border-green-500/30 bg-green-500/5",
      policy: "border-gray-500/30 bg-gray-500/5",
      csv: "border-yellow-500/30 bg-yellow-500/5",
    };
    return colors[source] || "border-gray-500/30 bg-gray-500/5";
  };

  return (
    <div className={`flex items-start gap-3 p-4 rounded-lg border ${getSourceColor(citation.source)} transition-colors hover:bg-surface-2`}>
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center text-sm font-medium text-foreground">
        {index}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">{getSourceIcon(citation.source)}</span>
          <span className="font-medium text-foreground truncate">{citation.title}</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-ink-muted">
          <span className="capitalize">{citation.source}</span>
          <span>•</span>
          <span>Relevance: {(citation.score * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}
