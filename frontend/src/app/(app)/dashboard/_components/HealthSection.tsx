import { fetchHealth } from "@/lib/api";
import { HealthCard } from "@/components/health/HealthCard";
import { Card } from "@/components/ui/card";

export default async function HealthSection() {
  const health = await fetchHealth().catch(() => null);

  if (!health) {
    return (
      <Card>
        <p className="text-sm text-[color:var(--color-text-secondary)]">
          Health data unavailable — API may be offline.
        </p>
      </Card>
    );
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Pipeline health
        </p>
        <span className="text-xs text-[color:var(--color-text-muted)]">
          {new Date(health.health_captured_at).toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            timeZone: "America/New_York",
          })}{" "}
          ET
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <HealthCard
          title="Lines"
          rows={[
            {
              label: "Tonight's games",
              value: health.lines.tonight_game_count,
            },
            {
              label: "Props captured",
              value: health.lines.tonight_prop_count,
            },
            {
              label: "Stale captures",
              value: health.lines.stale_captures,
              warn: health.lines.stale_captures > 0,
            },
            {
              label: "Oldest capture",
              value:
                health.lines.oldest_capture_age_minutes != null
                  ? `${health.lines.oldest_capture_age_minutes}m ago`
                  : "—",
              warn:
                (health.lines.oldest_capture_age_minutes ?? 0) > 60,
            },
            { label: "Source", value: health.lines.sportsbook },
          ]}
        />

        <HealthCard
          title="Rotations"
          rows={[
            {
              label: "Coverage",
              value: `${health.rotations.coverage_pct}%`,
              warn: health.rotations.coverage_pct < 95,
            },
            { label: "Pending", value: health.rotations.pending },
            { label: "Retry", value: health.rotations.retry },
            {
              label: "Quarantined",
              value: health.rotations.quarantined,
              warn: health.rotations.quarantined > 0,
            },
          ]}
        />

        <HealthCard
          title="Injury Reports"
          rows={[
            {
              label: "Latest report",
              value: health.injury_reports.latest_report_date ?? "—",
              warn: !health.injury_reports.latest_report_date,
            },
            {
              label: "Reports stored",
              value: health.injury_reports.reports_stored,
            },
            {
              label: "Entries stored",
              value: health.injury_reports.entries_stored.toLocaleString(),
            },
          ]}
        />

        <HealthCard
          title="Pregame Context"
          rows={[
            {
              label: "Games with context",
              value: health.pregame_context.tonight_games_with_context,
            },
            {
              label: "Games missing context",
              value: health.pregame_context.tonight_games_missing_context,
              warn:
                health.pregame_context.tonight_games_missing_context > 0,
            },
          ]}
        />

        <HealthCard
          title="Signal Run"
          rows={[
            {
              label: "Last run",
              value: health.signal_run.last_run_at
                ? new Date(
                    health.signal_run.last_run_at
                  ).toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    timeZone: "America/New_York",
                  })
                : "Not run",
              warn: !health.signal_run.last_run_at,
            },
            {
              label: "Signals generated",
              value: health.signal_run.signals_generated,
            },
            {
              label: "With recommendation",
              value: health.signal_run.signals_with_recommendation,
            },
          ]}
        />
      </div>
    </>
  );
}
