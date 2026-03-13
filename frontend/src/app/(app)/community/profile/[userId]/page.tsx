import { PageTemplate } from "@/components/placeholders/page-template";

export default function CommunityProfilePage() {
  return (
    <PageTemplate
      eyebrow="/community/profile/[userId]"
      title="Public profile placeholder"
      description="Public profile routing is scaffolded so later community work does not need to revisit the app frame or route map."
      apiContracts={["GET /api/community/profile/:userId"]}
      highlights={[
        "Designed as a focused profile view rather than part of a monolithic community page.",
        "Future public stats can share patterns with the private picks area.",
        "No social functionality is active yet.",
      ]}
    />
  );
}
