import type { PointsBreakdown } from "@/types/api";

const ROWS: { key: keyof PointsBreakdown; label: string }[] = [
  { key: "base_scoring", label: "Base scoring" },
  { key: "minutes_adjustment", label: "Minutes adj." },
  { key: "recent_form_adjustment", label: "Recent form" },
  { key: "usage_adjustment", label: "Usage adj." },
  { key: "efficiency_adjustment", label: "Efficiency adj." },
  { key: "opponent_adjustment", label: "Opponent def." },
  { key: "pace_adjustment", label: "Pace adj." },
  { key: "context_adjustment", label: "Context adj." },
];

function AdjBadge({ value }: { value: number }) {
  if (Math.abs(value) < 0.01) {
    return (
      <span className="font-mono text-sm text-[color:var(--color-text-muted)]">
        —
      </span>
    );
  }
  const positive = value > 0;
  const color = positive
    ? "text-[color:var(--color-positive)]"
    : "text-[color:var(--color-negative)]";
  return (
    <span className={`font-mono text-sm font-medium ${color}`}>
      {positive ? "+" : ""}
      {value.toFixed(2)}
    </span>
  );
}

interface Props {
  breakdown: PointsBreakdown;
}

export function BreakdownTable({ breakdown }: Props) {
  return (
    <div className="space-y-1">
      {ROWS.map(({ key, label }) => (
        <div
          key={key}
          className="flex items-center justify-between rounded-xl px-3 py-2 odd:bg-[color:var(--color-surface-elevated)]/40"
        >
          <span className="text-sm text-[color:var(--color-text-secondary)]">
            {label}
          </span>
          {key === "base_scoring" ? (
            <span className="font-mono text-sm font-semibold">
              {breakdown.base_scoring.toFixed(2)}
            </span>
          ) : (
            <AdjBadge value={breakdown[key] as number} />
          )}
        </div>
      ))}

      <div className="mt-2 flex items-center justify-between rounded-2xl border border-[color:var(--color-accent)]/30 bg-[color:var(--color-accent-muted)] px-3 py-3">
        <span className="font-semibold">Projection</span>
        <span className="font-mono text-lg font-bold text-[color:var(--color-accent)]">
          {breakdown.projected_points.toFixed(1)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 pt-2">
        {[
          { label: "Exp. mins", value: breakdown.expected_minutes.toFixed(1) },
          {
            label: "Exp. usage",
            value: `${(breakdown.expected_usage_pct * 100).toFixed(1)}%`,
          },
          { label: "PPM", value: breakdown.points_per_minute.toFixed(3) },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/60 px-3 py-2 text-center"
          >
            <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              {label}
            </div>
            <div className="mt-1 font-mono text-sm font-semibold">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
