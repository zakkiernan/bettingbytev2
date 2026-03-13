import { PageTemplate } from "@/components/placeholders/page-template";

export default function AlertsPage() {
  return (
    <PageTemplate
      eyebrow="/alerts"
      title="Alert center placeholder"
      description="This route is kept available for future notification preferences and history without adding logic outside the current requested scope."
      apiContracts={["GET /api/injuries/today", "GET /api/live/active"]}
      highlights={[
        "Notification settings can share visual patterns with the settings route.",
        "Future alert history can reuse table/list primitives from props and picks.",
        "No delivery system is implemented yet.",
      ]}
    />
  );
}
