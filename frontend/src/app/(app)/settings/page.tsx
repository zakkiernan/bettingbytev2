import { PageTemplate } from "@/components/placeholders/page-template";

export default function SettingsPage() {
  return (
    <PageTemplate
      eyebrow="/settings"
      title="Account and preferences shell"
      description="Settings is scaffolded as the eventual home for account, subscription, and notification preferences, while auth remains mocked through NextAuth credentials."
      apiContracts={["GET /api/auth/me", "POST /api/auth/login", "POST /api/auth/register"]}
      highlights={[
        "Subscription controls can land here later without moving navigation.",
        "Route already matches the spec’s expectation for account and preferences management.",
        "Current auth is a thin frontend-backend wiring layer only.",
      ]}
    />
  );
}
