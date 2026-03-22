import type { GameMatchup } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

interface MatchupGridProps {
  matchups: GameMatchup[];
  className?: string;
}

export function MatchupGrid({ matchups, className }: MatchupGridProps) {
  if (matchups.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No matchup data available
      </div>
    );
  }

  // Find primary defenders (most minutes guarding each offensive player)
  const primaryDefenders = new Map<string, string>();
  const byOffender = new Map<string, GameMatchup[]>();
  for (const m of matchups) {
    const existing = byOffender.get(m.offense_player_id) ?? [];
    existing.push(m);
    byOffender.set(m.offense_player_id, existing);
  }
  for (const [offId, ms] of byOffender) {
    const top = ms.sort((a, b) => b.matchup_minutes - a.matchup_minutes)[0];
    if (top) primaryDefenders.set(offId + "_" + top.defense_player_id, "primary");
  }

  // Show top 20 matchups by minutes
  const sorted = [...matchups].sort((a, b) => b.matchup_minutes - a.matchup_minutes).slice(0, 20);

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Player matchups
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-xs text-[color:var(--color-text-muted)]">
              <th className="pb-2 text-left font-medium">Offense</th>
              <th className="pb-2 text-left font-medium">Defender</th>
              <th className="pb-2 text-right font-medium">Min</th>
              <th className="pb-2 text-right font-medium">FGM/A</th>
              <th className="pb-2 text-right font-medium">FG%</th>
              <th className="pb-2 text-right font-medium">PTS</th>
              <th className="pb-2 text-right font-medium">SW</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]/50">
            {sorted.map((m, i) => {
              const isPrimary = primaryDefenders.has(m.offense_player_id + "_" + m.defense_player_id);
              return (
                <tr key={i} className="text-[color:var(--color-text-secondary)]">
                  <td className="py-2 font-medium text-[color:var(--color-text-primary)]">{m.offense_player_name}</td>
                  <td className="py-2">
                    <span className="flex items-center gap-1.5">
                      {m.defense_player_name}
                      {isPrimary && <Badge className="scale-75">Primary</Badge>}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono">{fmt(m.matchup_minutes)}</td>
                  <td className="py-2 text-right font-mono">
                    {fmt(m.matchup_field_goals_made, 0)}/{fmt(m.matchup_field_goals_attempted, 0)}
                  </td>
                  <td className="py-2 text-right font-mono">{pct(m.matchup_field_goal_percentage)}</td>
                  <td className="py-2 text-right font-mono">{fmt(m.player_points, 0)}</td>
                  <td className="py-2 text-right font-mono">{fmt(m.switches_on, 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
