import { PageTemplate } from "@/components/placeholders/page-template";

export default function PicksHistoryPage() {
  return (
    <PageTemplate
      eyebrow="/picks/history"
      title="Pick history placeholder"
      description="History and performance reporting can land here once tracked picks and outcomes exist."
      apiContracts={["GET /api/picks/history", "GET /api/picks/stats"]}
      highlights={[
        "Pagination and export affordances can slot into the existing hero panel.",
        "Keeps historical reporting separate from active pick workflow.",
        "Future ROI charts can be added without route churn.",
      ]}
    />
  );
}
