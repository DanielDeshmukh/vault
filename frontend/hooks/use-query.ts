"use client";

import { useState } from "react";
import { api, QueryResponse } from "@/lib/api";

interface UseQueryReturn {
  query: (question: string) => Promise<void>;
  response: QueryResponse | null;
  loading: boolean;
  error: string | null;
  reset: () => void;
}

export function useQuery(): UseQueryReturn {
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = async (question: string) => {
    setLoading(true);
    setError(null);
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

  const reset = () => {
    setResponse(null);
    setError(null);
  };

  return { query, response, loading, error, reset };
}
