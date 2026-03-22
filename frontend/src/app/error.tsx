"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[40vh] flex-col items-start justify-center gap-4 px-6 py-12">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-[color:var(--color-text-primary)]">
          Something went wrong
        </h2>
        <p className="max-w-xl text-sm text-[color:var(--color-text-muted)]">
          {error.message || "An unexpected error interrupted this page."}
        </p>
      </div>
      <button
        onClick={reset}
        className="rounded-lg bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}