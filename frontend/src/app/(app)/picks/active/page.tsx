import { PageTemplate } from "@/components/placeholders/page-template";

export default function PicksActivePage() {
  return (
    <PageTemplate
      eyebrow="/picks/active"
      title="Active picks placeholder"
      description="A focused route for open picks is ready when pick persistence and resolution logic arrive."
      apiContracts={["GET /api/picks/active"]}
      highlights={[
        "Designed for fast scanability on mobile and desktop.",
        "Can reuse prop-row visuals without duplicating data styling rules.",
        "Resolution state is intentionally deferred.",
      ]}
    />
  );
}
