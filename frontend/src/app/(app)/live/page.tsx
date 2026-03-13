import { PageTemplate } from "@/components/placeholders/page-template";

export default function LivePage() {
  return (
    <PageTemplate
      eyebrow="/live"
      title="Live center preview"
      description="The live center shell is in place for active-game summaries, live player tables, alerts, and pace tracking once live backend outputs are trustworthy."
      apiContracts={[
        "GET /api/live/active",
        "GET /api/live/:gameId",
        "WS /ws/live/:gameId",
      ]}
      highlights={[
        "The route exists now, but live modeling and richer alerting remain intentionally out of scope until later phases.",
        "Mobile navigation still keeps this page one tap away so the eventual premium feature has a clear home.",
        "The detail route is scaffolded separately to support game-specific pace and alert panels later.",
      ]}
    />
  );
}
