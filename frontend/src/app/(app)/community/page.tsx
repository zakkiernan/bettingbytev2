import { PageTemplate } from "@/components/placeholders/page-template";

export default function CommunityPage() {
  return (
    <PageTemplate
      eyebrow="/community"
      title="Community hub placeholder"
      description="The route exists for later social work, but the current scaffold keeps it intentionally light so it doesn’t compete with the critical-path line snapshot and API-contract work."
      apiContracts={[
        "GET /api/community/feed",
        "GET /api/community/leaderboard",
      ]}
      highlights={[
        "Feed, leaderboard, and public profile subroutes are already mapped so expansion stays organized.",
        "No social mechanics are implemented yet by design.",
        "The shell still gives frontend teams a realistic navigation target for mocks and prototypes.",
      ]}
    />
  );
}
