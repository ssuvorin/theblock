"use client";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="page page-centered">
      <div className="page-header">
        <h1 className="page-title">Something went wrong</h1>
        <p className="page-subtitle">{error.message || "An unexpected error occurred."}</p>
      </div>
      <button className="btn btn-primary" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
