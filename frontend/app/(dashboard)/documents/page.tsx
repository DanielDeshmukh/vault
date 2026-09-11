"use client";

import { useState, useEffect } from "react";
import { api, Document } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

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

      const response = await fetch("http://localhost:8000/api/ingest/", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${api.getToken()}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this document?")) return;

    try {
      await api.deleteDocument(id);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const getSourceBadgeColor = (source: string) => {
    const colors: Record<string, string> = {
      zendesk: "bg-orange-500/20 text-orange-400",
      jira: "bg-blue-500/20 text-blue-400",
      slack: "bg-purple-500/20 text-purple-400",
      confluence: "bg-blue-600/20 text-blue-300",
      transcript: "bg-green-500/20 text-green-400",
      policy: "bg-gray-500/20 text-gray-400",
      csv: "bg-yellow-500/20 text-yellow-400",
    };
    return colors[source] || "bg-gray-500/20 text-gray-400";
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-ink-muted">Loading documents...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold font-display">Documents</h1>
            <p className="text-ink-muted mt-1">Manage your ingested documents</p>
          </div>
          <div>
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".csv,.pdf,.docx,.txt"
              onChange={handleUpload}
            />
            <Button asChild disabled={uploading}>
              <label htmlFor="file-upload" className="cursor-pointer">
                {uploading ? "Uploading..." : "Upload Document"}
              </label>
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {documents.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-ink-muted mb-4">No documents yet</p>
              <p className="text-sm text-ink-tertiary">
                Upload a CSV, PDF, or text file to get started
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {documents.map((doc) => (
              <Card key={doc.id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-lg">{doc.title}</CardTitle>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSourceBadgeColor(doc.source)}`}>
                      {doc.source}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(doc.id)}
                    className="text-ink-tertiary hover:text-destructive"
                  >
                    Delete
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-4 text-sm text-ink-muted">
                    {doc.account_id && <span>Account: {doc.account_id}</span>}
                    {doc.department && <span>Department: {doc.department}</span>}
                    <span>Access Level: {doc.access_level}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
