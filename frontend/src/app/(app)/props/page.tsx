import { PageTemplate } from "@/components/placeholders/page-template";

export default function PropsPage() {
  return (
    <PageTemplate
      eyebrow="/props"
      title="Prop board shell"
      description="This placeholder is built around the scannable table-first experience from the spec, with room for filters, tier gating, inline expansion, and fast refresh indicators."
      apiContracts={[
        "GET /api/props/board?date=today&stat_type=points",
        "GET /api/edges/today",
        "GET /api/players/:playerId/props",
      ]}
      highlights={[
        "Route scaffolding already includes a deep-dive path so table rows can expand or link without changing page structure later.",
        "The shell is dark-first and mono-heavy to match the terminal-like data identity from the frontend spec.",
        "Filter controls can drop into the hero band while the results grid stays stable across desktop and mobile.",
      ]}
    />
  );
}
