import { PageTemplate } from "@/components/placeholders/page-template";

export default function DashboardPage() {
  return (
    <PageTemplate
      eyebrow="/dashboard"
      title="Daily command center"
      description="The dashboard shell is wired for today’s slate cards, top edges, injury watch, picks summary, and live-now widgets without depending on backend query implementation yet."
      apiContracts={[
        "GET /api/games/today",
        "GET /api/edges/today?sort=confidence&limit=10",
        "GET /api/live/active",
      ]}
      highlights={[
        "Bento layout is ready for slate cards, top-edge cards, and fast context panels with mono data styling.",
        "The header stays mobile-friendly while preserving desktop density for daily decision-making.",
        "Free-vs-premium gating can slot in at the card level without reworking the page frame.",
      ]}
    />
  );
}
