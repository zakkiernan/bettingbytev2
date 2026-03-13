import { PageTemplate } from "@/components/placeholders/page-template";

export default function PropDetailPage() {
  return (
    <PageTemplate
      eyebrow="/props/[signalId]"
      title="Transparent prop deep-dive"
      description="The deep-dive route is reserved for waterfall breakdowns, opportunity context, and recent history so the frontend can grow directly into the backend contract."
      apiContracts={[
        "GET /api/props/:signalId",
        "GET /api/players/:playerId/game-log?last=10",
      ]}
      highlights={[
        "Waterfall panels can visualize the exact scoring adjustments the new Pydantic contract exposes.",
        "Opportunity context and injury notes have their own slots instead of being squeezed into a generic stats card.",
        "A pick-tracking CTA area already exists conceptually, but no social or tracking logic is wired yet.",
      ]}
    />
  );
}
