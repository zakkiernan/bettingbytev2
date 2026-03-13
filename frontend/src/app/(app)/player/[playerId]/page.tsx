import { PageTemplate } from "@/components/placeholders/page-template";

export default function PlayerPage() {
  return (
    <PageTemplate
      eyebrow="/player/[playerId]"
      title="Player profile route"
      description="This route is ready for season averages, active props, game logs, and model insight copy, all centered around the player-first workflow in the product spec."
      apiContracts={[
        "GET /api/players/:playerId",
        "GET /api/players/:playerId/game-log?last=20",
        "GET /api/players/:playerId/trends",
      ]}
      highlights={[
        "Season averages and active props are separated so the page can balance static player context with live opportunity.",
        "Trend visualizations can be layered in later without changing the data contract or page path.",
        "The scaffold stays focused on points-first launch scope rather than prematurely expanding to every stat engine.",
      ]}
    />
  );
}
