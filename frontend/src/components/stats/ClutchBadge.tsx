import type { ClutchStatsEntry } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

interface ClutchBadgeProps {
  entries: ClutchStatsEntry[];
  seasonFgPct?: number;
  className?: string;
}

export function ClutchBadge({ entries, seasonFgPct, className }: ClutchBadgeProps) {
  // Look for the "Last 5 Minutes" / within 5 points entry
  const primary = entries.find((e) => e.point_diff === 5) ?? entries[0];

  if (!primary || !primary.gp) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No clutch data available
      </div>
    );
  }

  const clutchFg = primary.fg_pct ?? 0;
  const isClutchPerformer = seasonFgPct != null && clutchFg > seasonFgPct + 0.03;
  const isPressureFades = seasonFgPct != null && clutchFg < seasonFgPct - 0.05;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Clutch performance
        </p>
        {isClutchPerformer && <Badge tone="success">Clutch Performer</Badge>}
        {isPressureFades && <Badge tone="danger">Pressure Fades</Badge>}
      </div>
      <p className="text-xs text-[color:var(--color-text-secondary)]">
        {primary.clutch_time} &middot; Within {primary.point_diff} points &middot; {primary.gp} games
      </p>
      <div className="grid grid-cols-4 gap-3 sm:grid-cols-7">
        <ClutchStat label="PTS" value={fmt(primary.pts)} />
        <ClutchStat label="FG%" value={pct(primary.fg_pct)} />
        <ClutchStat label="3P%" value={pct(primary.fg3_pct)} />
        <ClutchStat label="FT%" value={pct(primary.ft_pct)} />
        <ClutchStat label="AST" value={fmt(primary.ast)} />
        <ClutchStat label="TOV" value={fmt(primary.tov)} />
        <ClutchStat
          label="+/-"
          value={fmt(primary.plus_minus)}
          accent={primary.plus_minus != null && primary.plus_minus > 0}
          negative={primary.plus_minus != null && primary.plus_minus < 0}
        />
      </div>
      <p className="text-xs text-[color:var(--color-text-muted)]">
        Record: {primary.w ?? 0}-{primary.l ?? 0}
      </p>
    </div>
  );
}

function ClutchStat({
  label,
  value,
  accent,
  negative,
}: {
  label: string;
  value: string;
  accent?: boolean;
  negative?: boolean;
}) {
  return (
    <div className="flex flex-col items-center">
      <span
        className={cn(
          "font-mono text-sm font-semibold",
          accent && "text-[color:var(--color-positive)]",
          negative && "text-[color:var(--color-negative)]",
        )}
      >
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">{label}</span>
    </div>
  );
}
