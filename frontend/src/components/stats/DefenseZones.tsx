import type { DefensiveZone } from "@/types/api";
import { cn } from "@/lib/utils";

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function diffColor(pctPlusMinus: number | null | undefined): string {
  if (pctPlusMinus == null) return "";
  // Negative pct_plusminus means opponents shoot WORSE = good defense
  if (pctPlusMinus <= -0.03) return "text-[color:var(--color-positive)]";
  if (pctPlusMinus >= 0.03) return "text-[color:var(--color-negative)]";
  return "text-[color:var(--color-warning)]";
}

function diffBg(pctPlusMinus: number | null | undefined): string {
  if (pctPlusMinus == null) return "bg-[color:var(--color-surface-elevated)]";
  if (pctPlusMinus <= -0.03) return "bg-[color:var(--color-positive)]/10";
  if (pctPlusMinus >= 0.03) return "bg-[color:var(--color-negative)]/10";
  return "bg-[color:var(--color-warning)]/10";
}

interface DefenseZonesProps {
  zones: DefensiveZone[];
  className?: string;
}

export function DefenseZones({ zones, className }: DefenseZonesProps) {
  if (zones.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No defensive tracking data available
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Defensive impact by zone
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {zones.map((zone) => (
          <div
            key={zone.defense_category}
            className={cn(
              "rounded-xl border border-[color:var(--color-border)] p-3",
              diffBg(zone.pct_plusminus),
            )}
          >
            <p className="text-[10px] font-medium uppercase tracking-wider text-[color:var(--color-text-muted)]">
              {zone.defense_category}
            </p>
            <div className="mt-2 flex items-end justify-between">
              <div>
                <span className="text-xs text-[color:var(--color-text-muted)]">D-FG%</span>
                <span className="ml-1.5 font-mono text-sm font-semibold">{pct(zone.d_fg_pct)}</span>
              </div>
              <div>
                <span className="text-xs text-[color:var(--color-text-muted)]">Avg</span>
                <span className="ml-1.5 font-mono text-sm">{pct(zone.normal_fg_pct)}</span>
              </div>
            </div>
            {zone.pct_plusminus != null && (
              <div className={cn("mt-1 text-right font-mono text-xs font-semibold", diffColor(zone.pct_plusminus))}>
                {zone.pct_plusminus > 0 ? "+" : ""}{(zone.pct_plusminus * 100).toFixed(1)}%
              </div>
            )}
            {zone.freq != null && (
              <div className="mt-1 text-xs text-[color:var(--color-text-muted)]">
                Freq: {pct(zone.freq)} | {zone.d_fgm ?? 0}/{zone.d_fga ?? 0}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
