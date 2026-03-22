import type { TeamLineupEntry } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

interface LineupLabProps {
  lineups: TeamLineupEntry[];
  className?: string;
}

const FEATURED_LINEUP_MINUTES_PER_GAME = 8;

export function LineupLab({ lineups, className }: LineupLabProps) {
  if (lineups.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No lineup data available
      </div>
    );
  }

  // Lineup stats are stored in per-game mode, so qualify using per-game minutes.
  const qualifiedLineups = lineups.filter((l) => (l.min ?? 0) >= FEATURED_LINEUP_MINUTES_PER_GAME);
  const deathLineup = qualifiedLineups.sort((a, b) => (b.net_rating ?? -999) - (a.net_rating ?? -999))[0];

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Lineup lab
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-xs text-[color:var(--color-text-muted)]">
              <th className="pb-2 text-left font-medium">Lineup</th>
              <th className="pb-2 text-right font-medium">GP</th>
              <th className="pb-2 text-right font-medium">MIN</th>
              <th className="pb-2 text-right font-medium">OffRtg</th>
              <th className="pb-2 text-right font-medium">DefRtg</th>
              <th className="pb-2 text-right font-medium">NetRtg</th>
              <th className="pb-2 text-right font-medium">+/-</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]/50">
            {lineups.map((l) => {
              const isDeath = deathLineup && l.group_id === deathLineup.group_id;
              const netColor = (l.net_rating ?? 0) > 0
                ? "text-[color:var(--color-positive)]"
                : (l.net_rating ?? 0) < 0
                  ? "text-[color:var(--color-negative)]"
                  : "";
              return (
                <tr key={l.group_id} className="text-[color:var(--color-text-secondary)]">
                  <td className="max-w-xs truncate py-2 text-xs font-medium text-[color:var(--color-text-primary)]">
                    <span className="flex items-center gap-1.5">
                      {l.group_name}
                      {isDeath && <Badge tone="success" className="scale-75">Death Lineup</Badge>}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono">{l.gp ?? "--"}</td>
                  <td className="py-2 text-right font-mono">{fmt(l.min)}</td>
                  <td className="py-2 text-right font-mono">{fmt(l.off_rating)}</td>
                  <td className="py-2 text-right font-mono">{fmt(l.def_rating)}</td>
                  <td className={cn("py-2 text-right font-mono font-semibold", netColor)}>{fmt(l.net_rating)}</td>
                  <td className="py-2 text-right font-mono">{fmt(l.plus_minus)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
