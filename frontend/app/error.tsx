"use client";

import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="brutalist min-h-screen flex items-center justify-center px-6">
      <div className="max-w-lg text-center">
        <div className="mono text-6xl font-bold accent mb-6">500</div>
        <h1 className="b-h2 mb-4">Something went wrong.</h1>
        <p className="text-ink-muted mb-8">
          An unexpected error occurred while processing your request.
          {error.digest && (
            <span className="block mt-2 mono text-[11px] text-ink-tertiary">
              Error ID: {error.digest}
            </span>
          )}
        </p>
        <div className="flex gap-4 justify-center">
          <button onClick={reset} className="b-btn b-btn-accent">
            Try Again
          </button>
          <Link href="/" className="b-btn b-btn-outline">
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
