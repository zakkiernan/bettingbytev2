import type { PlayTypeEntry } from "@/types/api";
import { cn } from "@/lib/utils";

function percentileColor(p: number | null | undefined): string {
  if (p == null) return "bg-[color:var(--color-surface-elevated)]";
  if (p >= 75) return "bg-[color:var(--color-positive)]";
  if (p >= 50) return "bg-[color:var(--color-accent)]";
  if (p >= 25) return "bg-[color:var(--color-warning)]";
  return "bg-[color:var(--color-negative)]";
}

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

interface PlayTypeBreakdownProps {
  entries: PlayTypeEntry[];
  className?: string;
}

export function PlayTypeBreakdown({ entries, className }: PlayTypeBreakdownProps) {
  if (entries.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No play type data available
      </div>
    );
  }

  // Sort by possession percentage descending
  const sorted = [...entries].sort((a, b) => (b.poss_pct ?? 0) - (a.poss_pct ?? 0));

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Play type breakdown
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-xs text-[color:var(--color-text-muted)]">
              <th className="pb-2 text-left font-medium">Play Type</th>
              <th className="pb-2 text-right font-medium">Freq</th>
              <th className="pb-2 text-right font-medium">PPP</th>
              <th className="pb-2 text-right font-medium">FG%</th>
              <th className="pb-2 text-right font-medium">eFG%</th>
              <th className="pb-2 text-right font-medium">TOV%</th>
              <th className="pb-2 text-center font-medium">Pctile</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]/50">
            {sorted.map((entry) => (
              <tr key={entry.play_type} className="text-[color:var(--color-text-secondary)]">
                <td className="py-2 font-medium text-[color:var(--color-text-primary)]">{entry.play_type}</td>
                <td className="py-2 text-right font-mono">{pct(entry.poss_pct)}</td>
                <td className="py-2 text-right font-mono">{fmt(entry.ppp)}</td>
                <td className="py-2 text-right font-mono">{pct(entry.fg_pct)}</td>
                <td className="py-2 text-right font-mono">{pct(entry.efg_pct)}</td>
                <td className="py-2 text-right font-mono">{pct(entry.tov_pct)}</td>
                <td className="py-2">
                  <div className="flex items-center justify-center">
                    <div className="relative h-2 w-16 overflow-hidden rounded-full bg-[color:var(--color-surface-elevated)]">
                      <div
                        className={cn("absolute left-0 top-0 h-full rounded-full transition-all", percentileColor(entry.percentile))}
                        style={{ width: `${entry.percentile ?? 0}%` }}
                      />
                    </div>
                    <span className="ml-2 w-8 text-right font-mono text-xs">
                      {entry.percentile != null ? Math.round(entry.percentile) : "--"}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
