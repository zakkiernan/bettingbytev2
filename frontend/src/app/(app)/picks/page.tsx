import { PageTemplate } from "@/components/placeholders/page-template";

export default function PicksPage() {
  return (
    <PageTemplate
      eyebrow="/picks"
      title="Pick tracker shell"
      description="The picks route group is scaffolded so personal tracking can plug in later without reshaping navigation or page composition."
      apiContracts={[
        "GET /api/picks/active",
        "GET /api/picks/history",
        "GET /api/picks/stats",
      ]}
      highlights={[
        "Top-level picks route acts as the hub while active and history paths are already present.",
        "Nothing social is implemented here yet, keeping the current work aligned with your requested sequencing.",
        "Record, ROI, and streak visuals can land inside the existing placeholder grid.",
      ]}
    />
  );
}
