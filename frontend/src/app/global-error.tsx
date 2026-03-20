"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body style={{ background: "#09090b", color: "#fafafa", fontFamily: "system-ui" }}>
        <div style={{ padding: "2rem" }}>
          <h2>Something went wrong</h2>
          <p style={{ color: "#a1a1aa" }}>{error.message}</p>
          <button
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1rem",
              background: "#5865F2",
              color: "#fff",
              border: "none",
              borderRadius: "0.375rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
