import type { ShotZone } from "@/types/api";
import { cn } from "@/lib/utils";

// League average FG% by zone (approximate 2025-26 benchmarks)
const LEAGUE_AVG: Record<string, number> = {
  "Restricted Area": 0.63,
  "In The Paint": 0.42,
  "Mid-Range": 0.42,
  "Left Corner 3": 0.38,
  "Right Corner 3": 0.38,
  "Above the Break 3": 0.36,
  "Backcourt": 0.05,
};

function zoneColor(fgPct: number, zone: string): string {
  const avg = LEAGUE_AVG[zone] ?? 0.4;
  const diff = fgPct - avg;
  if (diff > 0.05) return "bg-[color:var(--color-positive)]/20 text-[color:var(--color-positive)]";
  if (diff < -0.05) return "bg-[color:var(--color-negative)]/20 text-[color:var(--color-negative)]";
  return "bg-[color:var(--color-warning)]/20 text-[color:var(--color-warning)]";
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

interface ZoneHeatmapProps {
  zones: ShotZone[];
  className?: string;
}

export function ZoneHeatmap({ zones, className }: ZoneHeatmapProps) {
  if (zones.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No zone data available
      </div>
    );
  }

  const zoneMap = new Map(zones.map((z) => [z.zone, z]));

  function ZoneCard({ name }: { name: string }) {
    const z = zoneMap.get(name);
    if (!z || z.fga === 0) {
      return (
        <div className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/30 px-2 py-1.5 text-center text-xs text-[color:var(--color-text-muted)]">
          <div className="font-medium">{name}</div>
          <div>--</div>
        </div>
      );
    }
    return (
      <div className={cn("rounded-lg border border-[color:var(--color-border)] px-2 py-1.5 text-center", zoneColor(z.fg_pct, name))}>
        <div className="text-[10px] font-medium uppercase tracking-wider opacity-80">{name}</div>
        <div className="mt-0.5 font-mono text-sm font-bold">{pct(z.fg_pct)}</div>
        <div className="text-[10px] opacity-70">{z.fgm}/{z.fga}</div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Shooting zones
      </p>
      <div className="grid grid-cols-3 gap-2">
        <ZoneCard name="Left Corner 3" />
        <ZoneCard name="Above the Break 3" />
        <ZoneCard name="Right Corner 3" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <ZoneCard name="Mid-Range" />
        <ZoneCard name="In The Paint" />
        <ZoneCard name="Restricted Area" />
      </div>
    </div>
  );
}
