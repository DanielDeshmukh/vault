"use client";

import { useState, useCallback } from "react";

interface UseErrorHandlerOptions {
  onError?: (error: Error) => void;
  retryCount?: number;
  retryDelay?: number;
}

interface UseErrorHandlerReturn {
  error: Error | null;
  isLoading: boolean;
  handleError: (error: Error) => void;
  clearError: () => void;
  withRetry: <T>(fn: () => Promise<T>) => Promise<T>;
}

export function useErrorHandler({
  onError,
  retryCount = 3,
  retryDelay = 1000,
}: UseErrorHandlerOptions = {}): UseErrorHandlerReturn {
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleError = useCallback(
    (err: Error) => {
      setError(err);
      onError?.(err);
      console.error("Error:", err);
    },
    [onError]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const withRetry = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T> => {
      setIsLoading(true);
      setError(null);

      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= retryCount; attempt++) {
        try {
          const result = await fn();
          setIsLoading(false);
          return result;
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err));

          if (attempt < retryCount) {
            // Wait before retrying
            await new Promise((resolve) =>
              setTimeout(resolve, retryDelay * (attempt + 1))
            );
          }
        }
      }

      setIsLoading(false);
      if (lastError) {
        handleError(lastError);
      }
      throw lastError;
    },
    [retryCount, retryDelay, handleError]
  );

  return {
    error,
    isLoading,
    handleError,
    clearError,
    withRetry,
  };
}
