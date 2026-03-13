import { PageTemplate } from "@/components/placeholders/page-template";

export default function LiveGamePage() {
  return (
    <PageTemplate
      eyebrow="/live/[gameId]"
      title="Single-game live tracker"
      description="This drilldown route is ready for the eventual live scoreboard, pace tracker, and alert feed, while remaining a placeholder until live model work is phase-appropriate."
      apiContracts={[
        "GET /api/live/:gameId",
        "WS /ws/live/:gameId",
      ]}
      highlights={[
        "Separate route keeps per-game live state isolated from the broader live center overview.",
        "Pace, alerts, and player rows already have typed contracts in the backend stub to build against.",
        "No live edge logic is implemented yet; this is structure only.",
      ]}
    />
  );
}
