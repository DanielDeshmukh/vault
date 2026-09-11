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
              {loading ? "Searching..." : "Ask"}
            </Button>
          </div>
        </form>
      </div>

      {/* Results Area */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-6 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              {error}
            </div>
          )}

          {!response && !loading && (
            <div className="text-center py-12">
              <p className="text-ink-muted text-lg">
                Ask a question to get started
              </p>
              <p className="text-ink-tertiary text-sm mt-2">
                Try: &quot;What did we promise Acme Corp?&quot; or &quot;What&apos;s our refund policy?&quot;
              </p>
            </div>
          )}

          {loading && (
            <div className="text-center py-12">
              <p className="text-ink-muted">Searching documents...</p>
            </div>
          )}

          {response && (
            <div className="space-y-6">
              {/* Answer */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Answer</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-invert max-w-none">
                    <p className="text-foreground whitespace-pre-wrap">{response.answer}</p>
                  </div>
                </CardContent>
              </Card>

              {/* Citations */}
              {response.citations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Sources</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {response.citations.map((citation, i) => (
                        <CitationCard key={i} citation={citation} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Trace ID */}
              <div className="text-xs text-ink-tertiary">
                Trace ID: {response.trace_id}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
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

  return (
    <div className="flex items-start gap-3 p-3 rounded-md bg-surface-2 border border-border">
      <span className="text-lg">{getSourceIcon(citation.source)}</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground truncate">{citation.title}</p>
        <p className="text-sm text-ink-muted">
          {citation.source} • Score: {(citation.score * 100).toFixed(1)}%
        </p>
      </div>
    </div>
  );
}
