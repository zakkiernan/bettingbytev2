import { PageTemplate } from "@/components/placeholders/page-template";

export default function CommunityLeaderboardPage() {
  return (
    <PageTemplate
      eyebrow="/community/leaderboard"
      title="Leaderboard placeholder"
      description="The leaderboard route is available for future retention and social proof features without affecting current product priorities."
      apiContracts={["GET /api/community/leaderboard"]}
      highlights={[
        "Route is separate so ranking logic and filters can evolve independently.",
        "The placeholder keeps room for 7d, 30d, and season windows.",
        "Still intentionally unimplemented beyond the skeleton.",
      ]}
    />
  );
}
