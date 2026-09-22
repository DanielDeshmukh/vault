import Link from "next/link";

export default function NotFound() {
  return (
    <div className="brutalist min-h-screen flex items-center justify-center px-6">
      <div className="max-w-lg text-center">
        <div className="mono text-6xl font-bold accent mb-6">404</div>
        <h1 className="b-h2 mb-4">Page not found.</h1>
        <p className="text-ink-muted mb-8">
          The page you are looking for does not exist or has been moved.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/" className="b-btn b-btn-accent">
            Back to Home
          </Link>
          <Link href="/dashboard" className="b-btn b-btn-outline">
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
