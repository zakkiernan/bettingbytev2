import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{ padding: "2rem" }}>
      <h2>Not Found</h2>
      <p style={{ color: "#a1a1aa" }}>Could not find the requested page.</p>
      <Link href="/dashboard" style={{ color: "#5865F2", marginTop: "1rem", display: "inline-block" }}>
        Back to Dashboard
      </Link>
    </div>
  );
}
