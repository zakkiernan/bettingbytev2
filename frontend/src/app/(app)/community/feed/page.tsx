import { PageTemplate } from "@/components/placeholders/page-template";

export default function CommunityFeedPage() {
  return (
    <PageTemplate
      eyebrow="/community/feed"
      title="Community feed placeholder"
      description="Reserved for public pick activity once social features are on deck."
      apiContracts={["GET /api/community/feed"]}
      highlights={[
        "List-first layout fits feed items well.",
        "Can inherit pick card styling later.",
        "No upvotes or comments yet.",
      ]}
    />
  );
}
